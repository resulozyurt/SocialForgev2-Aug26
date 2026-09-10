"""
phases/phase4_visual.py
Phase 4 — reference-conditioned branded visual generation.

For an APPROVED ContentPackage: load the (brand, solution) reference library plus
the solution's visual note, brand identity, and the post's copy, then ask the image
model for N candidate drafts. The references carry the brand's proven design system
so a new post looks on-brand; the human picks one.

V7 prompt redesign. The old prompt mixed brand motifs, mood, composition, art
direction and a reference instruction all at the same weight, so the model averaged
them into a generic, flat scene and ignored the references. The prompt is now three
explicit layers with a clear authority order:

  1. BRAND TEMPLATE  — the reference images are the single source of truth for the
     design system (layout, type, palette, logo lock-up, motif placement).
  2. THIS POST       — what this specific visual has to say, plus the exact on-image
     text. Nothing else may be rendered as words.
  3. QUALITY BAR     — a fixed, non-negotiable premium-B2B-SaaS + photoreal block
     with an explicit negative list.

When a solution has no references we fall back to a text-only generation that leans
on the brand's own visual identity instead, so the step still works.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from core.database import get_db_context
from core.settings_store import get_app_setting
from integrations.image_gen import (
    DEFAULT_OPENAI_IMAGE_MODEL,
    MAX_REFERENCE_IMAGES,
    ImageGenError,
    generate_candidates,
)
from models.db_models import (
    Brand,
    BrandSolution,
    ContentPackage,
    ContentStatusEnum,
    SolutionReferenceImage,
    VisualGeneration,
)

logger = logging.getLogger(__name__)

_DEFAULT_SIZE = "1024x1024"
_DEFAULT_CANDIDATES = 2
_DEFAULT_QUALITY = "high"
_DEFAULT_FIDELITY = "high"

_SOLUTION_LABELS = {
    "merchandising": "retail merchandising / shelf execution",
    "field_audit": "field & store audit",
    "field_sales": "field sales",
    "home_service": "home service / field service",
    "ai": "AI in field operations",
    "general": "field operations",
}

# Default scene family per solution, used when a solution has no `visual_notes` yet.
# This exists because the copy step's `image_prompt` kept defaulting every solution
# to a supermarket aisle: field audit in particular happens across many industries,
# and the visual should reflect that instead of collapsing to retail shelves.
# An owner-written `visual_notes` always wins over these defaults.
_SOLUTION_SCENES = {
    "merchandising": (
        "in-store retail: shelves, aisles, displays and planograms, a merchandiser "
        "working with a tablet or phone"
    ),
    "field_audit": (
        "audits ACROSS INDUSTRIES — hotels and restaurants, construction sites, "
        "warehouses and depots, branch offices, factories and production lines, "
        "healthcare facilities, fuel stations, and retail. Pick the setting that "
        "fits this post and do NOT default to a supermarket shelf"
    ),
    "field_sales": (
        "field sales: a rep meeting a store owner or business customer face to face, "
        "a route between visits, an order or contract taken on a tablet"
    ),
    "home_service": (
        "home and field service: a technician at a customer's home or building, "
        "tools in use, an installation or repair, a branded service van"
    ),
    "ai": (
        "AI in the field: a real field worker whose device surfaces an AI insight. "
        "Keep the person and the real environment central — never an abstract "
        "'AI brain' illustration"
    ),
    "general": "real field operations: people at work in real environments",
}

# Layer 3 — fixed for every brand and every post. This is the bar the owner
# judges the output against: premium B2B SaaS marketing, real photography, real
# depth. Keep it short and absolute; a long list dilutes it.
_QUALITY_BAR = """QUALITY BAR — non-negotiable:
- Premium B2B SaaS marketing quality. This has to look like it came from a funded
  company's in-house design team, not from a template or a stock library.
- PHOTOREALISTIC for anything real: real people (natural faces, real skin, real
  posture, professional wardrobe), real environments, real products, real devices,
  natural directional light, believable shadows and reflections, shallow depth of
  field on the background.
- Build depth and craft: layered composition, soft realistic drop shadows, crisp
  edges, generous breathing room. Never a flat single plane.
- Any UI or data element sits on top of the photograph as a clean, modern floating
  card with soft shadow and rounded corners — a real product interface, not a doodle.
