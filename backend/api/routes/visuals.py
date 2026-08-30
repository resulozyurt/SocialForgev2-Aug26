"""
api/routes/visuals.py
Phase 4 — branded visual generation + review (Approval 3: copy + visual).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import ContentPackage, ContentStatusEnum

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
    image: Optional[str] = None
    text_overlay: Optional[dict] = None
    provider: Optional[str] = None
    generated_at: Optional[str] = None


async def _get_package(package_id: uuid.UUID, db: AsyncSession) -> ContentPackage:
    res = await db.execute(select(ContentPackage).where(ContentPackage.id == package_id))
    package = res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Content package not found.")
    return package


@router.post("/visuals/{package_id}/generate")
async def generate_visual(
    package_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Generate a branded visual for an APPROVED content package (runs in the
    background — poll /visuals/{package_id}/status)."""
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


@router.get("/visuals/{package_id}", response_model=VisualResponse)
async def get_visual(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns the current visual (base64 data URI in D1) and its review status."""
    package = await _get_package(package_id, db)
    a = package.asset_urls or {}
    return VisualResponse(
        package_id=str(package_id),
        visual_status=a.get("visual_status"),
        image=a.get("image"),
        text_overlay=a.get("text_overlay"),
        provider=a.get("provider"),
        generated_at=a.get("generated_at"),
    )


def _set_visual_status(package: ContentPackage, value: str) -> None:
    assets = dict(package.asset_urls or {})
    assets["visual_status"] = value
    package.asset_urls = assets


@router.patch("/visuals/{package_id}/approve")
async def approve_visual(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Approval 3 — the human approves the branded visual for this post."""
    package = await _get_package(package_id, db)
    if not (package.asset_urls or {}).get("image"):
        raise HTTPException(status_code=400, detail="Generate a visual before approving it.")
    _set_visual_status(package, "approved")
    return {"message": "Visual approved.", "package_id": str(package_id)}


@router.patch("/visuals/{package_id}/reject")
async def reject_visual(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Reject the current visual so it can be regenerated."""
    package = await _get_package(package_id, db)
    _set_visual_status(package, "rejected")
    return {"message": "Visual rejected.", "package_id": str(package_id)}
