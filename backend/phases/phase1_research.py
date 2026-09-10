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
import zlib
from dataclasses import dataclass
from typing import Any, Optional

from core.ai_provider import build_provider_from_config
from core.database import get_db_context
from core.settings_store import get_app_setting
from integrations.apify_client import ApifyClient
from integrations.free_research import (
    default_feeds,
    default_geo,
    fetch_google_trends,
    fetch_rss,
)
from integrations.web_search import DEFAULT_RECENCY, default_country, gather_search
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


# Industry verticals per solution. Without these, research only ever searched a
# solution's core terms — and for field_audit those terms are retail-shaped, so the
# system never saw hospitality, construction or healthcare audit signal and the
# calendar kept framing every audit post as a retail shelf audit. A solution is a
# capability; a vertical is where it gets sold. Both belong in the search.
_SOLUTION_VERTICALS: dict[str, list[str]] = {
    "merchandising": [
        "grocery retail", "convenience stores", "pharmacy retail",
        "electronics retail", "beverage FMCG", "cosmetics retail",
    ],
    "field_audit": [
        "hotels and hospitality", "restaurants and QSR", "construction sites",
        "manufacturing plants", "healthcare facilities",
        "fuel and convenience stations", "bank branches", "retail stores",
        "warehouses and logistics",
    ],
    "field_sales": [
        "FMCG distribution", "pharmaceutical sales", "building materials",
        "beverage distribution", "wholesale distribution", "agriculture inputs",
    ],
    "home_service": [
        "HVAC", "plumbing and electrical", "telecom installation",
        "appliance repair", "solar and energy", "pest control",
    ],
    "ai": [
        "retail shelf recognition", "field inspection automation",
        "route optimization", "form and document automation",
        "predictive maintenance",
    ],
}

# How the solution reads inside a vertical query.
_SOLUTION_QUERY_LABEL: dict[str, str] = {
    "merchandising": "merchandising execution",
    "field_audit": "audit and inspection software",
    "field_sales": "field sales management",
    "home_service": "field service management",
    "ai": "AI automation",
}

# Verticals searched per solution per run. Kept small so a run stays cheap; the
# window rotates by planning period so successive months cover the rest.
_VERTICALS_PER_RUN = 4

# Vertical queries roughly double the gathered sources, so cap what goes into the
# prompt. Everything gathered is still stored in `sources` for the audit trail —
# this only bounds the analysis input so a long run cannot overflow the model's
# context and come back as truncated, unparseable JSON.
_MAX_SEARCH_IN_PROMPT = 120


def _balanced_sample(items: list[dict], limit: int) -> list[dict]:
    """Trim to `limit` while keeping every solution represented.

    A plain head-slice would hand the model only the first solutions' results and
    silently starve the rest — exactly the imbalance this phase exists to prevent.
    Round-robin across solution buckets instead, preserving order within each."""
    if len(items) <= limit:
        return items
    buckets: dict[Any, list[dict]] = {}
    for it in items:
        buckets.setdefault(it.get("solution"), []).append(it)
    order = list(buckets)
    out: list[dict] = []
    idx = 0
    while len(out) < limit and any(buckets[k] for k in order):
        key = order[idx % len(order)]
        if buckets[key]:
            out.append(buckets[key].pop(0))
        idx += 1
    return out


def _solution_default_keywords(solution_value: str, brand) -> list[str]:
    """Per-solution fallback keywords when the Sources tab has none set for it."""
    base = list(_SOLUTION_KEYWORDS.get(solution_value, []))
    if base:
        return base
    label = str(solution_value).replace("_", " ").strip()
    industry = getattr(brand, "industry", None)
    return [f"{label} {industry}".strip()] if label else []


