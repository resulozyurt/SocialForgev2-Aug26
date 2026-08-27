"""
core/settings_store.py
Platform-level settings store (Brave / Apify keys, etc.) managed from the in-app
Settings page. Secret values are Fernet-encrypted at rest.
"""

from __future__ import annotations

from typing import Optional

from core.config import get_encryption_manager
from core.database import get_db_context
from models.db_models import AppSetting

# The settings the UI exposes. Extend as new integrations are added.
KNOWN_SETTINGS: dict[str, dict] = {
    "search_provider": {
        "label": "Search provider",
        "description": "Which web-search backend research uses. Free-friendly: serper (Google SERP, free credits) or google_cse (100/day free). Swap anytime.",
        "secret": False,
        "choices": ["serper", "brave", "google_cse", "tavily"],
    },
    "search_api_key": {
        "label": "Search API key",
        "description": "Key for the selected search provider. For Google CSE use the form APIKEY:SEARCHENGINEID.",
        "secret": True,
        "choices": None,
    },
    "apify_api_key": {
        "label": "Apify API token",
        "description": "Optional. Enables competitor social-media scraping when a brand turns it on.",
        "secret": True,
        "choices": None,
    },
}


async def get_app_setting(key: str) -> Optional[str]:
    async with get_db_context() as db:
        row = await db.get(AppSetting, key)
        if not row:
            return None
        try:
            return get_encryption_manager().decrypt(row.value_enc)
        except Exception:
            return None


async def set_app_setting(key: str, value: str) -> None:
    enc = get_encryption_manager().encrypt(value)
    async with get_db_context() as db:
        row = await db.get(AppSetting, key)
        if row:
            row.value_enc = enc
        else:
            db.add(AppSetting(key=key, value_enc=enc))


async def delete_app_setting(key: str) -> None:
    async with get_db_context() as db:
        row = await db.get(AppSetting, key)
        if row:
            await db.delete(row)