- Typography is razor sharp, correctly kerned, and perfectly legible at thumbnail size.

DO NOT PRODUCE: 3D cartoon renders, vector or flat illustration, clip art, isometric
icon art, plastic CGI toys, obvious stock-photo poses, collage, watermarks, borders,
frames, or a busy background that fights the headline."""

# Text discipline. Invented pseudo-words on shelves, signage and UI labels are the
# single most common way an otherwise good render becomes unusable.
_TEXT_RULE = """TEXT DISCIPLINE — read this twice:
- Render ONLY the single headline given above, spelled EXACTLY as written, once.
- Add NO sub-headline, NO supporting sentence, NO descriptive line under or beside
  the headline. The headline plus the logo is the entire text of this image. A
  second line of copy makes the layout crowded and the post unusable.
- Every other surface in the scene — product labels, packaging, signage, screens, UI
  chips, badges, charts — carries NO readable words. Leave them blank, abstract,
  or intentionally out of focus.
- Never invent words, never approximate a word, never add a caption, tagline, URL,
  price, or logo text that was not specified. A misspelled word makes the image
  unusable."""


def _solution_label(package) -> str:
    key = getattr(getattr(package, "solution", None), "value", None) or "general"
    return _SOLUTION_LABELS.get(key, key.replace("_", " "))


def _brand_cues(brand) -> str:
    """Short brand reinforcement. Used as a light nudge when references exist, and
    as the full description when they don't."""
    vi = getattr(brand, "visual_identity", None) or {}
    parts: list[str] = []
    styles = vi.get("style_keywords")
    if isinstance(styles, list) and styles:
        parts.append("style: " + ", ".join(str(s) for s in styles))
    motifs = vi.get("motifs")
    if isinstance(motifs, list) and motifs:
        parts.append("recurring elements: " + "; ".join(str(m) for m in motifs))
    ground = vi.get("ground_color")
    if ground:
        parts.append(f"background {ground}")
    pill = vi.get("pill") if isinstance(vi.get("pill"), dict) else {}
    if pill.get("bg_color"):
        parts.append(f"accent pill {pill.get('bg_color')}")
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


