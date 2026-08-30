"""
integrations/free_research.py
Free, legitimate research sources for Phase 1 — RSS feeds and Google Trends
daily trending searches. No paid API and no heavy dependencies (only feedparser).

This is the primary, free research signal source. Apify (paid competitor
scraping) is optional and stays behind a per-brand flag.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import feedparser

logger = logging.getLogger(__name__)

# Google Trends publishes daily trending searches per region as RSS.
GOOGLE_TRENDS_RSS = "https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"

# Sensible default feeds when a brand has not configured its own.
DEFAULT_FEEDS_EN = [
    # Retail-operations relevant feeds only. Generic social/platform-news feeds
    # (e.g. Social Media Today) were dropped — they produced off-topic noise
    # (unrelated platform/affiliate stories) with no tie to field operations.
    "https://www.retaildive.com/feeds/news/",
    "https://www.modernretail.co/feed/",
]
DEFAULT_FEEDS_TR = [
    "https://webrazzi.com/feed",
    "https://www.retaildive.com/feeds/news/",
]

_TAG_RE = re.compile(r"<[^>]+>")


def default_feeds(language: str) -> list[str]:
    return DEFAULT_FEEDS_TR if str(language).lower() == "tr" else DEFAULT_FEEDS_EN


def default_geo(language: str) -> str:
    return "TR" if str(language).lower() == "tr" else "US"


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text or "").replace("\xa0", " ").strip()


def _parse(url: str):
    # feedparser.parse does its own (blocking) HTTP fetch + parsing.
    return feedparser.parse(url)


async def fetch_rss(feeds: list[str], max_items_per_feed: int = 8) -> list[dict[str, Any]]:
    """Gather recent entries from a list of RSS/Atom feed URLs. Feed failures
    are logged and skipped so one bad feed never breaks the run."""
    items: list[dict[str, Any]] = []
    for url in feeds:
        try:
            parsed = await asyncio.to_thread(_parse, url)
            source = (parsed.feed.get("title") if getattr(parsed, "feed", None) else None) or url
            for entry in (parsed.entries or [])[:max_items_per_feed]:
                items.append(
                    {
                        "source": source,
                        "title": _clean(entry.get("title", "")),
                        "summary": _clean(entry.get("summary", "") or entry.get("description", ""))[:400],
                        "link": entry.get("link", ""),
                        "published": entry.get("published", "") or entry.get("updated", ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001 — one bad feed shouldn't kill the run
            logger.warning("RSS fetch failed for %s: %s", url, exc)
    logger.info("RSS gathered %d items from %d feeds", len(items), len(feeds))
    return items


async def fetch_google_trends(geo: str = "US", max_items: int = 15) -> list[dict[str, Any]]:
    """Gather today's trending searches for a region from Google Trends RSS."""
    url = GOOGLE_TRENDS_RSS.format(geo=geo)
    out: list[dict[str, Any]] = []
    try:
        parsed = await asyncio.to_thread(_parse, url)
        for entry in (parsed.entries or [])[:max_items]:
            out.append(
                {
                    "title": _clean(entry.get("title", "")),
                    "traffic": entry.get("ht_approx_traffic", "") or "",
                    "published": entry.get("published", ""),
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Trends fetch failed (geo=%s): %s", geo, exc)
    logger.info("Google Trends gathered %d items (geo=%s)", len(out), geo)
    return out
