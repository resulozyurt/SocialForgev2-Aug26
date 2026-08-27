"""
phases/phase2_calendar.py
Phase 2 — Content calendar scaffolding.

Reads an APPROVED Trend Report Card (Phase 1 output) and generates a monthly
content calendar: a list of planned posts (date, solution, pillar, platform,
content type, hook concept, ai_angle, objective) ready for human review before
Phase 3.

R2a (solution-aware): the calendar is now grounded in the brand's SOLUTION
taxonomy (brand_solutions), not just content pillars. A deterministic quota is
computed in Python so posts are balanced across the brand's focus solutions
(merchandising / field_audit / field_sales / home_service, with a small
general/brand carve-out). AI is treated as a CROSS-CUTTING theme: it gets no
standalone silo — instead a target share of posts carries a concrete "ai_angle"
showing how AI enhances that solution (e.g. "AI within merchandising").

Mirrors the Phase 1 architecture: load config from DB → call AI → parse the
structured JSON → persist.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from core.ai_provider import build_provider_from_config
from core.database import get_db_context
from models.db_models import (
    AIProviderConfig,
    Brand,
    BrandSolution,
    ContentCalendar,
    PhaseEnum,
    SolutionEnum,
    TrendReportCard,
)

logger = logging.getLogger(__name__)

DEFAULT_PLATFORMS = ["instagram", "linkedin"]
ALLOWED_CONTENT_TYPES = ["static", "carousel", "reel", "story", "thread"]

# The fixed taxonomy, mirrored from SolutionEnum for fast validation.
VALID_SOLUTIONS = {s.value for s in SolutionEnum}
# Solutions that never get their own quota bucket. "ai" is cross-cutting;
# "general" is a spillover/brand bucket handled separately.
_NON_PRIMARY = {"ai", "general"}
# Share of the month reserved for general/brand-level posts when the brand
# actually covers the "general" solution.
_GENERAL_SHARE = 0.15
# Share of posts that should carry a concrete AI angle when the brand treats AI
# as a focus (cross-cutting) area.
_AI_ANGLE_SHARE = 0.45


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CalendarResult:
    brand_slug: str
    planning_period: str
    post_count: int
    platforms: list
    entries: list
    summary: str
    raw_ai_output: str
    trend_report_card_id: object  # uuid.UUID
    solution_quota: Optional[dict] = None       # {solution: count} target
    ai_angle_target: int = 0                    # posts expected to carry an AI angle


# ─────────────────────────────────────────────────────────────────────────────
# Solution allocation (deterministic, computed in Python — not left to the LLM)
# ─────────────────────────────────────────────────────────────────────────────

def _allocate_solutions(solutions_meta: list, post_count: int) -> tuple[dict, int]:
    """
    Turn the brand's solution focus into an exact per-solution post quota that
    sums to post_count, plus a target number of posts that should carry an AI
    angle.

    solutions_meta: list of dicts {solution, is_focus, priority}.
    Returns (quota: {solution_value: count}, ai_angle_target: int).

    Rules:
      - "ai" gets no bucket (cross-cutting); "general" gets ~15% when present.
      - Focus, non-AI, non-general solutions split the rest by importance weight
        (1-5). Leftover posts go to the largest fractional share first, ties by
        priority (lower number wins).
      - If the brand has no usable primary solution, everything falls into
        "general" (or "ai" as a last resort) so the calendar still runs.
    """
    has_ai = any(s["solution"] == "ai" for s in solutions_meta)
    has_general = any(s["solution"] == "general" for s in solutions_meta)
    ai_angle_target = round(_AI_ANGLE_SHARE * post_count) if has_ai else 0

    primary = [s for s in solutions_meta if s["solution"] not in _NON_PRIMARY]
    focus_primary = [s for s in primary if s.get("is_focus")] or primary

    if not focus_primary:
        bucket = "general" if has_general else ("ai" if has_ai else "general")
        return {bucket: post_count}, ai_angle_target

    general_count = round(_GENERAL_SHARE * post_count) if has_general else 0
    # Never starve the primary solutions of at least one post each.
    general_count = max(0, min(general_count, post_count - len(focus_primary)))
    remaining = post_count - general_count

    # Split `remaining` across focus solutions weighted by importance (1-5),
    # using the largest-remainder method; ties break by priority (asc).
    weights = [max(1, int(s.get("importance") or 3)) for s in focus_primary]
    total_w = sum(weights) or len(focus_primary)
    exact = [remaining * w / total_w for w in weights]
    base = [int(x) for x in exact]
    leftover = remaining - sum(base)
    order = sorted(
        range(len(focus_primary)),
        key=lambda i: (-(exact[i] - base[i]), focus_primary[i].get("priority", 100)),
    )
    for k in range(leftover):
        base[order[k]] += 1

    quota: dict = {}
    for i, s in enumerate(focus_primary):
        quota[s["solution"]] = base[i]
    if general_count:
        quota["general"] = quota.get("general", 0) + general_count
    return quota, ai_angle_target


def _normalize_solution(value) -> str:
    """Coerce a model-produced solution label into a valid taxonomy value."""
    if not isinstance(value, str):
        return "general"
    v = value.strip().lower().replace("-", "_").replace(" ", "_")
    return v if v in VALID_SOLUTIONS else "general"


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior social media strategist building a monthly
content calendar for a B2B SaaS brand. You translate approved strategy (product
solution areas, content pillars, and trend signals) into a concrete,
platform-native posting plan.

You think in terms of the brand's SOLUTION areas first (what the product does),
then layer content pillars and trends on top. You treat AI as a cross-cutting
capability woven through those solutions, never as a separate content silo.

You always respond in valid JSON only — no preamble, no markdown, no extra text.
Every planned post is specific, scroll-stopping, and tied to a solution."""

