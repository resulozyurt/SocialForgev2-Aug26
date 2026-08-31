"""
phases/phase4_visual.py
Phase 4 — reference-conditioned branded visual generation (V4b).

For an APPROVED ContentPackage: load the (brand, solution) reference library plus
the solution's visual note, brand identity, and the post's copy, then ask the image
model (gpt-image-1 edits, multi-reference) for N candidate drafts. The references
carry the brand's proven style so a new post looks on-brand; the human picks one and
finishes it in Canva. When a solution has no references yet, we fall back to a
text-only generation so the step still works.
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from core.database import get_db_context
from core.settings_store import get_app_setting
from integrations.image_gen import ImageGenError, generate_candidates
from models.db_models import (
    Brand,
    BrandSolution,
    ContentPackage,
    ContentStatusEnum,
    SolutionReferenceImage,
)

logger = logging.getLogger(__name__)

_SIZE = "1024x1024"
_DEFAULT_CANDIDATES = 2
_DEFAULT_QUALITY = "medium"


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
    pill = vi.get("pill") if isinstance(vi.get("pill"), dict) else {}
    if pill.get("bg_color"):
        parts.append(f"accent-pill color {pill.get('bg_color')}")
    return " | ".join(parts) if parts else "clean, modern, on-brand"


def _headline_text(package, brand) -> tuple[str, str]:
    """Return (primary, secondary) on-visual text in the brand's language."""
    vd = package.visual_direction if isinstance(package.visual_direction, dict) else {}
    overlay = vd.get("text_overlay") if isinstance(vd.get("text_overlay"), dict) else {}
    primary = str(overlay.get("primary") or "").strip()
    secondary = str(overlay.get("secondary") or "").strip()
    if primary:
        return primary, secondary

    # Fall back to the copy package headline in the brand's language.
    lang = getattr(getattr(brand, "language", None), "value", None)
    copy = (
        package.copy_package_tr
        if str(lang).lower() == "tr" and isinstance(package.copy_package_tr, dict)
        else package.copy_package_en
    )
    if isinstance(copy, dict):
        primary = str(copy.get("headline") or copy.get("hook") or "").strip()
        secondary = str(copy.get("subhead") or copy.get("subheadline") or "").strip()
    return primary, secondary


def _scene_prompt(package, brand, solution_notes: str, has_refs: bool) -> str:
    vd = package.visual_direction if isinstance(package.visual_direction, dict) else {}
    concept = (
        vd.get("image_prompt")
        or vd.get("concept")
        or "a clean, modern brand visual for a social post"
    )
    mood = vd.get("mood") or "clean and confident"
    comp = vd.get("composition") or "clear focal subject with generous negative space"
    primary, secondary = _headline_text(package, brand)
    sol = getattr(getattr(package, "solution", None), "value", None) or "general"

    lines: list[str] = []
    lines.append(
        f"Create a professional social-media post visual for the brand "
        f"\"{brand.display_name}\" in its \"{sol}\" solution area."
    )
    lines.append(f"Concept: {concept}")
    lines.append(f"Mood: {mood}. Composition: {comp}.")
    lines.append(f"Brand visual language: {_brand_style(brand)}.")
    if solution_notes:
        lines.append(f"Solution art direction: {solution_notes}")
    if primary:
        txt = f'Headline to place on the visual: "{primary}"'
        if secondary:
            txt += f' — supporting line: "{secondary}"'
        lines.append(
            txt
            + ". Render this exact wording legibly, following the reference layout, "
            "in the brand's accent-pill and heading style."
        )
    if has_refs:
        lines.append(
            "Match the visual style, layout, color system, typography feel, and "
            "branding of the provided reference images as closely as possible — treat "
            "them as the brand template. Produce a NEW composition for the concept "
            "above, do not copy any single reference verbatim."
        )
    else:
        lines.append(
            "No reference images are available; render a clean, on-brand scene with "
            "professional social-media quality."
        )
    lines.append("Sharp, uncluttered, high-quality. Avoid stock-photo clichés and gibberish text.")
    return "\n".join(lines)


class Phase4Visual:
    """Generates N candidate branded visuals for an approved content package."""

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
            if not brand:
                raise ImageGenError("Brand not found for this package.")

            solution = getattr(package, "solution", None)

            # Reference library for this (brand, solution).
            references: list[bytes] = []
            solution_notes = ""
            if solution is not None:
                ref_res = await db.execute(
                    select(SolutionReferenceImage)
                    .where(
                        SolutionReferenceImage.brand_id == package.brand_id,
                        SolutionReferenceImage.solution == solution,
                    )
                    .order_by(
                        SolutionReferenceImage.sort_order,
                        SolutionReferenceImage.created_at,
                    )
                )
                references = [r.image_data for r in ref_res.scalars().all() if r.image_data]

                note_res = await db.execute(
                    select(BrandSolution).where(
                        BrandSolution.brand_id == package.brand_id,
                        BrandSolution.solution == solution,
                    )
                )
                sol_row = note_res.scalar_one_or_none()
                solution_notes = (getattr(sol_row, "visual_notes", None) or "").strip()

            provider = (await get_app_setting("image_provider")) or "openai"
            api_key = await get_app_setting("image_api_key")
            try:
                n = int((await get_app_setting("image_candidates")) or _DEFAULT_CANDIDATES)
            except (TypeError, ValueError):
                n = _DEFAULT_CANDIDATES
            quality = (await get_app_setting("image_quality")) or _DEFAULT_QUALITY

            has_refs = len(references) > 0
            prompt = _scene_prompt(package, brand, solution_notes, has_refs)

            image_list = await generate_candidates(
                provider,
                prompt,
                api_key,
                references=references,
                n=n,
                size=_SIZE,
                quality=quality,
            )

            candidates = []
            for img in image_list:
                data_uri = "data:image/png;base64," + base64.b64encode(img).decode()
                candidates.append({"id": uuid.uuid4().hex, "image": data_uri})

            vd = package.visual_direction if isinstance(package.visual_direction, dict) else {}
            overlay = vd.get("text_overlay")

            assets = dict(package.asset_urls or {})
            assets.update(
                {
                    # Backward-compat single field (current Stage-4 UI reads this);
                    # the V5 gallery reads `candidates`.
                    "image": candidates[0]["image"] if candidates else None,
                    "candidates": candidates,
                    "selected_id": None,
                    "provider": provider,
                    "scene_prompt": prompt,
                    "text_overlay": overlay,
                    "used_references": has_refs,
                    "reference_count": len(references),
                    "visual_status": "draft",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            package.asset_urls = assets
            await db.flush()
            logger.info(
                "Phase 4 generated %d candidate(s) for package %s (refs=%d, provider=%s)",
                len(candidates),
                package_id,
                len(references),
                provider,
            )
            return {"visual_status": "draft", "candidates": len(candidates), "used_references": has_refs}
