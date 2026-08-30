"""
phases/phase4_visual.py
Phase 4 — branded visual generation from an APPROVED ContentPackage.

D1: generate a clean, text-free scene from the package's visual_direction plus the
brand's visual identity, and store it on the package for human review. The brand
pill / logo / exact headline overlay is Phase D2; Google Drive upload is D3.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from core.database import get_db_context
from core.settings_store import get_app_setting
from integrations.image_gen import ImageGenError, generate_image
from models.db_models import Brand, ContentPackage, ContentStatusEnum

logger = logging.getLogger(__name__)

_SIZE = "1024x1024"


def _brand_style(brand) -> str:
    vi = getattr(brand, "visual_identity", None) or {}
    parts: list[str] = []
    styles = vi.get("style_keywords")
    if isinstance(styles, list) and styles:
        parts.append("style: " + ", ".join(str(s) for s in styles))
    motifs = vi.get("motifs")
    if isinstance(motifs, list) and motifs:
        parts.append("motifs: " + "; ".join(str(m) for m in motifs))
    ground = vi.get("ground_color")
    if ground:
        parts.append(f"background tone {ground}")
    return " | ".join(parts) if parts else "clean, modern, on-brand"


def _scene_prompt(package, brand) -> str:
    vd = package.visual_direction or {}
    base = vd.get("image_prompt") or vd.get("concept") or "a clean, modern brand visual for a social post"
    mood = vd.get("mood") or "clean and confident"
    comp = vd.get("composition") or "clear focal subject with generous negative space"
    return (
        f"{base}\n\n"
        f"Mood: {mood}. Composition: {comp}. Brand visual language: {_brand_style(brand)}.\n"
        "IMPORTANT: Do NOT render any text, letters, words, numbers, logos, watermarks, or UI "
        "in the image. Leave clean, uncluttered negative space (upper-left and lower area) where "
        "a headline and logo will be overlaid later. Professional social-media quality; "
        "photorealistic or clean 3D as appropriate; sharp and uncluttered."
    )


class Phase4Visual:
    """Generates a branded visual for an approved content package."""

    async def run(self, package_id: str) -> dict:
        async with get_db_context() as db:
            pkg_res = await db.execute(
                select(ContentPackage).where(ContentPackage.id == package_id)
            )
            package = pkg_res.scalar_one_or_none()
            if not package:
                raise ImageGenError(f"Content package {package_id} not found.")
            if package.status != ContentStatusEnum.APPROVED:
                raise ImageGenError("Approve the copy for this post before generating its visual.")

            brand_res = await db.execute(select(Brand).where(Brand.id == package.brand_id))
            brand = brand_res.scalar_one_or_none()

            provider = (await get_app_setting("image_provider")) or "openai"
            api_key = await get_app_setting("image_api_key")

            prompt = _scene_prompt(package, brand)
            image_bytes = await generate_image(provider, prompt, api_key, size=_SIZE)
            data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()

            vd = package.visual_direction if isinstance(package.visual_direction, dict) else {}
            overlay = vd.get("text_overlay")

            assets = dict(package.asset_urls or {})
            assets.update(
                {
                    "image": data_uri,
                    "provider": provider,
                    "scene_prompt": prompt,
                    "text_overlay": overlay,
                    "visual_status": "draft",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            package.asset_urls = assets
            await db.flush()
            logger.info("Phase 4 visual generated for package %s", package_id)
            return {"visual_status": "draft"}