CALENDAR_PROMPT = """Build a content calendar for the planning period below.

BRAND: {brand_name}
INDUSTRY: {industry}
PLANNING PERIOD: {planning_period}   (use real calendar dates inside this month)
TOTAL POSTS TO PLAN: {post_count}
TARGET PLATFORMS: {platforms}
ALLOWED CONTENT TYPES: {content_types}

BRAND SOLUTION AREAS (the product's focus — what each post should be about):
{solutions}

SOLUTION QUOTA — plan EXACTLY this many posts per solution (counts sum to {post_count}):
{solution_quota}

AI IS A CROSS-CUTTING THEME (not a separate bucket):
- Do NOT dedicate whole posts to a standalone "AI" topic.
- Instead, give about {ai_angle_target} of the posts a concrete "ai_angle": one
  sentence on how AI enhances THAT post's solution (e.g. for merchandising:
  "AI flags at-risk shelves before the rep leaves the store").
- Posts with no meaningful AI angle use "ai_angle": "".

APPROVED CONTENT PILLARS (thematic overlay — pick a fitting pillar per post):
{pillars}

TOP TRENDING TOPICS (from the approved trend report — anchor concepts to these):
{trending_topics}

HOT FORMATS THIS CYCLE:
{hot_formats}

RULES:
- Plan exactly {post_count} posts and honor the SOLUTION QUOTA exactly.
- "solution" MUST be one of the quota keys above, spelled exactly.
- Each entry targets exactly ONE platform from TARGET PLATFORMS. Pick a content
  type that fits that platform (e.g. carousel/reel/static/story for Instagram;
  static/carousel/thread for LinkedIn).
- Spread dates evenly across the planning month, preferring weekdays. Use ISO
  format "YYYY-MM-DD". Avoid scheduling more than ~2 posts on the same day.
- "hook_concept" is a single punchy line describing the scroll-stopping idea —
  not a full caption.
- "objective" is one of: awareness, engagement, conversion, retention, community.

Respond with a JSON object in exactly this structure:
{{
  "summary": "2-3 sentence overview of the month's content strategy, including how solutions and AI are balanced",
  "entries": [
    {{
      "date": "{planning_period}-03",
      "solution": "merchandising",
      "pillar": "...",
      "platform": "instagram",
      "content_type": "carousel",
      "hook_concept": "...",
      "ai_angle": "how AI enhances this post's solution, or empty string",
      "objective": "engagement",
      "rationale": "one sentence tying this to a solution, pillar, or trend"
    }}
  ]
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 Runner
# ─────────────────────────────────────────────────────────────────────────────

class Phase2Calendar:
    """Orchestrates content calendar generation from an approved trend report."""

    async def run(
        self,
        brand_id: str,
        report_id: Optional[object] = None,
        post_count: Optional[int] = None,
        platforms: Optional[list] = None,
    ) -> CalendarResult:
        """
        Generate a content calendar for a brand.

        Args:
            brand_id:   UUID of the brand.
            report_id:  Optional specific approved TrendReportCard id. If omitted,
                        the most recent APPROVED report for the brand is used.
            post_count: How many posts to plan. Defaults to brand.monthly_post_target.
            platforms:  Platforms to plan for. Defaults to instagram + linkedin.
        """
        async with get_db_context() as db:
            from sqlalchemy import select

            brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
            brand = brand_result.scalar_one_or_none()
            if not brand:
                raise ValueError(f"Brand {brand_id} not found.")

            # Resolve the approved trend report (the Phase 2 human-review gate).
            if report_id:
                rep_result = await db.execute(
                    select(TrendReportCard).where(TrendReportCard.id == report_id)
                )
                report = rep_result.scalar_one_or_none()
                if not report:
                    raise ValueError(f"Trend report {report_id} not found.")
                if not report.is_approved:
                    raise ValueError(
                        f"Trend report {report_id} is not approved yet. "
                        "Approve it before generating a calendar."
                    )
            else:
                rep_result = await db.execute(
                    select(TrendReportCard)
                    .where(
                        TrendReportCard.brand_id == brand_id,
                        TrendReportCard.is_approved == True,  # noqa: E712
                    )
                    .order_by(TrendReportCard.created_at.desc())
                )
                report = rep_result.scalars().first()
                if not report:
                    raise ValueError(
                        f"No approved trend report found for brand {brand_id}. "
                        "Run Phase 1 and approve a report first."
                    )

            # AI config for Phase 2.
            config_result = await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.brand_id == brand_id,
                    AIProviderConfig.phase == PhaseEnum.CALENDAR,
                )
            )
            ai_config = config_result.scalar_one_or_none()
            if not ai_config:
                raise ValueError(
                    f"No AI config found for Phase 2 (calendar), brand {brand_id}. "
                    "Add one via POST /settings/providers with phase=phase2_calendar."
                )

            # Brand solution focus (R2a). Extracted to plain dicts inside the
            # session so we don't depend on lazy-loading after it closes.
            sol_result = await db.execute(
                select(BrandSolution)
                .where(
                    BrandSolution.brand_id == brand_id,
                    BrandSolution.is_active == True,  # noqa: E712
                )
                .order_by(BrandSolution.priority.asc())
            )
            solutions_meta = [
                {
                    "solution": s.solution.value,
                    "is_focus": bool(s.is_focus),
                    "priority": s.priority,
                    "importance": int(s.importance or 3),
                    "concept_notes": s.concept_notes or "",
                }
                for s in sol_result.scalars().all()
            ]

        # expire_on_commit=False keeps these objects usable outside the session.
        resolved_post_count = post_count or brand.monthly_post_target or 20
        resolved_platforms = platforms or DEFAULT_PLATFORMS

        result = await self._generate_calendar(
            brand=brand,
            report=report,
            ai_config=ai_config,
            post_count=resolved_post_count,
            platforms=resolved_platforms,
            solutions_meta=solutions_meta,
        )

        await self._save_calendar(brand_id, result)
        return result

    async def _generate_calendar(
        self,
        brand: Brand,
        report: TrendReportCard,
        ai_config,
        post_count: int,
        platforms: list,
        solutions_meta: list,
    ) -> CalendarResult:
        """Build the prompt, call the AI, and parse the structured calendar."""
        pillars = report.recommended_pillars or []
        topics = report.trending_topics or []
        formats = report.hot_formats or []

        # Deterministic solution balance (falls back gracefully if the brand has
        # no solutions modeled yet — keeps older brands working).
        if solutions_meta:
            quota, ai_angle_target = _allocate_solutions(solutions_meta, post_count)
            solutions_block = json.dumps(
                [
                    {"solution": s["solution"], "focus": s["is_focus"],
                     "importance": s["importance"], "notes": s["concept_notes"]}
                    for s in solutions_meta
                ],
                indent=2, ensure_ascii=False,
            )
            quota_block = "\n".join(f"- {sol}: {cnt} posts" for sol, cnt in quota.items())
        else:
            quota, ai_angle_target = {}, 0
            solutions_block = "(no solution taxonomy modeled for this brand — plan by pillars only)"
            quota_block = "(no solution quota — distribute across pillars only)"

        prompt = CALENDAR_PROMPT.format(
            brand_name=brand.display_name,
            industry=brand.industry or "B2B SaaS",
            planning_period=report.planning_period,
            post_count=post_count,
            platforms=", ".join(platforms),
            content_types=", ".join(ALLOWED_CONTENT_TYPES),
            solutions=solutions_block,
            solution_quota=quota_block,
            ai_angle_target=ai_angle_target,
            pillars=json.dumps(pillars, indent=2, ensure_ascii=False),
            trending_topics=json.dumps(topics[:6], indent=2, ensure_ascii=False),
            hot_formats=json.dumps(formats, indent=2, ensure_ascii=False),
        )

        provider = build_provider_from_config(
            provider_name=ai_config.provider.value,
            model=ai_config.model,
            encrypted_api_key=ai_config.api_key_enc,
        )

        # A 30-post month with solution + ai_angle fields overflows a 4096-token
        # cap and gets truncated mid-JSON. Scale the ceiling to the plan size so
        # every entry fits; keep it within limits broadly supported by models.
        gen_max_tokens = min(max(ai_config.max_tokens or 4096, post_count * 200 + 1200), 8000)

        response = await provider.complete(
            user_message=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=ai_config.temperature,
            max_tokens=gen_max_tokens,
        )

        data = self._parse_json_response(response.content)
        entries = self._normalize_entries(data.get("entries", []))
        summary = data.get("summary", "")

        actual = {}
        for e in entries:
            actual[e["solution"]] = actual.get(e["solution"], 0) + 1
        logger.info(
            f"Generated {len(entries)} calendar entries for {brand.slug} — "
            f"{report.planning_period}. Target quota={quota or 'n/a'}; "
            f"actual={actual or 'n/a'}; ai_angle_target={ai_angle_target}."
        )

        return CalendarResult(
            brand_slug=brand.slug,
            planning_period=report.planning_period,
            post_count=post_count,
            platforms=platforms,
            entries=entries,
            summary=summary,
            raw_ai_output=response.content,
            trend_report_card_id=report.id,
            solution_quota=quota or None,
            ai_angle_target=ai_angle_target,
        )

    @staticmethod
    def _normalize_entries(entries: list) -> list:
        """Guarantee every entry has a valid solution and an ai_angle key."""
        clean = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            e["solution"] = _normalize_solution(e.get("solution"))
            if not isinstance(e.get("ai_angle"), str):
                e["ai_angle"] = ""
            clean.append(e)
        return clean

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """Parse the AI's JSON output, tolerating code fences, prose, or a
        response truncated by the token limit (salvages complete entries)."""
        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        salvaged = Phase2Calendar._salvage_entries(text)
        if salvaged["entries"]:
            logger.warning(
                "Calendar JSON was malformed/truncated — salvaged %d entries.",
                len(salvaged["entries"]),
            )
            return salvaged
        raise ValueError(f"AI response was not valid JSON: {content[:200]}")

    @staticmethod
    def _salvage_entries(text: str) -> dict:
        """Recover the summary and every brace-balanced entry object from a
        malformed or truncated calendar response."""
        summary = ""
        m = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            summary = m.group(1)
        entries = []
        idx = text.find('"entries"')
        scan = text[idx:] if idx != -1 else text
        depth = 0
        start = None
        for i, ch in enumerate(scan):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        chunk = scan[start:i + 1]
                        try:
                            obj = json.loads(chunk)
                        except json.JSONDecodeError:
                            obj = None
                        if isinstance(obj, dict) and (
                            "date" in obj or "solution" in obj or "hook_concept" in obj
                        ):
                            entries.append(obj)
                        start = None
        return {"summary": summary, "entries": entries}

    async def _save_calendar(self, brand_id: str, result: CalendarResult) -> None:
        """Persist the content calendar to the database."""
        async with get_db_context() as db:
            calendar = ContentCalendar(
                brand_id=brand_id,
                trend_report_card_id=result.trend_report_card_id,
                planning_period=result.planning_period,
                post_count=result.post_count,
                platforms=result.platforms,
                entries=result.entries,
                summary=result.summary,
                raw_ai_output=result.raw_ai_output,
                is_approved=False,
            )
            db.add(calendar)
            logger.info(
                f"Content calendar saved for {result.brand_slug} — "
                f"{result.planning_period} ({len(result.entries)} entries)"
            )
