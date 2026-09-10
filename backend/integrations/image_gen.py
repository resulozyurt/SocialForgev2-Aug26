"""
integrations/image_gen.py
Pluggable image-generation layer for the Phase-4 visual step.

The active provider, model and key come from the in-app Settings page, so we are
never locked to one vendor or one model generation. OpenAI is the first provider
and supports two paths:

  * edits  — reference-conditioned: the (brand, solution) reference library is sent
    alongside the prompt so a new post inherits the brand's proven design system.
    This is the primary path (it mirrors the owner's manual ChatGPT workflow).
  * generate — text-only fallback used when a solution has no references yet.

Both return a list of raw PNG bytes (one per candidate). The human picks one.

V7 notes:
  * The model is configurable. Newer GPT image models (gpt-image-2.5-*) render
    text far more reliably and are markedly more photorealistic than gpt-image-1,
    which is why the default moved up.
  * `input_fidelity=high` tells the model to hold on to the detail of the input
    reference images instead of loosely paraphrasing them.
  * The edits endpoint accepts at most 16 reference images; we trim to that.
  * Some model/endpoint combinations reject `n > 1`. When that happens we fall
    back to N parallel single-image calls so the candidate count still works.
"""

from __future__ import annotations

import asyncio
import base64
import logging

import httpx

logger = logging.getLogger(__name__)

IMAGE_PROVIDERS = ["openai", "gemini"]

_OPENAI_GENERATE_URL = "https://api.openai.com/v1/images/generations"
_OPENAI_EDITS_URL = "https://api.openai.com/v1/images/edits"

# Newest first. The first entry is the default when no model is configured.
OPENAI_IMAGE_MODELS = [
    "gpt-image-2.5-sunburst",
    "gpt-image-2.5-flare",
    "gpt-image-2",
    "gpt-image-1.5",
    "gpt-image-1",
]
DEFAULT_OPENAI_IMAGE_MODEL = OPENAI_IMAGE_MODELS[0]

# The edits endpoint caps reference images at 16 for GPT image models.
MAX_REFERENCE_IMAGES = 16

_TIMEOUT = 300  # high-quality edits with several references are slow


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


def _is_unsupported_n(status_code: int, body: str) -> bool:
    """True when the API refused the request specifically because of `n`."""
    if status_code != 400:
        return False
    lowered = (body or "").lower()
    return "'n'" in lowered or '"n"' in lowered or "parameter: n" in lowered


async def _parallel(make_call, n: int, model: str) -> list[bytes]:
    """Run N single-image calls concurrently. Succeeds if at least one returns."""
    results = await asyncio.gather(
        *[make_call() for _ in range(n)], return_exceptions=True
    )
    images: list[bytes] = []
    last_error = ""
    for r in results:
        if isinstance(r, BaseException):
            last_error = str(r)
            continue
        if r.status_code >= 400:
            last_error = f"{r.status_code}: {r.text[:200]}"
            continue
        try:
            images.extend(_decode_items(r.json()))
        except ImageGenError as exc:
            last_error = str(exc)
    if not images:
        raise ImageGenError(
            f"OpenAI image API ({model}) returned no images. {last_error}"
        )
    return images


async def _openai_generate(
    prompt: str, api_key: str, model: str, size: str, n: int, quality: str
) -> list[bytes]:
    async def _call(count: int = 1) -> httpx.Response:
        payload: dict = {"model": model, "prompt": prompt, "size": size, "n": count}
        if quality:
            payload["quality"] = quality
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            return await c.post(
                _OPENAI_GENERATE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

    resp = await _call(n)
    if resp.status_code >= 400:
        if n > 1 and _is_unsupported_n(resp.status_code, resp.text):
            logger.info("Model %s rejected n=%d; falling back to parallel calls.", model, n)
            return await _parallel(_call, n, model)
        raise ImageGenError(f"OpenAI image API {resp.status_code}: {resp.text[:400]}")
    return _decode_items(resp.json())


async def _openai_edits(
    prompt: str,
    api_key: str,
    model: str,
    size: str,
    n: int,
    quality: str,
    references: list[bytes],
    input_fidelity: str,
) -> list[bytes]:
    # GPT image models accept multiple reference images under the repeated
    # "image[]" multipart field (max 16). Reference bytes are already downscaled
    # JPEGs (see the V2 reference upload route).
    refs = references[:MAX_REFERENCE_IMAGES]
    if len(references) > MAX_REFERENCE_IMAGES:
        logger.warning(
            "Trimmed %d reference images down to the API limit of %d.",
            len(references),
            MAX_REFERENCE_IMAGES,
        )

    async def _call(count: int = 1) -> httpx.Response:
        files = [
            ("image[]", (f"ref_{i}.jpg", raw, "image/jpeg"))
            for i, raw in enumerate(refs)
        ]
        data: dict = {"model": model, "prompt": prompt, "size": size, "n": str(count)}
        if quality:
            data["quality"] = quality
        if input_fidelity:
            data["input_fidelity"] = input_fidelity
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            return await c.post(
                _OPENAI_EDITS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            )

    resp = await _call(n)
    if resp.status_code >= 400:
        if n > 1 and _is_unsupported_n(resp.status_code, resp.text):
            logger.info(
                "Model %s rejected n=%d on edits; falling back to parallel calls.", model, n
            )
            return await _parallel(_call, n, model)
        raise ImageGenError(
            f"OpenAI image edits API {resp.status_code}: {resp.text[:400]}"
        )
    return _decode_items(resp.json())


async def generate_candidates(
    provider: str,
    prompt: str,
    api_key: str,
    references: list[bytes] | None = None,
    n: int = 2,
    size: str = "1024x1024",
    quality: str = "high",
    model: str | None = None,
    input_fidelity: str = "high",
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
        chosen = (model or "").strip() or DEFAULT_OPENAI_IMAGE_MODEL
        if refs:
            return await _openai_edits(
                prompt, api_key, chosen, size, n, quality, refs, input_fidelity
            )
        return await _openai_generate(prompt, api_key, chosen, size, n, quality)
    raise ImageGenError(f"Image provider '{provider}' is not supported yet.")


# Back-compat single-image helper (text-only). Prefer generate_candidates.
async def generate_image(
    provider: str, prompt: str, api_key: str, size: str = "1024x1024"
) -> bytes:
    imgs = await generate_candidates(
        provider, prompt, api_key, references=None, n=1, size=size
    )
    return imgs[0]