def _vertical_queries(solution_value: str, planning_period: str) -> dict[str, str]:
    """Vertical-specific queries for one solution, rotating by planning period.

    The rotation uses crc32 rather than hash(), which Python randomizes per
    process: re-running the same month must reproduce the same queries, while a
    different month should surface different industries."""
    verticals = _SOLUTION_VERTICALS.get(solution_value) or []
    if not verticals:
        return {}
    label = _SOLUTION_QUERY_LABEL.get(
        solution_value, str(solution_value).replace("_", " ")
    )
    offset = zlib.crc32((planning_period or "").encode("utf-8")) % len(verticals)
    picked = [
        verticals[(offset + i) % len(verticals)]
        for i in range(min(_VERTICALS_PER_RUN, len(verticals)))
    ]
    return {f"{v} {label} trends": v for v in picked}


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

SYSTEM_PROMPT = """You are a senior B2B content strategist briefing a marketing team
that does NOT know this industry. You read raw research inputs — search results, news
articles, competitor posts — and turn them into a decision-ready trend report.

You are rigorous about evidence. A claim you cannot point to in the inputs does not go
in the report. You would rather ship six sharp, well-sourced signals than fifteen vague
ones. You never pad, never hedge, and never write marketing language about marketing.

You always respond in valid JSON only — no preamble, no markdown, no extra text."""

