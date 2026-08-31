"""
phases/phase1_research.py
Competitive intelligence and trend analysis — Phase 1.

Workflow:
  1. Pull competitor posts via Apify (Instagram + LinkedIn)
  2. Send raw data to AI for structured trend analysis
  3. Return a Trend Report Card ready for human review

NOTE (2026-05-31): Now using REAL Apify scraping. The old mock generator is
preserved below as _scrape_competitors_mock for offline/AI-only testing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from core.ai_provider import build_provider_from_config
from core.database import get_db_context
from integrations.apify_client import ApifyClient
from integrations.free_research import (
    default_feeds,
    default_geo,
    fetch_google_trends,
    fetch_rss,
)
from integrations.web_search import default_country, gather_search
from models.db_models import AIProviderConfig, Brand, BrandSolution, Competitor, PhaseEnum, TrendReportCard

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pick(post: dict, keys: list[str], default: Any) -> Any:
    """Return the first present, non-empty value among `keys` (handles the fact
    that Instagram and LinkedIn scrapers use different field names)."""
    for k in keys:
        if k in post and post[k] not in (None, ""):
            return post[k]
    return default


def _default_keywords(brand) -> list[str]:
    """Fallback search keywords when a brand has not defined its areas of
    interest yet. The Sources tab lets the user set precise ones."""
    industry = brand.industry or "field operations software"
    return [
        f"{industry} trends",
        f"{industry} best practices",
        f"{brand.display_name} competitors",
    ]


# Baseline per-solution search terms, used when the brand has not entered its own
# per-solution keywords on the Sources tab. This guarantees every focus solution
# runs its OWN tagged search (so its report tab shows real, solution-specific
# sources) instead of everything collapsing into the "general" bucket.
_SOLUTION_KEYWORDS: dict[str, list[str]] = {
    "merchandising": ["retail merchandising execution", "planogram compliance", "in-store execution"],
    "field_audit": ["field audit", "retail store audit", "franchise compliance audit"],
    "field_sales": ["field sales execution", "retail field sales", "territory sales management"],
    "home_service": ["home service operations", "field service management", "service technician software"],
    "ai": ["AI image recognition retail", "computer vision retail shelf", "AI in field operations"],
}


def _solution_default_keywords(solution_value: str, brand) -> list[str]:
    """Per-solution fallback keywords when the Sources tab has none set for it."""
    base = list(_SOLUTION_KEYWORDS.get(solution_value, []))
    if base:
        return base
    label = str(solution_value).replace("_", " ").strip()
    industry = getattr(brand, "industry", None)
    return [f"{label} {industry}".strip()] if label else []


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
    sources: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior social media strategist with 10+ years of 
experience in US B2B and B2C markets. You analyze competitor content data and 
extract actionable trend signals.

You always respond in valid JSON only — no preamble, no markdown, no extra text.
Your analysis is sharp, specific, and grounded in the actual data provided."""

