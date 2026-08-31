"""
integrations/image_gen.py
Pluggable image-generation layer for the redesigned Phase-4 visual step.

The active provider + key come from the in-app Settings page, so we are never
locked to one vendor. OpenAI `gpt-image-1` is the first provider and supports two
paths:

  * edits  — reference-conditioned: the (brand, solution) reference library is sent
    alongside the prompt so a new post inherits the brand's proven style. This is
    the primary path (mirrors the owner's manual ChatGPT workflow).
  * generate — text-only fallback used when a solution has no references yet.

Both return a list of raw PNG bytes (one per candidate). The human picks one and
finishes it in Canva.
"""

from __future__ import annotations

import base64
import logging

import httpx

logger = logging.getLogger(__name__)

IMAGE_PROVIDERS = ["openai", "gemini"]

_OPENAI_GENERATE_URL = "https://api.openai.com/v1/images/generations"
_OPENAI_EDITS_URL = "https://api.openai.com/v1/images/edits"
_OPENAI_MODEL = "gpt-image-1"
_TIMEOUT = 240  # edits with several references + multiple candidates is slow


class ImageGenError(RuntimeError):
    """Raised when image generation fails (surfaced to the review UI)."""


def _decode_items(data: dict) -> list[bytes]:
    items = data.get("data") or []
    out: list[bytes] = []
    for it in items:
        b64 = it.get("b64_json")
        if b64:
            out.append(base64.b64decode(b64))
    if not out:
        raise ImageGenError("Image API returned no image data.")
    return out


async def _openai_generate(
    prompt: str, api_key: str, size: str, n: int, quality: str
) -> list[bytes]:
    payload = {
        "model": _OPENAI_MODEL,
        "prompt": prompt,
        "size": size,
        "n": n,
    }
    if quality:
        payload["quality"] = quality
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        resp = await c.post(
            _OPENAI_GENERATE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        raise ImageGenError(f"OpenAI image API {resp.status_code}: {resp.text[:400]}")
    return _decode_items(resp.json())


async def _openai_edits(
    prompt: str,
    api_key: str,
    size: str,
    n: int,
    quality: str,
    references: list[bytes],
) -> list[bytes]:
    # gpt-image-1 accepts multiple reference images under the repeated "image[]"
    # multipart field. Reference bytes are already downscaled JPEGs (V2 upload).
    files = [
        ("image[]", (f"ref_{i}.jpg", raw, "image/jpeg"))
        for i, raw in enumerate(references)
    ]
    data = {
        "model": _OPENAI_MODEL,
        "prompt": prompt,
        "size": size,
        "n": str(n),
    }
    if quality:
        data["quality"] = quality
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        resp = await c.post(
            _OPENAI_EDITS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=files,
        )
    if resp.status_code >= 400:
        raise ImageGenError(f"OpenAI image edits API {resp.status_code}: {resp.text[:400]}")
    return _decode_items(resp.json())


async def generate_candidates(
    provider: str,
    prompt: str,
    api_key: str,
    references: list[bytes] | None = None,
    n: int = 2,
    size: str = "1024x1024",
    quality: str = "medium",
) -> list[bytes]:
    """Generate N candidate images. Uses the reference-conditioned edits path when
    references are provided, else falls back to text-only generation. Returns a list
    of raw PNG bytes. Raises ImageGenError on any failure."""
    if not api_key:
        raise ImageGenError("No image API key configured. Set one on the Settings page.")
    n = max(1, min(int(n or 1), 4))
    refs = references or []
    p = (provider or "openai").lower()
    if p == "openai":
        if refs:
            return await _openai_edits(prompt, api_key, size, n, quality, refs)
        return await _openai_generate(prompt, api_key, size, n, quality)
    raise ImageGenError(f"Image provider '{provider}' is not supported yet.")


# Back-compat single-image helper (text-only). Prefer generate_candidates.
async def generate_image(
    provider: str, prompt: str, api_key: str, size: str = "1024x1024"
) -> bytes:
    imgs = await generate_candidates(
        provider, prompt, api_key, references=None, n=1, size=size
    )
    return imgs[0]
