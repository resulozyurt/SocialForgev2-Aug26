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
import json
import logging

import httpx

logger = logging.getLogger(__name__)

IMAGE_PROVIDERS = ["openai", "gemini"]

_OPENAI_GENERATE_URL = "https://api.openai.com/v1/images/generations"
_OPENAI_EDITS_URL = "https://api.openai.com/v1/images/edits"
_OPENAI_MODELS_URL = "https://api.openai.com/v1/models"

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


# Optional request parameters that not every model generation accepts. When the API
# rejects one of these, we drop it and retry rather than failing the whole run —
# model capabilities move faster than this file does. (For example
# gpt-image-2.5-sunburst rejects `input_fidelity`, which gpt-image-1 requires to
# hold reference detail.)
_DROPPABLE_PARAMS = ("input_fidelity", "quality", "background", "output_format", "size")

_MAX_PARAM_RETRIES = 3


def _error_body(resp: httpx.Response) -> str:
    try:
        return resp.text or ""
    except Exception:  # noqa: BLE001 — never let error handling raise
        return ""


def _rejected_param(status_code: int, body: str) -> str | None:
    """Return the name of the optional parameter the API rejected, if any."""
    if status_code != 400:
        return None
    param = None
    try:
        param = ((json.loads(body) or {}).get("error") or {}).get("param")
    except Exception:  # noqa: BLE001 — non-JSON error body
        param = None
    if param in _DROPPABLE_PARAMS:
        return param
    lowered = (body or "").lower()
    for candidate in _DROPPABLE_PARAMS:
        if f"'{candidate}'" in lowered and (
            "does not support" in lowered
            or "unsupported" in lowered
            or "unknown parameter" in lowered
            or "not supported" in lowered
        ):
            return candidate
    return None


def _is_unsupported_n(status_code: int, body: str) -> bool:
    """True when the API refused the request specifically because of `n`."""
    if status_code != 400:
        return False
    try:
        if ((json.loads(body) or {}).get("error") or {}).get("param") == "n":
            return True
    except Exception:  # noqa: BLE001
        pass
    lowered = (body or "").lower()
    return "'n'" in lowered or '"n"' in lowered or "parameter: n" in lowered


async def list_openai_image_models(api_key: str) -> list[str]:
    """List the image models this API key is actually allowed to use.

    The Settings page uses this so the owner picks from what their key can reach
    instead of from a list this file guessed. Falls back to the curated list on
    any failure (the caller decides how to surface that)."""
    if not api_key:
        raise ImageGenError("No image API key configured.")
    async with httpx.AsyncClient(timeout=20) as c:
        resp = await c.get(
            _OPENAI_MODELS_URL, headers={"Authorization": f"Bearer {api_key}"}
        )
    if resp.status_code >= 400:
        raise ImageGenError(
            f"OpenAI models API {resp.status_code}: {_error_body(resp)[:200]}"
        )
    ids = [
        str(m.get("id") or "")
        for m in (resp.json().get("data") or [])
        if isinstance(m, dict)
    ]
    images = [
        i for i in ids if i.startswith("gpt-image") or i.startswith("dall-e")
    ]
    if not images:
        return []

    def rank(model_id: str) -> tuple[int, int, str]:
        # Known models first, in our curated order; then everything else.
        # Dated snapshots (…-2026-04-21) sort below their rolling alias.
        known = (
            OPENAI_IMAGE_MODELS.index(model_id)
            if model_id in OPENAI_IMAGE_MODELS
            else len(OPENAI_IMAGE_MODELS)
        )
        dated = 1 if any(ch.isdigit() for ch in model_id.split("-")[-1]) and len(
            model_id.split("-")[-1]
        ) == 2 else 0
        return (known, dated, model_id)

    return sorted(dict.fromkeys(images), key=rank)


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
    dropped: set[str] = set()

    async def _call(count: int = 1) -> httpx.Response:
        payload: dict = {"model": model, "prompt": prompt, "n": count}
        if size and "size" not in dropped:
            payload["size"] = size
        if quality and "quality" not in dropped:
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

    for _ in range(_MAX_PARAM_RETRIES):
        resp = await _call(n)
        if resp.status_code < 400:
            return _decode_items(resp.json())
        body = _error_body(resp)
        bad = _rejected_param(resp.status_code, body)
        if bad and bad not in dropped:
            dropped.add(bad)
            logger.info("Model %s rejected '%s'; retrying without it.", model, bad)
            continue
        if n > 1 and _is_unsupported_n(resp.status_code, body):
            logger.info("Model %s rejected n=%d; falling back to parallel calls.", model, n)
            return await _parallel(_call, n, model)
        raise ImageGenError(f"OpenAI image API {resp.status_code}: {body[:400]}")
    raise ImageGenError(
        f"OpenAI image API kept rejecting parameters for model '{model}' "
        f"(dropped: {', '.join(sorted(dropped)) or 'none'})."
    )


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

    dropped: set[str] = set()

    async def _call(count: int = 1) -> httpx.Response:
        files = [
            ("image[]", (f"ref_{i}.jpg", raw, "image/jpeg"))
            for i, raw in enumerate(refs)
        ]
        data: dict = {"model": model, "prompt": prompt, "n": str(count)}
        if size and "size" not in dropped:
            data["size"] = size
        if quality and "quality" not in dropped:
            data["quality"] = quality
        if input_fidelity and "input_fidelity" not in dropped:
            data["input_fidelity"] = input_fidelity
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            return await c.post(
                _OPENAI_EDITS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            )

    for _ in range(_MAX_PARAM_RETRIES):
        resp = await _call(n)
        if resp.status_code < 400:
            return _decode_items(resp.json())
        body = _error_body(resp)
        bad = _rejected_param(resp.status_code, body)
        if bad and bad not in dropped:
            dropped.add(bad)
            logger.info(
                "Model %s rejected '%s' on edits; retrying without it.", model, bad
            )
            continue
        if n > 1 and _is_unsupported_n(resp.status_code, body):
            logger.info(
                "Model %s rejected n=%d on edits; falling back to parallel calls.", model, n
            )
            return await _parallel(_call, n, model)
        raise ImageGenError(f"OpenAI image edits API {resp.status_code}: {body[:400]}")
    raise ImageGenError(
        f"OpenAI image edits API kept rejecting parameters for model '{model}' "
        f"(dropped: {', '.join(sorted(dropped)) or 'none'})."
    )


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
