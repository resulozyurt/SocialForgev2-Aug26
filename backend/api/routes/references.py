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

from core.database import get_db
from models.db_models import Brand, BrandSolution, SolutionEnum, SolutionReferenceImage

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
