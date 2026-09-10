"""
api/routes/references.py
V2 — Solution reference-image library (part of the visual-generation redesign).

Per (brand, solution) the owner uploads ~8-10 proven example posts. At Phase-4
visual generation (V4) these are passed to the image model so a new post inherits
the brand's proven style for that solution. Uploads are downscaled with Pillow and
stored in Postgres (BYTEA) — no new infra, and Drive stays retired.

Also exposes per-(brand, solution) `visual_notes` (a free-form style note fed into
the image prompt). Notes live on `brand_solutions`; a PUT upserts a minimal,
non-focus row if the brand does not yet track that solution.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai_provider import build_provider_from_config
from core.database import get_db
from models.db_models import (
    AIProviderConfig,
    Brand,
    BrandSolution,
    ContentPackage,
    PhaseEnum,
    SolutionEnum,
    SolutionReferenceImage,
    TrendReportCard,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Limits (kept conservative — references are a small, curated set).
_MAX_PER_SOLUTION = 24        # generous headroom over the owner's ~8-10
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024   # 15 MB per file, before downscale
_MAX_DIM = 1024               # longest edge after downscale
_JPEG_QUALITY = 85


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ReferenceImageResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    solution: SolutionEnum
    filename: Optional[str]
    note: Optional[str]
    content_type: str
    sort_order: int
    created_at: datetime
    raw_url: str

    class Config:
        from_attributes = True


class ReferenceImagePatch(BaseModel):
    note: Optional[str] = None
    sort_order: Optional[int] = None


class ReorderPayload(BaseModel):
    ordered_ids: list[uuid.UUID]


class VisualNotesResponse(BaseModel):
    brand_id: uuid.UUID
    solution: SolutionEnum
    visual_notes: Optional[str]


class VisualNotesPayload(BaseModel):
    visual_notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_response(row: SolutionReferenceImage) -> ReferenceImageResponse:
    return ReferenceImageResponse(
        id=row.id,
        brand_id=row.brand_id,
        solution=row.solution,
        filename=row.filename,
        note=row.note,
        content_type=row.content_type,
        sort_order=row.sort_order,
        created_at=row.created_at,
        raw_url=f"/api/v1/references/{row.id}/raw",
    )


def _downscale(raw: bytes) -> tuple[bytes, str]:
    """Downscale to <= _MAX_DIM on the longest edge and re-encode as JPEG.
    Returns (bytes, content_type). Raises ValueError on an unreadable image."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Not a readable image: {exc}") from exc

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    elif img.mode == "L":
        img = img.convert("RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > _MAX_DIM:
        scale = _MAX_DIM / float(longest)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return out.getvalue(), "image/jpeg"


async def _require_brand(brand_id: uuid.UUID, db: AsyncSession) -> Brand:
    res = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = res.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")
    return brand


async def _get_reference(ref_id: uuid.UUID, db: AsyncSession) -> SolutionReferenceImage:
    res = await db.execute(
        select(SolutionReferenceImage).where(SolutionReferenceImage.id == ref_id)
    )
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Reference image not found.")
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Reference-image endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/brands/{brand_id}/solutions/{solution}/references",
    response_model=list[ReferenceImageResponse],
)
async def list_references(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    db: AsyncSession = Depends(get_db),
):
    """List the reference images for a (brand, solution), ordered for display."""
    res = await db.execute(
        select(SolutionReferenceImage)
        .where(
            SolutionReferenceImage.brand_id == brand_id,
            SolutionReferenceImage.solution == solution,
        )
        .order_by(SolutionReferenceImage.sort_order, SolutionReferenceImage.created_at)
    )
    return [_to_response(r) for r in res.scalars().all()]


