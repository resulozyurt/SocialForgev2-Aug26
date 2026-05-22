"""
phases/phase1_research.py
Competitive intelligence and trend analysis — Phase 1.

Workflow:
  1. Pull competitor posts via Apify (Instagram + LinkedIn)
  2. Send raw data to AI for structured trend analysis
  3. Return a Trend Report Card ready for human review
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from core.ai_provider import build_provider_from_config
from core.database import get_db_context
from integrations.apify_client import ApifyClient
from models.db_models import AIProviderConfig, Brand, Competitor, PhaseEnum, TrendReportCard

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompetitorData:
    name: str
    platform: str
    posts: list[dict]


@dataclass
class TrendReportResult:
    brand_slug: str
    planning_period: str
    trending_topics: list[dict]
    hot_formats: list[dict]
    content_gaps: list[dict]
    algorithm_notes: dict
    recommended_pillars: list[dict]
    raw_ai_output: str


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior social media strategist with 10+ years of 
experience in US B2B and B2C markets. You analyze competitor content data and 
extract actionable trend signals.

You always respond in valid JSON only — no preamble, no markdown, no extra text.
Your analysis is sharp, specific, and grounded in the actual data provided."""

ANALYSIS_PROMPT = """Analyze the following competitor social media posts and produce 
a structured Trend Report Card.

BRAND: {brand_name}
INDUSTRY: {industry}
PLANNING PERIOD: {planning_period}

COMPETITOR DATA:
{competitor_data}

Respond with a JSON object in exactly this structure:
{{
  "trending_topics": [
    {{"rank": 1, "topic": "...", "signal_strength": "high|medium|low", "sources": ["..."], "why_it_matters": "..."}}
  ],
  "hot_formats": [
    {{"format": "...", "why_working": "...", "example_structure": "..."}}
  ],
  "content_gaps": [
    {{"gap": "...", "opportunity": "...", "suggested_angle": "..."}}
  ],
  "algorithm_notes": {{
    "instagram": "...",
    "linkedin": "..."
  }},
  "recommended_pillars": [
    {{"name": "...", "description": "...", "percentage": 20, "rationale": "..."}}
  ]
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 Runner
# ─────────────────────────────────────────────────────────────────────────────

class Phase1Research:
    """
    Orchestrates the full Phase 1 competitive intelligence workflow.
    """

    def __init__(self, apify_key: str) -> None:
        self._apify = ApifyClient(api_key=apify_key)

    async def run(
        self,
        brand_id: str,
        planning_period: str,
        max_posts_per_competitor: int = 20,
    ) -> TrendReportResult:
        """
        Full Phase 1 run for a brand.

        Args:
            brand_id:       UUID of the brand to research.
            planning_period: e.g. "2025-06"
            max_posts_per_competitor: How many posts to pull per competitor.

        Returns:
            TrendReportResult with structured trend data.
        """
        async with get_db_context() as db:
            from sqlalchemy import select

            # Load brand
            brand_result = await db.execute(
                select(Brand).where(Brand.id == brand_id)
            )
            brand = brand_result.scalar_one_or_none()
            if not brand:
                raise ValueError(f"Brand {brand_id} not found.")

            # Load competitors
            comp_result = await db.execute(
                select(Competitor).where(Competitor.brand_id == brand_id)
            )
            competitors = comp_result.scalars().all()

            # Load AI config for Phase 1
            config_result = await db.execute(
                select(AIProviderConfig).where(
                    AIProviderConfig.brand_id == brand_id,
                    AIProviderConfig.phase == PhaseEnum.RESEARCH,
                )
            )
            ai_config = config_result.scalar_one_or_none()
            if not ai_config:
                raise ValueError(f"No AI config found for Phase 1, brand {brand_id}.")

        # Scrape competitor data
        competitor_data = await self._scrape_competitors(
            competitors, max_posts_per_competitor
        )

        # Run AI analysis
        report = await self._analyze_with_ai(
            brand=brand,
            planning_period=planning_period,
            competitor_data=competitor_data,
            ai_config=ai_config,
        )

        # Save to DB
        await self._save_report(brand_id, planning_period, report)

        return report

    async def _scrape_competitors(
        self,
        competitors: list,
        max_posts: int,
    ) -> list[CompetitorData]:
        """Scrape posts from all competitors across available platforms."""
        all_data = []

        for competitor in competitors:
            if competitor.instagram_handle:
                try:
                    posts = await self._apify.scrape_instagram_posts(
                        competitor.instagram_handle, max_posts
                    )
                    all_data.append(CompetitorData(
                        name=competitor.name,
                        platform="instagram",
                        posts=posts,
                    ))
                    logger.info(f"Scraped {len(posts)} Instagram posts from {competitor.name}")
                except Exception as exc:
                    logger.warning(f"Instagram scrape failed for {competitor.name}: {exc}")

            if competitor.linkedin_handle:
                try:
                    posts = await self._apify.scrape_linkedin_posts(
                        competitor.linkedin_handle, max_posts
                    )
                    all_data.append(CompetitorData(
                        name=competitor.name,
                        platform="linkedin",
                        posts=posts,
                    ))
                    logger.info(f"Scraped {len(posts)} LinkedIn posts from {competitor.name}")
                except Exception as exc:
                    logger.warning(f"LinkedIn scrape failed for {competitor.name}: {exc}")

        return all_data

    async def _analyze_with_ai(
        self,
        brand: Brand,
        planning_period: str,
        competitor_data: list[CompetitorData],
        ai_config,
    ) -> TrendReportResult:
        """Send scraped data to AI and parse the structured response."""

        # Format competitor data for the prompt
        formatted = []
        for cd in competitor_data:
            # Extract only essential fields to keep prompt size manageable
            simplified_posts = [
                {
                    "caption": p.get("caption", p.get("text", ""))[:300],
                    "likes": p.get("likesCount", p.get("likes", 0)),
                    "comments": p.get("commentsCount", p.get("comments", 0)),
                    "type": p.get("type", "post"),
                    "timestamp": p.get("timestamp", ""),
                }
                for p in cd.posts[:20]
            ]
            formatted.append({
                "competitor": cd.name,
                "platform": cd.platform,
                "posts": simplified_posts,
            })

        provider = build_provider_from_config(
            provider_name=ai_config.provider.value,
            model=ai_config.model,
            encrypted_api_key=ai_config.api_key_enc,
        )

        prompt = ANALYSIS_PROMPT.format(
            brand_name=brand.display_name,
            industry=brand.industry or "B2B SaaS",
            planning_period=planning_period,
            competitor_data=json.dumps(formatted, indent=2),
        )

        response = await provider.complete(
            user_message=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=ai_config.temperature,
            max_tokens=ai_config.max_tokens,
        )

        # Parse JSON response
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            # Try to extract JSON from response if there's surrounding text
            import re
            match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"AI response was not valid JSON: {response.content[:200]}")

        return TrendReportResult(
            brand_slug=brand.slug,
            planning_period=planning_period,
            trending_topics=data.get("trending_topics", []),
            hot_formats=data.get("hot_formats", []),
            content_gaps=data.get("content_gaps", []),
            algorithm_notes=data.get("algorithm_notes", {}),
            recommended_pillars=data.get("recommended_pillars", []),
            raw_ai_output=response.content,
        )

    async def _save_report(
        self,
        brand_id: str,
        planning_period: str,
        report: TrendReportResult,
    ) -> None:
        """Persist the Trend Report Card to the database."""
        async with get_db_context() as db:
            trend_report = TrendReportCard(
                brand_id=brand_id,
                planning_period=planning_period,
                trending_topics=report.trending_topics,
                hot_formats=report.hot_formats,
                content_gaps=report.content_gaps,
                algorithm_notes=report.algorithm_notes,
                recommended_pillars=report.recommended_pillars,
                raw_ai_output=report.raw_ai_output,
                is_approved=False,
            )
            db.add(trend_report)
            logger.info(f"Trend report saved for {report.brand_slug} — {planning_period}")