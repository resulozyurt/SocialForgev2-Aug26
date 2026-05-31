"""
phases/phase3_copy.py
Phase 3 — Content generation (copywriting).

Reads an APPROVED Content Calendar (Phase 2 output) and turns each entry into a
full ContentPackage: hook variants, platform-native caption, CTA, tiered hashtags,
alt text, optional carousel/thread copy, plus a visual direction brief that Phase 4
will use to produce the actual image. Copy is generated in EN (primary, native US
English) and TR (localized adaptation).

One AI call per calendar entry → highest per-post quality. Failures on a single
entry are logged and skipped so the rest of the batch still completes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.ai_provider import build_provider_from_config
from core.database import get_db_context
from core.json_utils import parse_ai_json
from models.db_models import (
    AIProviderConfig,
    Brand,
    ContentCalendar,
    ContentPackage,
    ContentStatusEnum,
    ContentTypeEnum,
    PhaseEnum,
    PlatformEnum,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_platform(value: Optional[str]) -> PlatformEnum:
    try:
        return PlatformEnum(str(value).lower())
    except (ValueError, AttributeError):
        return PlatformEnum.INSTAGRAM


def _to_content_type(value: Optional[str]) -> ContentTypeEnum:
    try:
        return ContentTypeEnum(str(value).lower())
    except (ValueError, AttributeError):
        return ContentTypeEnum.STATIC


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


@dataclass
class CopyResult:
    brand_slug: str
    planning_period: str
    requested: int
    generated: int
    failed: int
    post_ids: list = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior social media copywriter for US brands with 10+ 
years of experience. You write in native American English — no translated phrasing, 
no stiff formality, no generic AI voice, no "excited to announce" energy. You write 
platform-native: Instagram, LinkedIn, and X each have their own DNA and you apply it 
automatically. You also produce a faithful, natural-sounding Turkish (TR) adaptation 
of the same post for the brand's localization needs.

You always respond in valid, strictly parseable JSON only — no preamble, no markdown, 
no extra text. CRITICAL: inside any JSON string value, do NOT use raw double quotes. 
If you need to quote a word or phrase inside the text, use single quotes ('like this'). 
Use straight apostrophes for contractions. Never let a double quote appear inside a 
string except as the delimiter of that string."""

COPY_PROMPT = """Write a complete content package for ONE social media post.

BRAND: {brand_name}
INDUSTRY: {industry}
BRAND VOICE: {voice}
PLATFORM: {platform}
CONTENT TYPE: {content_type}
CONTENT PILLAR: {pillar}
OBJECTIVE: {objective}
SCHEDULED DATE: {date}
HOOK CONCEPT (the scroll-stopping idea to build on): {hook_concept}
WHY THIS POST (strategic context from the calendar): {rationale}

Respond with a JSON object in exactly this structure:
{{
  "strategic_rationale": "3-4 sentences: why now, why this format for this platform, what audience behavior it's designed to trigger",
  "target_audience": "the specific persona/segment this post targets",
  "copy_en": {{
    "hooks": ["scroll-stopping hook variant A", "variant B", "variant C"],
    "caption": "full platform-appropriate caption in native US English (opening hook + body + CTA woven in naturally)",
    "cta": "one specific, non-generic call to action",
    "hashtags": {{"broad": ["..."], "niche": ["..."], "branded": ["..."]}},
    "alt_text": "accessibility description of the planned image",
    "carousel_slides": ["Slide 1 (cover): ...", "Slide 2: ...", "..."],
    "thread": ["Tweet 1 (hook): ...", "Tweet 2: ...", "..."]
  }},
  "copy_tr": {{ "hooks": ["..."], "caption": "...", "cta": "...", "hashtags": {{"broad": [], "niche": [], "branded": []}}, "alt_text": "...", "carousel_slides": [], "thread": [] }},
  "visual_direction": {{
    "concept": "what the image communicates at a glance",
    "mood": "e.g. bold and punchy / clean and minimal",
    "color_palette": ["#RRGGBB"],
    "composition": "layout guidance",
    "image_prompt": "a detailed, model-ready image generation prompt",
    "text_overlay": {{"primary": "exact text on the visual", "secondary": "supporting line"}}
  }}
}}

RULES:
- Only fill "carousel_slides" if CONTENT TYPE is carousel; otherwise use an empty array [].
- Only fill "thread" if PLATFORM is x or twitter; otherwise use an empty array [].
- Match caption length to the platform (Instagram: punchy, scannable; LinkedIn: longer, value-dense, line breaks).
- Hashtags: 2-3 broad, 3-5 niche, 2-3 branded.
- "copy_tr" mirrors "copy_en" in structure but reads as natural Turkish, not a literal translation.
- Inside text, quote phrases with single quotes only. Never put a raw double quote inside a JSON string value."""


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 Runner
# ─────────────────────────────────────────────────────────────────────────────

