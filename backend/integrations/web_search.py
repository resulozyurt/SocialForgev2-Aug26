"""
integrations/web_search.py
Pluggable web-search layer for Phase 1 research. The active provider + key are
chosen from the in-app Settings page, so we are never locked to one vendor.

Supported providers (all return a common shape):
  - serper      : Google SERP via serper.dev (generous free credits)
  - brave       : Brave Search API
  - google_cse  : Google Programmable Search (key form "APIKEY:SEARCHENGINEID")
  - tavily      : Tavily AI search

Each provider function returns list[{title, url, description, age}] and NEVER
raises — any failure logs and yields [] so research degrades gracefully.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SEARCH_PROVIDERS = ["serper", "brave", "google_cse", "tavily"]
_TAG_RE = re.compile(r"<[^>]+>")


def default_country(language: str) -> str:
    return "TR" if str(language).lower() == "tr" else "US"


def _clean(text: str) -> str:
    return _TAG_RE.sub("", text or "").replace("\xa0", " ").strip()


async def _serper(query: str, api_key: str, count: int, country: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "gl": country.lower(), "num": count},
        )
        resp.raise_for_status()
        data = resp.json()
    out = []
    for r in (data.get("organic") or [])[:count]:
        out.append({
            "title": _clean(r.get("title", "")),
            "url": r.get("link", ""),
            "description": _clean(r.get("snippet", ""))[:400],
            "age": r.get("date", ""),
        })
    return out


async def _brave(query: str, api_key: str, count: int, country: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params={"q": query, "count": count, "country": country, "freshness": "pm"},
        )
        resp.raise_for_status()
        data = resp.json()
    out = []
    for w in ((data.get("web") or {}).get("results") or [])[:count]:
        out.append({
            "title": _clean(w.get("title", "")),
            "url": w.get("url", ""),
            "description": _clean(w.get("description", ""))[:400],
            "age": w.get("age", "") or w.get("page_age", ""),
        })
    return out


async def _google_cse(query: str, api_key: str, count: int, country: str) -> list[dict[str, Any]]:
    # api_key form: "APIKEY:SEARCHENGINEID"
    key, _, cx = api_key.partition(":")
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": key, "cx": cx, "q": query, "num": min(count, 10), "gl": country.lower()},
        )
        resp.raise_for_status()
        data = resp.json()
    out = []
    for r in (data.get("items") or [])[:count]:
        out.append({
            "title": _clean(r.get("title", "")),
            "url": r.get("link", ""),
            "description": _clean(r.get("snippet", ""))[:400],
            "age": "",
        })
    return out


async def _tavily(query: str, api_key: str, count: int, country: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=25) as c:
        resp = await c.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": count},
        )
        resp.raise_for_status()
        data = resp.json()
    out = []
    for r in (data.get("results") or [])[:count]:
        out.append({
            "title": _clean(r.get("title", "")),
            "url": r.get("url", ""),
            "description": _clean(r.get("content", ""))[:400],
            "age": "",
        })
    return out


_DISPATCH = {
    "serper": _serper,
    "brave": _brave,
    "google_cse": _google_cse,
    "tavily": _tavily,
}


async def web_search(
    provider: str,
    query: str,
    api_key: str,
    count: int = 5,
    country: str = "US",
) -> list[dict[str, Any]]:
    if not api_key or not query:
        return []
    fn = _DISPATCH.get((provider or "serper").lower())
    if not fn:
        logger.warning("Unknown search provider %r", provider)
        return []
    try:
        return await fn(query, api_key, count, country)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Search (%s) failed for %r: %s", provider, query, exc)
        return []


async def gather_search(
    provider: str,
    keywords: list[str],
    api_key: str,
    count_per: int = 5,
    country: str = "US",
) -> list[dict[str, Any]]:
    """Run several keyword searches through the chosen provider, merge + dedupe by URL."""
    results: list[dict[str, Any]] = []
    for kw in keywords[:6]:
        for r in await web_search(provider, kw, api_key, count_per, country):
            r["query"] = kw
            results.append(r)
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in results:
        url = r.get("url")
        if url and url not in seen:
            seen.add(url)
            deduped.append(r)
    logger.info("Search (%s) gathered %d unique results from %d keywords", provider, len(deduped), len(keywords))
    return deduped
