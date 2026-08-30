"""
integrations/image_gen.py
Pluggable image-generation layer for Phase 4 branded visuals. The active provider
+ key come from the in-app Settings page, so we are never locked to one vendor.

Providers return raw PNG bytes. OpenAI (gpt-image-1) is the first provider. The
brand pill / logo / exact headline text are composited on top of the scene in
Phase 4 (image models render text unreliably), so prompts ask for a clean,
text-free scene with negative space reserved for the overlay.
"""

from __future__ import annotations

import base64
import logging

import httpx

logger = logging.getLogger(__name__)

IMAGE_PROVIDERS = ["openai", "gemini"]


class ImageGenError(RuntimeError):
    """Raised when image generation fails (surfaced to the review UI)."""


async def _openai(prompt: str, api_key: str, size: str) -> bytes:
    async with httpx.AsyncClient(timeout=120) as c:
        resp = await c.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": "gpt-image-1", "prompt": prompt, "size": size, "n": 1},
        )
    if resp.status_code >= 400:
        raise ImageGenError(f"OpenAI image API {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    items = data.get("data") or []
    b64 = items[0].get("b64_json") if items else None
    if not b64:
        raise ImageGenError("OpenAI returned no image data.")
    return base64.b64decode(b64)


async def generate_image(
    provider: str, prompt: str, api_key: str, size: str = "1024x1024"
) -> bytes:
    """Generate one image and return raw PNG bytes. Raises ImageGenError on any failure."""
    if not api_key:
        raise ImageGenError("No image API key configured. Set one on the Settings page.")
    p = (provider or "openai").lower()
    if p == "openai":
        return await _openai(prompt, api_key, size)
    raise ImageGenError(f"Image provider '{provider}' is not supported yet.")
