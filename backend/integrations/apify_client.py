"""
integrations/apify_client.py
Apify scraper client for competitor social media data collection.
Supports Instagram and LinkedIn feed scraping.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import httpx

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"

# Apify actor IDs for each platform
ACTORS = {
    "instagram_profile": "apify~instagram-profile-scraper",
    "instagram_posts":   "apify~instagram-scraper",
    "linkedin_posts":    "supreme_coder~linkedin-post",
}


class ApifyClient:
    """
    Thin async wrapper around the Apify API.
    Runs actors and waits for results synchronously (polling).
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=120)

    async def _run_actor(self, actor_id: str, input_data: dict) -> list[dict]:
        """
        Start an Apify actor run and wait for it to finish.
        Returns the dataset items on success.
        """
        run_url = f"{APIFY_BASE_URL}/acts/{actor_id}/runs"
        headers = {"Authorization": f"Bearer {self._api_key}"}

        response = await self._client.post(
            run_url,
            json={"input": input_data},
            headers=headers,
        )
        response.raise_for_status()
        run_data = response.json()
        run_id = run_data["data"]["id"]

        logger.info(f"Apify actor started: {actor_id}, run_id: {run_id}")

        import asyncio
        for _ in range(60):  # max 5 minutes
            await asyncio.sleep(5)
            status_response = await self._client.get(
                f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                headers=headers,
            )
            status_response.raise_for_status()
            status = status_response.json()["data"]["status"]

            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify run {run_id} ended with status: {status}")

        dataset_id = status_response.json()["data"]["defaultDatasetId"]
        items_response = await self._client.get(
            f"{APIFY_BASE_URL}/datasets/{dataset_id}/items",
            headers=headers,
            params={"limit": 100},
        )
        items_response.raise_for_status()
        return items_response.json()

    async def scrape_instagram_posts(
        self,
        username: str,
        max_posts: int = 30,
    ) -> list[dict]:
        """
        Scrape recent posts from an Instagram profile.
        Returns a list of post objects with likes, comments, caption, etc.
        """
        logger.info(f"Scraping Instagram posts for @{username}")
        results = await self._run_actor(
            ACTORS["instagram_posts"],
            {
                "directUrls": [f"https://www.instagram.com/{username}/"],
                "resultsType": "posts",
                "resultsLimit": max_posts,
            },
        )
        return results

    async def scrape_linkedin_posts(
        self,
        company_handle: str,
        max_posts: int = 30,
    ) -> list[dict]:
        """
        Scrape recent posts from a LinkedIn company page.
        """
        logger.info(f"Scraping LinkedIn posts for {company_handle}")
        results = await self._run_actor(
            ACTORS["linkedin_posts"],
            {
                "urls": [f"https://www.linkedin.com/company/{company_handle}/"],
                "limitPerSource": max_posts,
                "deepScrape": True,
            },
        )
        return results

    async def close(self) -> None:
        await self._client.aclose()