def _scene_prompt(package, brand, solution_notes: str, ref_count: int) -> str:
    vd = package.visual_direction if isinstance(package.visual_direction, dict) else {}
    concept = str(
        vd.get("concept")
        or vd.get("image_prompt")
        or "a clean, modern brand visual for a social post"
    ).strip()
    scene = str(vd.get("image_prompt") or "").strip()
    # The support line is deliberately dropped: rendered under the headline it made
    # every layout crowded. The copy still carries it for the caption/alt text.
    primary, _support_line = _headline_text(package, brand)
    sol = _solution_label(package)
    ctype = getattr(getattr(package, "content_type", None), "value", None) or "static"

    out: list[str] = []
    out.append(
        f"You are producing a premium B2B SaaS social-media post visual for "
        f"\"{brand.display_name}\", in its {sol} solution area."
    )
    if ctype == "carousel":
        out.append(
            "This is the COVER frame of a carousel: it must stop the scroll on its "
            "own and leave the detail to the following slides."
        )

    # ── Layer 1 — the brand template ────────────────────────────────────────
    out.append("")
    if ref_count:
        out.append(
            f"LAYER 1 — BRAND TEMPLATE (authority):\n"
            f"The {ref_count} attached reference image(s) ARE this brand's template. "
            "Reproduce their design system exactly: the layout skeleton and where the "
            "text block sits, the type hierarchy and weights, the exact color palette, "
            "the logo lock-up and its corner, the accent-pill treatment on the key "
            "word, the graphic motif and its placement, the margins and the amount of "
            "white space. Where this brief and the references disagree, THE REFERENCES "
            "WIN. Compose a NEW scene inside that system — never re-stage or copy any "
            "single reference's photograph."
        )
        cues = _brand_cues(brand)
        if cues:
            out.append(f"Brand cues (reinforcement only, the references are authority): {cues}")
    else:
        out.append(
            "LAYER 1 — BRAND TEMPLATE:\n"
            "No reference images exist for this solution yet, so build the layout from "
            f"the brand's own visual identity: {_brand_cues(brand)}. Left-aligned text "
            "column, logo top-left, one accent-pill highlight, generous white space."
        )

    # ── Layer 2 — this specific post ────────────────────────────────────────
    #
    # Authority order inside this layer matters. The copy step writes
    # `image_prompt` before anyone has looked at it, and it has a strong pull
    # toward whatever setting the brand is best known for — which is how every
    # solution ended up as a supermarket aisle. So the solution's own art
    # direction (owner-written `visual_notes`, else the built-in scene family)
    # is stated FIRST and declared the winner on any conflict; the copy's scene
    # wording is demoted to a suggestion.
    out.append("")
    post_lines = [f"LAYER 2 — THIS POST:\nWhat it must communicate: {concept}"]

    art_direction = solution_notes or _SOLUTION_SCENES.get(
        getattr(getattr(package, "solution", None), "value", None) or "general",
        _SOLUTION_SCENES["general"],
    )
    post_lines.append(
        f"SETTING for {sol} (authoritative — this decides where the scene takes "
        f"place): {art_direction}"
    )
    if scene and scene != concept:
        post_lines.append(
            f"Scene suggestion from the copy (use only the parts that fit the SETTING "
            f"above; ignore anything that contradicts it, and ignore any request for a "
            f"3D render, illustration or split-screen): {scene}"
        )
    if primary:
        post_lines.append(f'On-image headline — the ONLY text, render EXACTLY: "{primary}"')
        post_lines.append(
            "Set it in the reference's heading style and wrap it the way the references "
            "wrap theirs; put the single most important word in the brand's accent pill. "
            "Do not add a supporting line beneath it."
        )
    else:
        post_lines.append("No on-image text: render the scene only, with no words at all.")
    out.append("\n".join(post_lines))

    # ── Layer 3 — the fixed quality bar ─────────────────────────────────────
    out.append("")
    out.append(_QUALITY_BAR)
    out.append("")
    out.append(_TEXT_RULE)

    return "\n".join(out)


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

            references = references[:MAX_REFERENCE_IMAGES]

            provider = (await get_app_setting("image_provider")) or "openai"
            api_key = await get_app_setting("image_api_key")
            model = (await get_app_setting("image_model")) or DEFAULT_OPENAI_IMAGE_MODEL
            try:
                n = int((await get_app_setting("image_candidates")) or _DEFAULT_CANDIDATES)
            except (TypeError, ValueError):
                n = _DEFAULT_CANDIDATES
            quality = (await get_app_setting("image_quality")) or _DEFAULT_QUALITY
            size = (await get_app_setting("image_size")) or _DEFAULT_SIZE
            fidelity = (await get_app_setting("image_fidelity")) or _DEFAULT_FIDELITY

            prompt = _scene_prompt(package, brand, solution_notes, len(references))

            image_list = await generate_candidates(
                provider,
                prompt,
                api_key,
                references=references,
                n=n,
                size=size,
                quality=quality,
                model=model,
                input_fidelity=fidelity,
            )

            # Persist every generated image as a VisualGeneration row (image
            # history), so all runs stay selectable — not just the latest run.
            has_refs = len(references) > 0
            new_gen_ids: list[str] = []
            for img in image_list:
                gen = VisualGeneration(
                    package_id=package.id,
                    image_data=img,
                    content_type="image/png",
                    used_references=has_refs,
                    reference_count=len(references),
                    provider=provider,
                    scene_prompt=prompt,
                )
                db.add(gen)
                await db.flush()  # assign gen.id
                new_gen_ids.append(str(gen.id))

            assets = dict(package.asset_urls or {})
            assets.update(
                {
                    "selected_generation_id": new_gen_ids[0] if new_gen_ids else assets.get("selected_generation_id"),
                    "provider": provider,
                    "model": model,
                    "scene_prompt": prompt,
                    "used_references": has_refs,
                    "reference_count": len(references),
                    "visual_status": "draft",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            # Drop legacy inline data-uris now that history is persisted in its own table.
            assets.pop("image", None)
            assets.pop("candidates", None)
            assets.pop("selected_id", None)
            package.asset_urls = assets
            await db.flush()
            logger.info(
                "Phase 4 generated %d image(s) for package %s (refs=%d, provider=%s, model=%s)",
                len(new_gen_ids),
                package_id,
                len(references),
                provider,
                model,
            )
            return {
                "visual_status": "draft",
                "generated": len(new_gen_ids),
                "used_references": has_refs,
            }