ANALYSIS_PROMPT = """Analyze the research inputs below and produce a Trend Report Card for the brand.

BRAND: {brand_name}
INDUSTRY: {industry}
PLANNING PERIOD: {planning_period}

BRAND FOCUS SOLUTIONS (cover these areas; tag each topic and gap with the solution it serves, or "general"):
{focus_solutions}

TARGETED WEB SEARCH RESULTS (each carries a "solution" tag, and where present a "vertical" tag naming the industry it was gathered under):
{search_results}

GOOGLE TRENDS (today's trending searches in the brand's region):
{google_trends}

RSS ARTICLES (recent industry / news headlines):
{rss_articles}

COMPETITOR POSTS (optional; may be empty):
{competitor_data}

═══════════════════════════════════════════════════════════════
HOW TO READ THE INPUTS
═══════════════════════════════════════════════════════════════

SOURCE QUALITY — not every result is signal. Weight them in this order:
  1. News, research, survey data, regulator or association publications, and
     operator/practitioner accounts — these are real signal.
  2. Analyst and trade commentary — usable signal.
  3. Vendor marketing pages, product landing pages, "top 10 best software"
     listicles and SEO roundups — these are ADVERTISING, not evidence. They tell
     you a keyword is commercially contested, nothing more. Do NOT build a
     trending topic on them, and do not cite them as proof of a trend.
If after filtering an area has no real signal, say so plainly in its brief rather
than inventing one.

RELEVANCE — use only inputs clearly tied to {brand_name}'s industry and the focus
solutions. Silently discard unrelated consumer, platform or viral topics. Fewer,
sharper signals beat many loose ones.

INDUSTRY SPREAD — critical. Several results carry a "vertical" tag (hospitality,
construction, healthcare, manufacturing, logistics, retail, and so on). A solution
is a capability; the vertical is the industry that buys it. Do NOT collapse every
signal into the single industry this brand is best known for. When the inputs show
real activity in a vertical, name that vertical explicitly in the topic itself —
e.g. "Hospitality: chains moving nightly checks to mobile checklists", not a
generic "checklists are trending". Across all trending_topics, cover at least TWO
different verticals whenever the inputs support it.

EVIDENCE AND SIGNAL STRENGTH — set signal_strength from how many DISTINCT sources
support the point, not from how exciting it sounds:
  high   = 3 or more independent sources
  medium = 2 independent sources
  low    = 1 source, or the sources are weak/vendor-ish
Put the real article titles or URLs you used in each "sources" array. Never invent
a source, and never reuse the same source to justify a "high".

═══════════════════════════════════════════════════════════════
HOW TO WRITE
═══════════════════════════════════════════════════════════════

A non-expert reads this report and has to decide what to publish this month.
- Plain, concrete English. No buzzwords, no "leverage", no "in today's landscape".
- Every sentence carries information. If a line could appear in any report for any
  company, delete it.
- Prefer specifics from the inputs: numbers, named regulations, named events,
  dated changes, real operator complaints.
- Name the tension, not the theme. "Franchisees fail surprise audits because the
  checklist lives in a binder" beats "compliance is important".

VOLUME: 6-10 trending_topics, 4-6 content_gaps, 3-5 hot_formats, 3-5
recommended_pillars whose percentages sum to 100, and one solution_brief for EVERY
focus solution that has real signal.

Respond with a JSON object in exactly this structure:
{{
  "trending_topics": [
    {{"rank": 1, "topic": "Name the vertical when the inputs point to one, then the specific shift", "solution": "merchandising|field_audit|field_sales|home_service|ai|general", "signal_strength": "high|medium|low", "sources": ["real title or URL from the inputs"], "why_it_matters": "2-3 sentences: what changed, who feels it, and what this brand can say about it that a competitor cannot"}}
  ],
  "hot_formats": [
    {{"format": "...", "why_working": "...", "example_structure": "..."}}
  ],
  "content_gaps": [
    {{"gap": "what nobody in this space is saying well", "solution": "merchandising|field_audit|field_sales|home_service|ai|general", "opportunity": "why the gap is worth filling now", "suggested_angle": "a concrete post idea, specific enough to hand to a writer"}}
  ],
  "algorithm_notes": {{
    "executive_summary": "4-6 plain sentences for someone with no context: what is actually happening in this brand's space this period, WHICH INDUSTRIES are showing the most demand right now and which are quiet, and what that means for the month's content. Name the industries.",
    "solution_briefs": [
      {{"solution": "merchandising|field_audit|field_sales|home_service|ai|general", "whats_happening": "2-3 plain sentences on the real trend or tension in this area right now, naming the verticals the inputs point to", "why_it_matters": "1-2 sentences on why this brand's audience should care", "content_ideas": ["a concrete idea grounded in a specific input", "another, aimed at a different vertical"]}}
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
        vertical_plan: dict[str, dict[str, str]] = {}
        for sv in focus_solutions:
            # Explicit per-solution keywords win; otherwise fall back to a baseline
            # so the solution still gets its OWN tagged search (not the general bucket).
            kws = list(solution_keywords.get(sv) or _solution_default_keywords(sv, brand))
            # Always add rotating vertical queries on top. The brand's own keywords
            # describe the capability; these ask what is happening in the industries
            # that buy it, which is the signal the report was missing.
            verticals = _vertical_queries(sv, planning_period)
            if verticals:
                vertical_plan[sv] = verticals
                kws.extend(verticals.keys())
            if kws:
                sol_tasks.append((sv, kws))
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

        # Recency window keeps a "trend report" from becoming an archive sweep.
        recency = (await get_app_setting("research_recency")) or DEFAULT_RECENCY

        search_items: list = []
        if self._search_key:
            seen_urls: set = set()
            for sol, kws in sol_tasks:
                if not kws:
                    continue
                vmap = vertical_plan.get(sol or "", {})
                found = await gather_search(
                    self._search_provider,
                    kws,
                    self._search_key,
                    country=country,
                    recency=recency,
                    max_queries=len(kws),
                )
                added = 0
                for it in found:
                    u = it.get("url")
                    if u and u in seen_urls:
                        continue
                    if u:
                        seen_urls.add(u)
                    it["solution"] = sol
                    # Tag which industry this result came in under, so the report
                    # can talk about verticals instead of guessing at them.
                    vertical = vmap.get(it.get("query") or "")
                    if vertical:
                        it["vertical"] = vertical
                    search_items.append(it)
                    added += 1
                extra = f" ({len(vmap)} industry queries)" if vmap else ""
                _p(f"Searched {sol or 'general'}: {added} new source(s){extra}.")
        else:
            _p("No search provider key set — using RSS only.")

        competitor_data = (
            await self._scrape_competitors(competitors, max_posts_per_competitor)
            if use_apify
            else []
        )

        gathered_sources = {
            "keywords": gen_kws,
            "recency": recency,
            "vertical_queries": {
                sv: sorted(vmap.values()) for sv, vmap in vertical_plan.items()
            },
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
            search_items=_balanced_sample(search_items, _MAX_SEARCH_IN_PROMPT),
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