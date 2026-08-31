"""
api/routes/copy.py
Phase 3 — Content generation (copywriting) endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import (
    Brand,
    ContentPackage,
    ContentStatusEnum,
    ContentTypeEnum,
    PlatformEnum,
)

router = APIRouter()


class CopyRunRequest(BaseModel):
    calendar_id: Optional[uuid.UUID] = None   # specific approved calendar; else latest approved
    limit: Optional[int] = None               # generate only first N entries (quick test)
    generate_tr: bool = True                  # also produce Turkish copy


class CopyRunResponse(BaseModel):
    message: str
    brand_id: str


class ContentPackageResponse(BaseModel):
    id: uuid.UUID
    post_id: str
    brand_id: uuid.UUID
    platform: PlatformEnum
    content_type: ContentTypeEnum
    status: ContentStatusEnum
    scheduled_at: Optional[datetime] = None
    objective: Optional[str] = None
    target_audience: Optional[str] = None
    strategic_rationale: Optional[str] = None
    copy_package_en: Optional[dict] = None
    copy_package_tr: Optional[dict] = None
    visual_direction: Optional[dict] = None

    class Config:
        from_attributes = True


@router.post("/copy/{brand_id}/run", response_model=CopyRunResponse)
async def run_copy(
    brand_id: uuid.UUID,
    payload: CopyRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers Phase 3 copy generation for a brand.
    Requires an APPROVED Content Calendar (Phase 2). Runs in the background —
    one AI call per calendar entry, so a full month can take a few minutes.
    Check GET /copy/{brand_id} for results.
    """
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")

    calendar_id = payload.calendar_id
    limit = payload.limit
    generate_tr = payload.generate_tr

    from core.job_status import start_job, finish_job, fail_job, log_step
    job_key = f"copy:{brand_id}"
    start_job(job_key, "Starting copy generation…")

    async def _run():
        from phases.phase3_copy import Phase3Copy
        try:
            runner = Phase3Copy()
            await runner.run(
                brand_id=str(brand_id),
                calendar_id=calendar_id,
                limit=limit,
                generate_tr=generate_tr,
                progress=lambda m: log_step(job_key, m),
            )
            finish_job(job_key, "Copy generation complete — packages ready to review.")
        except Exception as exc:  # noqa: BLE001 — surface the real reason to the UI
            fail_job(job_key, str(exc))

    background_tasks.add_task(_run)

    return CopyRunResponse(
        message="Phase 3 copy generation started. Check /copy/{brand_id} for results.",
        brand_id=str(brand_id),
    )


@router.get("/copy/{brand_id}", response_model=list[ContentPackageResponse])
async def list_packages(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns all content packages for a brand, newest first."""
    result = await db.execute(
        select(ContentPackage)
        .where(ContentPackage.brand_id == brand_id)
        .order_by(ContentPackage.created_at.desc())
    )
    return result.scalars().all()


@router.get("/copy/detail/{package_id}", response_model=ContentPackageResponse)
async def get_package(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns a single content package."""
    result = await db.execute(
        select(ContentPackage).where(ContentPackage.id == package_id)
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Content package not found.")
    return package


class CopyStatusResponse(BaseModel):
    status: str = "idle"      # idle | running | done | error
    message: str = ""
    log: list = []


@router.get("/copy/{brand_id}/status", response_model=CopyStatusResponse)
async def copy_status(brand_id: uuid.UUID):
    """Most recent background copy-run status + real step log for a brand."""
    from core.job_status import get_job
    job = get_job(f"copy:{brand_id}")
    if not job:
        return CopyStatusResponse()
    return CopyStatusResponse(**job)


@router.patch("/copy/{package_id}/approve")
async def approve_package(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Human approval gate — marks a content package APPROVED (gate before Phase 4)."""
    result = await db.execute(
        select(ContentPackage).where(ContentPackage.id == package_id)
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Content package not found.")

    package.status = ContentStatusEnum.APPROVED
    return {"message": "Content package approved.", "package_id": str(package_id)}