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
    "image_provider": {
        "label": "Image provider",
        "description": "Which image-generation backend the visual step uses. When a solution has reference images, the model runs reference-conditioned edits against them. Add references on each solution's page.",
        "secret": False,
        "choices": ["openai"],
    },
    "image_api_key": {
        "label": "Image API key",
        "description": "Key for the selected image provider (e.g. your OpenAI API key).",
        "secret": True,
        "choices": None,
    },
    "image_model": {
        "label": "Image model",
        "description": "Populated live from your image API key once it is saved, so you only see models the key can actually use. gpt-image-2.5-sunburst is the sharpest for photoreal scenes and on-image text (recommended); -flare is faster and cheaper; gpt-image-2 and older render text less reliably. Save the key first, then reload this page to refresh the list.",
        "secret": False,
        "choices": [
            "gpt-image-2.5-sunburst",
            "gpt-image-2.5-flare",
            "gpt-image-2",
            "gpt-image-1.5",
            "gpt-image-1",
        ],
    },
    "image_candidates": {
        "label": "Image candidates",
        "description": "How many candidate visuals to generate per post (1-4). More candidates give more choice but cost more and take longer. Default 2.",
        "secret": False,
        "choices": ["1", "2", "3", "4"],
    },
    "image_quality": {
        "label": "Image quality",
        "description": "Render quality. Higher is sharper but slower and more expensive. high is the sweet spot for social; xhigh/max only pay off on large sizes.",
        "secret": False,
        "choices": ["low", "medium", "high", "xhigh", "max", "auto"],
    },
    "image_size": {
        "label": "Image size",
        "description": "Output size / aspect. 1024x1024 square (feed), 1088x1360 portrait 4:5 (best Instagram reach), 1024x1536 tall portrait, 1536x1024 landscape (LinkedIn), or auto.",
        "secret": False,
        "choices": ["1024x1024", "1088x1360", "1024x1536", "1536x1024", "auto"],
    },
    "image_fidelity": {
        "label": "Reference fidelity",
        "description": "How tightly the model must hold to the uploaded reference images. high keeps their layout, palette and logo treatment; low lets the model reinterpret them. Not every model accepts this — when one rejects it, the request is retried without it automatically. Default high.",
        "secret": False,
        "choices": ["high", "low"],
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
