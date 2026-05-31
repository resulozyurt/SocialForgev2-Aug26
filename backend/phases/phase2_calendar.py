"""
phases/phase2_calendar.py
Phase 2 — Content calendar scaffolding.

Reads an APPROVED Trend Report Card (Phase 1 output) and generates a monthly
content calendar: a list of planned posts (date, pillar, platform, content
type, hook concept, objective) ready for human review before Phase 3.

Mirrors the Phase 1 architecture: load config from DB → call AI → parse the
structured JSON → persist.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from core.ai_provider import build_provider_from_config
from core.database import get_db_context
from models.db_models import (
    AIProviderConfig,
    Brand,
    ContentCalendar,
    PhaseEnum,
    TrendReportCard,
)

logger = logging.getLogger(__name__)

DEFAULT_PLATFORMS = ["instagram", "linkedin"]
ALLOWED_CONTENT_TYPES = ["static", "carousel", "reel", "story", "thread"]


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


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior social media strategist building a monthly 
content calendar for a US brand. You translate approved strategy (content pillars 
and trend signals) into a concrete, platform-native posting plan.

You always respond in valid JSON only — no preamble, no markdown, no extra text.
Every planned post is specific, scroll-stopping, and tied to a content pillar."""

CALENDAR_PROMPT = """Build a content calendar for the planning period below.

BRAND: {brand_name}
INDUSTRY: {industry}
PLANNING PERIOD: {planning_period}   (use real calendar dates inside this month)
TOTAL POSTS TO PLAN: {post_count}
TARGET PLATFORMS: {platforms}
ALLOWED CONTENT TYPES: {content_types}

APPROVED CONTENT PILLARS (distribute posts across these by their percentage):
{pillars}

TOP TRENDING TOPICS (from the approved trend report — anchor concepts to these):
{trending_topics}

HOT FORMATS THIS CYCLE:
{hot_formats}

RULES:
- Plan exactly {post_count} posts.
- Distribute posts across pillars roughly matching each pillar's percentage.
- Each entry targets exactly ONE platform. Pick a content type that fits that
  platform (e.g. carousel/reel/static/story for Instagram; static/carousel/thread
  for LinkedIn). Only use platforms from TARGET PLATFORMS.
- Spread dates evenly across the planning month, preferring weekdays. Use ISO
  format "YYYY-MM-DD". Avoid scheduling more than ~2 posts on the same day.
- "hook_concept" is a single punchy line describing the scroll-stopping idea —
  not a full caption.
- "objective" is one of: awareness, engagement, conversion, retention, community.

Respond with a JSON object in exactly this structure:
{{
  "summary": "2-3 sentence overview of the month's content strategy",
  "entries": [
    {{
      "date": "{planning_period}-03",
      "pillar": "...",
      "platform": "instagram",
      "content_type": "carousel",
      "hook_concept": "...",
      "objective": "engagement",
      "rationale": "one sentence tying this to a pillar or trend"
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

        # expire_on_commit=False keeps these objects usable outside the session.
        resolved_post_count = post_count or brand.monthly_post_target or 20
        resolved_platforms = platforms or DEFAULT_PLATFORMS

        result = await self._generate_calendar(
            brand=brand,
            report=report,
            ai_config=ai_config,
            post_count=resolved_post_count,
            platforms=resolved_platforms,
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
    ) -> CalendarResult:
        """Build the prompt, call the AI, and parse the structured calendar."""
        pillars = report.recommended_pillars or []
        topics = report.trending_topics or []
        formats = report.hot_formats or []

        prompt = CALENDAR_PROMPT.format(
            brand_name=brand.display_name,
            industry=brand.industry or "B2B SaaS",
            planning_period=report.planning_period,
            post_count=post_count,
            platforms=", ".join(platforms),
            content_types=", ".join(ALLOWED_CONTENT_TYPES),
            pillars=json.dumps(pillars, indent=2, ensure_ascii=False),
            trending_topics=json.dumps(topics[:6], indent=2, ensure_ascii=False),
            hot_formats=json.dumps(formats, indent=2, ensure_ascii=False),
        )

        provider = build_provider_from_config(
            provider_name=ai_config.provider.value,
            model=ai_config.model,
            encrypted_api_key=ai_config.api_key_enc,
        )

        response = await provider.complete(
            user_message=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=ai_config.temperature,
            max_tokens=ai_config.max_tokens,
        )

        data = self._parse_json_response(response.content)
        entries = data.get("entries", [])
        summary = data.get("summary", "")

        logger.info(
            f"Generated {len(entries)} calendar entries for {brand.slug} — "
            f"{report.planning_period}"
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
        )

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """Parse the AI's JSON output, tolerating markdown fences or prose."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"AI response was not valid JSON: {content[:200]}")

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