@router.post(
    "/brands/{brand_id}/solutions/{solution}/references",
    response_model=list[ReferenceImageResponse],
    status_code=201,
)
async def upload_references(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload one or more example images for a (brand, solution). Each file is
    downscaled (Pillow, JPEG, longest edge <= 1024) before storage."""
    await _require_brand(brand_id, db)

    count_res = await db.execute(
        select(func.count(SolutionReferenceImage.id)).where(
            SolutionReferenceImage.brand_id == brand_id,
            SolutionReferenceImage.solution == solution,
        )
    )
    existing_count = int(count_res.scalar() or 0)
    if existing_count + len(files) > _MAX_PER_SOLUTION:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many references: {existing_count} stored, {len(files)} more "
                f"would exceed the limit of {_MAX_PER_SOLUTION} for this solution."
            ),
        )

    order_res = await db.execute(
        select(func.coalesce(func.max(SolutionReferenceImage.sort_order), -1)).where(
            SolutionReferenceImage.brand_id == brand_id,
            SolutionReferenceImage.solution == solution,
        )
    )
    next_order = int(order_res.scalar() or -1) + 1

    created: list[SolutionReferenceImage] = []
    for f in files:
        raw = await f.read()
        if not raw:
            raise HTTPException(status_code=400, detail=f"Empty file: {f.filename}")
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{f.filename} is larger than {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )
        try:
            data, content_type = _downscale(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{f.filename}: {exc}") from exc

        row = SolutionReferenceImage(
            brand_id=brand_id,
            solution=solution,
            image_data=data,
            content_type=content_type,
            filename=(f.filename or "")[:255] or None,
            sort_order=next_order,
        )
        next_order += 1
        db.add(row)
        created.append(row)

    await db.flush()
    for r in created:
        await db.refresh(r)
    logger.info(
        "Uploaded %d reference image(s) for brand %s / %s", len(created), brand_id, solution.value
    )
    return [_to_response(r) for r in created]


@router.get("/references/{ref_id}/raw")
async def get_reference_raw(ref_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Serve the stored image bytes (what the UI <img> tag loads)."""
    row = await _get_reference(ref_id, db)
    return Response(
        content=row.image_data,
        media_type=row.content_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.patch("/references/{ref_id}", response_model=ReferenceImageResponse)
async def patch_reference(
    ref_id: uuid.UUID,
    payload: ReferenceImagePatch,
    db: AsyncSession = Depends(get_db),
):
    """Update a reference's note and/or sort_order."""
    row = await _get_reference(ref_id, db)
    if payload.note is not None:
        row.note = payload.note
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    await db.flush()
    await db.refresh(row)
    return _to_response(row)


@router.put(
    "/brands/{brand_id}/solutions/{solution}/references/order",
    response_model=list[ReferenceImageResponse],
)
async def reorder_references(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    payload: ReorderPayload,
    db: AsyncSession = Depends(get_db),
):
    """Set the display order for a (brand, solution): sort_order follows the
    position of each id in `ordered_ids`. Ids not belonging to this
    (brand, solution) are rejected."""
    res = await db.execute(
        select(SolutionReferenceImage).where(
            SolutionReferenceImage.brand_id == brand_id,
            SolutionReferenceImage.solution == solution,
        )
    )
    rows = {r.id: r for r in res.scalars().all()}
    for pos, rid in enumerate(payload.ordered_ids):
        row = rows.get(rid)
        if not row:
            raise HTTPException(
                status_code=400,
                detail=f"Reference {rid} does not belong to this brand/solution.",
            )
        row.sort_order = pos
    await db.flush()

    refreshed = await db.execute(
        select(SolutionReferenceImage)
        .where(
            SolutionReferenceImage.brand_id == brand_id,
            SolutionReferenceImage.solution == solution,
        )
        .order_by(SolutionReferenceImage.sort_order, SolutionReferenceImage.created_at)
    )
    return [_to_response(r) for r in refreshed.scalars().all()]


@router.delete("/references/{ref_id}", status_code=204)
async def delete_reference(ref_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a reference image."""
    row = await _get_reference(ref_id, db)
    await db.delete(row)
    await db.flush()
    return Response(status_code=204)


# ─────────────────────────────────────────────────────────────────────────────
# Per-(brand, solution) visual notes
# ─────────────────────────────────────────────────────────────────────────────

async def _get_solution_row(
    brand_id: uuid.UUID, solution: SolutionEnum, db: AsyncSession
) -> Optional[BrandSolution]:
    res = await db.execute(
        select(BrandSolution).where(
            BrandSolution.brand_id == brand_id,
            BrandSolution.solution == solution,
        )
    )
    return res.scalar_one_or_none()


@router.get(
    "/brands/{brand_id}/solutions/{solution}/visual-notes",
    response_model=VisualNotesResponse,
)
async def get_visual_notes(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    db: AsyncSession = Depends(get_db),
):
    """Return the visual note for a (brand, solution). Null when none is set (or
    the brand does not track this solution yet)."""
    row = await _get_solution_row(brand_id, solution, db)
    return VisualNotesResponse(
        brand_id=brand_id,
        solution=solution,
        visual_notes=(row.visual_notes if row else None),
    )


@router.put(
    "/brands/{brand_id}/solutions/{solution}/visual-notes",
    response_model=VisualNotesResponse,
)
async def set_visual_notes(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    payload: VisualNotesPayload,
    db: AsyncSession = Depends(get_db),
):
    """Set the visual note for a (brand, solution). Upserts a minimal, non-focus
    `brand_solutions` row if the brand does not yet track this solution, so a note
    can be attached without implying it is a content focus."""
    await _require_brand(brand_id, db)
    row = await _get_solution_row(brand_id, solution, db)
    if not row:
        row = BrandSolution(
            brand_id=brand_id,
            solution=solution,
            is_focus=False,
            priority=100,
            importance=3,
        )
        db.add(row)
    row.visual_notes = payload.visual_notes
    await db.flush()
    await db.refresh(row)
    return VisualNotesResponse(
        brand_id=brand_id, solution=solution, visual_notes=row.visual_notes
    )


# ─────────────────────────────────────────────────────────────────────────────
# AI-drafted art direction (visual notes)
#
# Visual notes are the single strongest lever on image quality: Phase 4 treats
# them as the authoritative SETTING for a solution, overriding whatever location
# the copy step invented. But an empty textarea is a bad ask — the owner should
# not have to guess the wording. This endpoint drafts one from what the system
# already knows about the brand and the solution, and returns it WITHOUT saving,
# so the human edits and approves it (the same human-in-the-loop rule as every
# other stage).
# ─────────────────────────────────────────────────────────────────────────────

_ART_DIRECTION_SYSTEM = """You are an art director for a B2B SaaS brand. You write
short, concrete art-direction briefs that a photographer or an image model can follow
without asking questions.

You describe SCENES: who is in frame, where they are, what they are doing, what is in
their hands, and the light. You never describe layout, logo placement, typography or
color systems — those are fixed by the brand template elsewhere and repeating them
crowds out the scene.

You reply with the brief text only. No preamble, no headings, no markdown, no quotes."""

_ART_DIRECTION_PROMPT = """Write an art-direction brief for ONE solution area of this brand.
It will be pasted into an image prompt for every future post in this area, so it must be
general enough to cover many posts and specific enough to prevent generic stock imagery.

BRAND: {brand_name}
INDUSTRY: {industry}
SOLUTION AREA: {solution_label}
BRAND VISUAL STYLE (context only — do NOT restate it in your answer): {visual_language}

DEFAULT SCENE FAMILY the system falls back to today:
{scene_family}

WHAT RESEARCH SAYS ABOUT THIS AREA RIGHT NOW (may be empty):
{research_brief}

SCENES RECENT POSTS IN THIS AREA ASKED FOR (may be empty — treat as examples of what
the copy step tends to invent, not as targets):
{recent_scenes}

REFERENCE IMAGES ON FILE FOR THIS AREA: {reference_count}

{instruction_block}
RULES:
- 2-4 sentences, 45-80 words. This gets read by a model, not framed on a wall.
- Name the real settings this solution actually happens in, and say plainly which
  settings to avoid if the area keeps drifting somewhere wrong.
- Name the people: their role, what they wear, what device or tool they hold.
- Real photography of real people in real places. Never ask for a 3D render, an
  illustration, vector art, or a split-screen diagram.
- Say something about light and mood in a few words.
- Do NOT mention logo, headline, pill, palette, layout, negative space or typography.

Reply with the brief text only."""


class VisualNotesSuggestion(BaseModel):
    brand_id: uuid.UUID
    solution: SolutionEnum
    suggestion: str
    used_reference_count: int
    used_recent_posts: int
    used_research: bool


class VisualNotesSuggestRequest(BaseModel):
    instruction: Optional[str] = None


def _solution_label(solution: SolutionEnum) -> str:
    return str(solution.value).replace("_", " ")


def _visual_language(brand: Brand) -> str:
    vi = getattr(brand, "visual_identity", None)
    if not isinstance(vi, dict):
        return "clean, modern B2B SaaS"
    bits: list[str] = []
    sk = vi.get("style_keywords")
    if isinstance(sk, list) and sk:
        bits.append(", ".join(str(x) for x in sk))
    mo = vi.get("motifs")
    if isinstance(mo, list) and mo:
        bits.append("; ".join(str(x) for x in mo))
    return " | ".join(bits) if bits else "clean, modern B2B SaaS"


@router.post(
    "/brands/{brand_id}/solutions/{solution}/visual-notes/suggest",
    response_model=VisualNotesSuggestion,
)
async def suggest_visual_notes(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    payload: VisualNotesSuggestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Draft an art-direction brief for a (brand, solution) with the Copy AI.

    Grounded in what the system already has: the brand's visual style, the default
    scene family Phase 4 uses, the latest approved trend report's brief for this
    solution, and the scenes recent posts asked for. Returns the draft only — the
    caller reviews it and saves it through PUT visual-notes."""
    brand = await _require_brand(brand_id, db)

    cfg_res = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.brand_id == brand_id,
            AIProviderConfig.phase == PhaseEnum.COPY,
        )
    )
    ai_config = cfg_res.scalar_one_or_none()
    if not ai_config:
        raise HTTPException(
            status_code=400,
            detail="No Copy AI provider configured for this brand. Add one under AI Providers.",
        )

    # How many references exist for this solution (context, not input — the text
    # model cannot see them).
    ref_count = (
        await db.execute(
            select(func.count())
            .select_from(SolutionReferenceImage)
            .where(
                SolutionReferenceImage.brand_id == brand_id,
                SolutionReferenceImage.solution == solution,
            )
        )
    ).scalar_one() or 0

    # Scenes recent posts in this solution asked for.
    pkg_res = await db.execute(
        select(ContentPackage)
        .where(
            ContentPackage.brand_id == brand_id,
            ContentPackage.solution == solution,
        )
        .order_by(ContentPackage.created_at.desc())
        .limit(6)
    )
    recent: list[str] = []
    for pkg in pkg_res.scalars().all():
        vd = pkg.visual_direction if isinstance(pkg.visual_direction, dict) else {}
        scene = str(vd.get("image_prompt") or vd.get("concept") or "").strip()
        if scene:
            recent.append(f"- {scene[:240]}")

    # The latest approved trend report's brief for this solution.
    rep_res = await db.execute(
        select(TrendReportCard)
        .where(
            TrendReportCard.brand_id == brand_id,
            TrendReportCard.is_approved.is_(True),
        )
        .order_by(TrendReportCard.created_at.desc())
        .limit(1)
    )
    research_brief = ""
    report = rep_res.scalar_one_or_none()
    if report and isinstance(report.algorithm_notes, dict):
        for b in report.algorithm_notes.get("solution_briefs") or []:
            if not isinstance(b, dict):
                continue
            if str(b.get("solution") or "").strip().lower() == solution.value:
                parts = [
                    str(b.get("whats_happening") or "").strip(),
                    str(b.get("why_it_matters") or "").strip(),
                ]
                research_brief = " ".join(x for x in parts if x)[:900]
                break

    from phases.phase4_visual import SOLUTION_SCENES

    instruction = (payload.instruction or "").strip()
    prompt = _ART_DIRECTION_PROMPT.format(
        brand_name=brand.display_name,
        industry=brand.industry or "B2B SaaS",
        solution_label=_solution_label(solution),
        visual_language=_visual_language(brand),
        scene_family=SOLUTION_SCENES.get(solution.value, SOLUTION_SCENES["general"]),
        research_brief=research_brief or "(none)",
        recent_scenes="\n".join(recent) if recent else "(none)",
        reference_count=ref_count,
        instruction_block=(
            f"EXTRA DIRECTION FROM THE OWNER (obey this above all): {instruction}\n\n"
            if instruction
            else ""
        ),
    )

    provider = build_provider_from_config(
        provider_name=ai_config.provider.value,
        model=ai_config.model,
        encrypted_api_key=ai_config.api_key_enc,
    )
    response = await provider.complete(
        user_message=prompt,
        system_prompt=_ART_DIRECTION_SYSTEM,
        temperature=ai_config.temperature,
        max_tokens=400,
    )
    suggestion = (response.content or "").strip().strip('"').strip()
    if not suggestion:
        raise HTTPException(status_code=502, detail="The AI returned an empty brief.")

    return VisualNotesSuggestion(
        brand_id=brand_id,
        solution=solution,
        suggestion=suggestion,
        used_reference_count=ref_count,
        used_recent_posts=len(recent),
        used_research=bool(research_brief),
    )
