"""
scripts/test_apify.py
Standalone Apify connectivity test.

Calls the Instagram and LinkedIn scrapers directly (bypassing the Phase 1
pipeline) so we can see the EXACT error/response from Apify, including the
body of any 400 Bad Request.

Run from the backend directory:
    .venv\\Scripts\\activate
    python scripts/test_apify.py
"""

import asyncio
import json
import os
import sys
import traceback

# Make `core`, `integrations`, etc. importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import httpx

from core.config import get_settings
from integrations.apify_client import ApifyClient

# ── Test targets (FieldPie competitors) ─────────────────────────────────────
INSTAGRAM_HANDLE = "servicetitan"
LINKEDIN_HANDLE = "servicetitan"
MAX_POSTS = 5


def _line(title: str) -> None:
    print("\n" + "─" * 70)
    print(title)
    print("─" * 70)


async def _try(label: str, coro):
    """Run a scrape call and print either a sample result or the full error."""
    _line(label)
    try:
        results = await coro
        print(f"✅ SUCCESS — {len(results)} item(s) returned.")
        if results:
            print("First item (truncated):")
            print(json.dumps(results[0], indent=2, ensure_ascii=False)[:800])
    except httpx.HTTPStatusError as exc:
        print(f"❌ HTTP {exc.response.status_code} from Apify")
        print("Request URL:", exc.request.url)
        print("Response body:")
        print(exc.response.text[:2000])
    except Exception as exc:  # noqa: BLE001 — we want to see everything
        print(f"❌ {type(exc).__name__}: {exc}")
        traceback.print_exc()


async def main() -> None:
    settings = get_settings()
    apify_key = settings.bootstrap_apify_key

    _line("ENV CHECK")
    if not apify_key:
        print("❌ BOOTSTRAP_APIFY_KEY is empty. Check backend/.env")
        return
    print(f"✅ Apify key loaded (starts with: {apify_key[:10]}..., length: {len(apify_key)})")

    client = ApifyClient(api_key=apify_key)
    try:
        await _try(
            f"INSTAGRAM — @{INSTAGRAM_HANDLE} (actor: apify~instagram-scraper)",
            client.scrape_instagram_posts(INSTAGRAM_HANDLE, MAX_POSTS),
        )
        await _try(
            f"LINKEDIN — {LINKEDIN_HANDLE} (actor: supreme_coder~linkedin-post)",
            client.scrape_linkedin_posts(LINKEDIN_HANDLE, MAX_POSTS),
        )
    finally:
        await client.close()

    _line("DONE")
    print("Copy everything above and paste it back to continue.")


if __name__ == "__main__":
    asyncio.run(main())