"""
api/routes/visuals.py
Phase 4 — branded visual generation + review (Approval 3: copy + visual).

B3: every generated image is persisted as a VisualGeneration row (image history),
so all runs stay selectable — not just the latest. Bytes are served from
`/visuals/generations/{id}/raw`; the chosen one is tracked by
`ContentPackage.asset_urls['selected_generation_id']`.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import ContentPackage, ContentStatusEnum, VisualGeneration

logger = logging.getLogger(__name__)
router = APIRouter()

# Last-run visual status per package so the UI can surface a background-run
# failure instead of a silent empty result. In-memory (single-instance tool).
_VISUAL_JOBS: dict[str, dict] = {}


class VisualStatusResponse(BaseModel):
    status: str = "idle"      # idle | running | done | error
    message: str = ""


class VisualResponse(BaseModel):
    package_id: str
    visual_status: Optional[str] = None
    selected_generation_id: Optional[str] = None
    generations: list[dict] = []      # [{id, created_at, used_references, reference_count}]
    used_references: Optional[bool] = None
    reference_count: Optional[int] = None
    provider: Optional[str] = None
    generated_at: Optional[str] = None


class SelectGenerationPayload(BaseModel):
    generation_id: str


async def _get_package(package_id: uuid.UUID, db: AsyncSession) -> ContentPackage:
    res = await db.execute(select(ContentPackage).where(ContentPackage.id == package_id))
    package = res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Content package not found.")
    return package


async def _list_generations(package_id: uuid.UUID, db: AsyncSession) -> list[VisualGeneration]:
    res = await db.execute(
        select(VisualGeneration)
        .where(VisualGeneration.package_id == package_id)
        .order_by(VisualGeneration.created_at.desc())
    )
    return list(res.scalars().all())


@router.post("/visuals/{package_id}/generate")
async def generate_visual(
    package_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Generate branded visual candidates for an APPROVED content package (runs in
    the background — poll /visuals/{package_id}/status). Each run appends to the
    package's image history."""
    package = await _get_package(package_id, db)
    if package.status != ContentStatusEnum.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="Approve the copy for this post before generating its visual.",
        )

    _VISUAL_JOBS[str(package_id)] = {"status": "running", "message": "Generating the branded visual…"}

    async def _run():
        from phases.phase4_visual import Phase4Visual
        try:
            await Phase4Visual().run(package_id=str(package_id))
            _VISUAL_JOBS[str(package_id)] = {"status": "done", "message": "Visual ready for review."}
        except Exception as exc:  # noqa: BLE001 — surface the real reason to the UI
            logger.exception("Visual generation failed for package %s", package_id)
            _VISUAL_JOBS[str(package_id)] = {"status": "error", "message": str(exc)}

    background_tasks.add_task(_run)
    return {"message": "Visual generation started.", "package_id": str(package_id)}


@router.get("/visuals/{package_id}/status", response_model=VisualStatusResponse)
async def visual_status(package_id: uuid.UUID):
    """Most recent background visual-run status for a package (idle/running/done/error)."""
    job = _VISUAL_JOBS.get(str(package_id))
    if not job:
        return VisualStatusResponse()
    return VisualStatusResponse(**job)


# Declared before /visuals/{package_id} so the literal "generations" segment wins.
@router.get("/visuals/generations/{gen_id}/raw")
async def get_generation_raw(gen_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Serve the stored bytes of one generated image."""
    res = await db.execute(select(VisualGeneration).where(VisualGeneration.id == gen_id))
    gen = res.scalar_one_or_none()
    if not gen:
        raise HTTPException(status_code=404, detail="Generation not found.")
    return Response(
        content=gen.image_data,
        media_type=gen.content_type or "image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/visuals/{package_id}", response_model=VisualResponse)
async def get_visual(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Return the package's visual review state plus its full generation history
    (newest first). The UI builds thumbnail URLs from each generation id."""
    package = await _get_package(package_id, db)
    a = package.asset_urls or {}
    gens = await _list_generations(package_id, db)

    generations = [
        {
            "id": str(g.id),
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "used_references": g.used_references,
            "reference_count": g.reference_count,
        }
        for g in gens
    ]
    selected = a.get("selected_generation_id")
    if not selected and generations:
        selected = generations[0]["id"]

    # Reference stats of the selected generation (fallback: newest).
    sel_gen = next((g for g in gens if str(g.id) == selected), gens[0] if gens else None)

    return VisualResponse(
        package_id=str(package_id),
        visual_status=a.get("visual_status"),
        selected_generation_id=selected,
        generations=generations,
        used_references=(sel_gen.used_references if sel_gen else a.get("used_references")),
        reference_count=(sel_gen.reference_count if sel_gen else a.get("reference_count")),
        provider=a.get("provider"),
        generated_at=a.get("generated_at"),
    )


def _set_visual_status(package: ContentPackage, value: str) -> None:
    assets = dict(package.asset_urls or {})
    assets["visual_status"] = value
    package.asset_urls = assets


@router.patch("/visuals/{package_id}/select")
async def select_generation(
    package_id: uuid.UUID,
    payload: SelectGenerationPayload,
    db: AsyncSession = Depends(get_db),
):
    """Pick which generation from the history is the chosen visual for this post."""
    package = await _get_package(package_id, db)
    try:
        gen_uuid = uuid.UUID(payload.generation_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid generation id.")
    res = await db.execute(
        select(VisualGeneration).where(
            VisualGeneration.id == gen_uuid,
            VisualGeneration.package_id == package_id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Generation not found for this package.")
    assets = dict(package.asset_urls or {})
    assets["selected_generation_id"] = payload.generation_id
    package.asset_urls = assets
    return {"message": "Generation selected.", "package_id": str(package_id), "selected_generation_id": payload.generation_id}


@router.patch("/visuals/{package_id}/approve")
async def approve_visual(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Approval 3 — the human approves the branded visual for this post."""
    package = await _get_package(package_id, db)
    gens = await _list_generations(package_id, db)
    if not gens:
        raise HTTPException(status_code=400, detail="Generate a visual before approving it.")
    _set_visual_status(package, "approved")
    return {"message": "Visual approved.", "package_id": str(package_id)}


@router.patch("/visuals/{package_id}/reject")
async def reject_visual(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Reject the current visual so it can be regenerated."""
    package = await _get_package(package_id, db)
    _set_visual_status(package, "rejected")
    return {"message": "Visual rejected.", "package_id": str(package_id)}