ANALYSIS_PROMPT = """Analyze the following research inputs and produce a structured Trend Report Card for the brand.

BRAND: {brand_name}
INDUSTRY: {industry}
PLANNING PERIOD: {planning_period}

BRAND FOCUS SOLUTIONS (cover these areas; tag each topic and gap with the solution it serves, or "general"):
{focus_solutions}

TARGETED WEB SEARCH RESULTS (each result carries a "solution" tag for the area it was gathered under, or null for general — prefer these and respect the tagging):
{search_results}

GOOGLE TRENDS (today's trending searches in the brand's region):
{google_trends}

RSS ARTICLES (recent industry / news headlines):
{rss_articles}

COMPETITOR POSTS (optional; may be empty):
{competitor_data}

RELEVANCE — critical: use ONLY inputs clearly relevant to {brand_name}'s industry
and the BRAND FOCUS SOLUTIONS above. Silently discard off-topic inputs — unrelated
consumer/platform trends, viral or entertainment topics, generic marketing news that
does not touch this brand's solutions. Never force an irrelevant item into the report
to fill space; fewer, sharper, on-point signals beat many loose ones. If an input is
only tangentially related, leave it out.

Ground EVERY trend signal in the inputs above. In each "sources" array, put the
actual article titles or URLs you used from the inputs — never invent a source.
Spread trending_topics and content_gaps across the BRAND FOCUS SOLUTIONS above, and
set each item's "solution" to the area it serves (one of the focus solutions, or
"general"). WRITING QUALITY — a human reviewer who is NOT a domain expert reads this report.
Write in plain, concrete English: no buzzwords, no vague filler, no "leverage synergies".
Every point must be specific and grounded in the inputs. Provide an "executive_summary"
and one "solution_brief" for EACH focus solution that has any real signal, so the reviewer
understands what is happening and what to create — even with no prior context.

Respond with a JSON object in exactly this structure:
{{
  "trending_topics": [
    {{"rank": 1, "topic": "...", "solution": "merchandising|field_audit|field_sales|home_service|ai|general", "signal_strength": "high|medium|low", "sources": ["..."], "why_it_matters": "..."}}
  ],
  "hot_formats": [
    {{"format": "...", "why_working": "...", "example_structure": "..."}}
  ],
  "content_gaps": [
    {{"gap": "...", "solution": "merchandising|field_audit|field_sales|home_service|ai|general", "opportunity": "...", "suggested_angle": "..."}}
  ],
  "algorithm_notes": {{
    "executive_summary": "3-5 plain sentences a non-expert can follow: what is happening in this brand's space this period and what it means for the content plan. No jargon.",
    "solution_briefs": [
      {{"solution": "merchandising|field_audit|field_sales|home_service|ai|general", "whats_happening": "2-3 plain sentences on the real trend or tension in this area right now", "why_it_matters": "1-2 sentences on why it matters to this brand's audience", "content_ideas": ["a concrete content idea grounded in the inputs", "another concrete idea"]}}
    ],
    "platform": {{"instagram": "one specific algorithm/format note", "linkedin": "one specific algorithm/format note"}}
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

    def __init__(
        self,
        apify_key: Optional[str] = None,
        search_provider: Optional[str] = None,
        search_key: Optional[str] = None,
    ) -> None:
        # Apify is optional; the free RSS + Google Trends path is the default.
        self._apify = ApifyClient(api_key=apify_key) if apify_key else None
        self._search_provider = search_provider or "serper"
        self._search_key = search_key

    async def run(
        self,
        brand_id: str,
        planning_period: str,
        max_posts_per_competitor: int = 20,
        progress=None,
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

            # Load focus solutions (E4b: research is gathered per solution).
            sol_result = await db.execute(
                select(BrandSolution)
                .where(
                    BrandSolution.brand_id == brand_id,
                    BrandSolution.is_active == True,  # noqa: E712
                    BrandSolution.is_focus == True,  # noqa: E712
                )
                .order_by(BrandSolution.priority.asc())
            )
            focus_solutions = [s.solution.value for s in sol_result.scalars().all()]

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

        _p = progress if callable(progress) else (lambda *a, **k: None)
        _p("Gathering sources: RSS feeds + targeted web search…")

        # Resolve research sources: free RSS + Google Trends is primary; Apify
        # competitor scraping is opt-in per brand (research_sources.use_apify).
        cfg = brand.research_sources or {}
        language = getattr(brand.language, "value", brand.language)
        feeds = cfg.get("rss_feeds") or default_feeds(language)
        geo = cfg.get("trends_geo") or default_geo(language)
        country = cfg.get("search_country") or default_country(language)
        use_apify = bool(cfg.get("use_apify")) and self._apify is not None

        # E4b: build per-solution search tasks. Each focus solution searches with
        # its own keywords; a general bucket uses the brand-wide keywords. Falls
        # back to brand-wide only (old behavior) when no per-solution keywords set.
        solution_keywords = cfg.get("solution_keywords") or {}
        sol_tasks: list = []
        for sv in focus_solutions:
            # Explicit per-solution keywords win; otherwise fall back to a baseline
            # so the solution still gets its OWN tagged search (not the general bucket).
            kws = solution_keywords.get(sv) or _solution_default_keywords(sv, brand)
            if kws:
                sol_tasks.append((sv, list(kws)))
        # A general bucket only when the brand set explicit brand-wide keywords, or
        # when there are no focus solutions at all (nothing to tag against).
        gen_kws = cfg.get("search_keywords") or ([] if sol_tasks else _default_keywords(brand))
        if gen_kws:
            sol_tasks.append((None, list(gen_kws)))

        rss_items = await fetch_rss(feeds)
        # Google Trends daily-trending is region-wide noise (unrelated viral topics),
        # so it is opt-in per brand (research_sources.use_trends). Targeted per-solution
        # search is the primary, relevant signal.
        trends_items = await fetch_google_trends(geo) if cfg.get("use_trends") else []
        _p(f"RSS: {len(rss_items)} article(s) gathered.")

        search_items: list = []
        if self._search_key:
            seen_urls: set = set()
            for sol, kws in sol_tasks:
                if not kws:
                    continue
                found = await gather_search(
                    self._search_provider, kws, self._search_key, country=country
                )
                added = 0
                for it in found:
                    u = it.get("url")
                    if u and u in seen_urls:
                        continue
                    if u:
                        seen_urls.add(u)
                    it["solution"] = sol
                    search_items.append(it)
                    added += 1
                _p(f"Searched {sol or 'general'}: {added} new source(s).")
        else:
            _p("No search provider key set — using RSS only.")

        competitor_data = (
            await self._scrape_competitors(competitors, max_posts_per_competitor)
            if use_apify
            else []
        )

        gathered_sources = {
            "keywords": gen_kws,
            "solution_keywords": {
                sv: solution_keywords[sv] for sv in focus_solutions if solution_keywords.get(sv)
            },
            "search": search_items,
            "rss": rss_items,
            "trends": trends_items,
        }

        _p(f"Collected {len(search_items)} search source(s). Running AI analysis…")

        # Run AI analysis
        report = await self._analyze_with_ai(
            brand=brand,
            planning_period=planning_period,
            search_items=search_items,
            rss_items=rss_items,
            trends_items=trends_items,
            competitor_data=competitor_data,
            ai_config=ai_config,
            focus_solutions=focus_solutions,
        )
        report.sources = gathered_sources

        # Save to DB
        await self._save_report(brand_id, planning_period, report)
        _p(
            f"Report saved — {len(report.trending_topics)} topic(s), "
            f"{len(report.content_gaps)} content gap(s)."
        )

        return report

    async def _scrape_competitors(
        self,
        competitors: list,
        max_posts: int,
    ) -> list[CompetitorData]:
        """Scrape posts from all competitors across available platforms."""
        if self._apify is None:
            return []
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

    async def _scrape_competitors_mock(
        self,
        competitors: list,
        max_posts: int,
    ) -> list[CompetitorData]:
        """MOCK data for offline / AI-only testing. Not called in normal runs.
        Swap this in place of _scrape_competitors if you need to test the AI
        pipeline without hitting Apify (and without spending Apify credits).
        """
        all_data = []
        for competitor in competitors:
            all_data.append(CompetitorData(
                name=competitor.name,
                platform="instagram",
                posts=[
                    {"caption": "Streamline your field service operations with our latest update.", "likes": 245, "comments": 18, "type": "post", "timestamp": "2026-05-01"},
                    {"caption": "5 ways to reduce technician downtime. Thread below.", "likes": 189, "comments": 34, "type": "post", "timestamp": "2026-05-05"},
                    {"caption": "Customer spotlight: How ABC Corp cut scheduling time by 40%.", "likes": 312, "comments": 27, "type": "carousel", "timestamp": "2026-05-10"},
                ],
            ))
            all_data.append(CompetitorData(
                name=competitor.name,
                platform="linkedin",
                posts=[
                    {"caption": "The future of field service management is mobile-first.", "likes": 156, "comments": 22, "type": "post", "timestamp": "2026-05-03"},
                    {"caption": "We just hit 10,000 customers. Here is what we learned.", "likes": 423, "comments": 61, "type": "post", "timestamp": "2026-05-08"},
                ],
            ))
        logger.info(f"Using mock data for {len(competitors)} competitors")
        return all_data

    async def _analyze_with_ai(
        self,
        brand: Brand,
        planning_period: str,
        search_items: list[dict],
        rss_items: list[dict],
        trends_items: list[dict],
        competitor_data: list[CompetitorData],
        ai_config,
        focus_solutions: Optional[list] = None,
    ) -> TrendReportResult:
        """Send scraped data to AI and parse the structured response."""

        # Format competitor data for the prompt.
        # Instagram and LinkedIn scrapers return different field names, so we
        # probe several likely keys for each metric (see _pick).
        formatted = []
        for cd in competitor_data:
            simplified_posts = [
                {
                    "caption": str(_pick(p, ["caption", "text"], ""))[:300],
                    "likes": _pick(p, ["likesCount", "likes", "numLikes", "reactionsCount", "totalReactionCount"], 0),
                    "comments": _pick(p, ["commentsCount", "comments", "numComments"], 0),
                    "shares": _pick(p, ["sharesCount", "shares", "numShares", "repostsCount"], 0),
                    "type": _pick(p, ["type", "postType"], "post"),
                    "timestamp": _pick(p, ["timestamp", "postedAtISO", "publishedAt", "timeSincePosted"], ""),
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

        competitor_block = (
            json.dumps(formatted, indent=2) if formatted else "(none — free research path)"
        )
        prompt = ANALYSIS_PROMPT.format(
            brand_name=brand.display_name,
            industry=brand.industry or "B2B SaaS",
            planning_period=planning_period,
            focus_solutions=", ".join(focus_solutions) if focus_solutions else "general",
            search_results=json.dumps(search_items, indent=2, ensure_ascii=False) if search_items else "(none)",
            google_trends=json.dumps(trends_items, indent=2, ensure_ascii=False) if trends_items else "(none)",
            rss_articles=json.dumps(rss_items, indent=2, ensure_ascii=False) if rss_items else "(none)",
            competitor_data=competitor_block,
        )

        response = await provider.complete(
            user_message=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=ai_config.temperature,
            # The enriched report (executive summary + per-solution briefs) is larger,
            # so give it real headroom to avoid a truncated, unparseable response.
            max_tokens=max(ai_config.max_tokens or 4096, 8000),
        )

        # Parse JSON response (model sometimes wraps it in ```json fences).
        data = self._parse_json_response(response.content)

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

    @staticmethod
    def _parse_json_response(content: str) -> dict:
        """Parse the AI's JSON output, tolerating markdown code fences or
        surrounding prose."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"AI response was not valid JSON: {content[:200]}")

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
                sources=report.sources,
                is_approved=False,
            )
            db.add(trend_report)
            logger.info(f"Trend report saved for {report.brand_slug} — {planning_period}")