class Phase3Copy:
    """Generates full ContentPackages from an approved content calendar."""

    async def run(
        self,
        brand_id: str,
        calendar_id: Optional[object] = None,
        limit: Optional[int] = None,
        generate_tr: bool = True,
    ) -> CopyResult:
        """
        Generate content packages for an approved calendar.

        Args:
            brand_id:    UUID of the brand.
            calendar_id: Optional specific approved calendar id. If omitted, the
                         most recent APPROVED calendar for the brand is used.
            limit:       Generate copy for only the first N entries (handy for a
                         quick test before the full batch). None = all entries.
            generate_tr: Also produce the Turkish copy package.
        """
        async with get_db_context() as db:
            from sqlalchemy import select

            brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
            brand = brand_result.scalar_one_or_none()
            if not brand:
                raise ValueError(f"Brand {brand_id} not found.")

            # Resolve the approved calendar (the Phase 3 human-review gate).
            if calendar_id:
                cal_result = await db.execute(
                    select(ContentCalendar).where(ContentCalendar.id == calendar_id)
                )
                calendar = cal_result.scalar_one_or_none()
                if not calendar:
                    raise ValueError(f"Calendar {calendar_id} not found.")
                if not calendar.is_approved:
                    raise ValueError(
                        f"Calendar {calendar_id} is not approved yet. "
                        "Approve it before generating copy."
                    )
            else:
                cal_result = await db.execute(
                    select(ContentCalendar)
                    .where(
                        ContentCalendar.brand_id == brand_id,
                        ContentCalendar.is_approved == True,  # noqa: E712
                    )
                    .order_by(ContentCalendar.created_at.desc())
                )
                calendar = cal_result.scalars().first()
                if not calendar:
                    raise ValueError(
                        f"No approved calendar found for brand {brand_id}. "
                        "Run Phase 2 and approve a calendar first."
                    )

            config_result = await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.brand_id == brand_id,
                    AIProviderConfig.phase == PhaseEnum.COPY,
                )
            )
            ai_config = config_result.scalar_one_or_none()
            if not ai_config:
                raise ValueError(
                    f"No AI config found for Phase 3 (copy), brand {brand_id}. "
                    "Add one via POST /settings/providers with phase=phase3_copy."
                )

        # expire_on_commit=False keeps these objects usable outside the session.
        entries = list(calendar.entries or [])
        if limit:
            entries = entries[:limit]

        period = calendar.planning_period
        provider = build_provider_from_config(
            provider_name=ai_config.provider.value,
            model=ai_config.model,
            encrypted_api_key=ai_config.api_key_enc,
        )

        packages: list[ContentPackage] = []
        failed = 0
        for index, entry in enumerate(entries, start=1):
            try:
                data = await self._generate_copy(
                    brand=brand,
                    provider=provider,
                    temperature=ai_config.temperature,
                    max_tokens=ai_config.max_tokens,
                    entry=entry,
                    generate_tr=generate_tr,
                )
                pkg = self._build_package(
                    brand=brand,
                    brand_id=brand_id,
                    entry=entry,
                    data=data,
                    index=index,
                    period=period,
                    generate_tr=generate_tr,
                )
                packages.append(pkg)
                logger.info(f"Copy generated: {pkg.post_id} ({entry.get('platform')})")
            except Exception as exc:  # noqa: BLE001 — skip a bad entry, keep the batch
                failed += 1
                logger.warning(
                    f"Copy generation failed for entry {index} "
                    f"('{str(entry.get('hook_concept', ''))[:50]}'): {exc}"
                )

        await self._save_packages(packages)

        result = CopyResult(
            brand_slug=brand.slug,
            planning_period=period,
            requested=len(entries),
            generated=len(packages),
            failed=failed,
            post_ids=[p.post_id for p in packages],
        )
        logger.info(
            f"Phase 3 done for {brand.slug} — {period}: "
            f"{result.generated}/{result.requested} packages ({result.failed} failed)"
        )
        return result

    async def _generate_copy(
        self,
        brand: Brand,
        provider,
        temperature: float,
        max_tokens: int,
        entry: dict,
        generate_tr: bool,
    ) -> dict:
        """Build the prompt for one entry, call the AI, and parse the JSON."""
        prompt = COPY_PROMPT.format(
            brand_name=brand.display_name,
            industry=brand.industry or "B2B SaaS",
            voice=brand.voice_guide_text or "Confident, practical, peer-to-peer. No corporate fluff.",
            platform=entry.get("platform", "instagram"),
            content_type=entry.get("content_type", "static"),
            pillar=entry.get("pillar", ""),
            objective=entry.get("objective", "engagement"),
            date=entry.get("date", ""),
            hook_concept=entry.get("hook_concept", ""),
            rationale=entry.get("rationale", ""),
        )

        response = await provider.complete(
            user_message=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return parse_ai_json(response.content)

    def _build_package(
        self,
        brand: Brand,
        brand_id: str,
        entry: dict,
        data: dict,
        index: int,
        period: str,
        generate_tr: bool,
    ) -> ContentPackage:
        """Assemble a ContentPackage ORM object from the parsed AI output."""
        period_compact = period.replace("-", "")
        post_id = f"{brand.slug}-{period_compact}-{index:02d}-{uuid.uuid4().hex[:4]}"

        return ContentPackage(
            post_id=post_id,
            brand_id=brand_id,
            platform=_to_platform(entry.get("platform")),
            content_type=_to_content_type(entry.get("content_type")),
            status=ContentStatusEnum.DRAFT,
            scheduled_at=_parse_date(entry.get("date")),
            trend_signal=entry.get("rationale"),
            objective=(entry.get("objective") or "")[:64] or None,
            target_audience=data.get("target_audience"),
            strategic_rationale=data.get("strategic_rationale"),
            copy_package_en=data.get("copy_en"),
            copy_package_tr=data.get("copy_tr") if generate_tr else None,
            visual_direction=data.get("visual_direction"),
        )

    async def _save_packages(self, packages: list) -> None:
        """Persist all generated content packages in one transaction."""
        if not packages:
            logger.warning("No content packages to save.")
            return
        async with get_db_context() as db:
            db.add_all(packages)
            logger.info(f"Saved {len(packages)} content package(s).")