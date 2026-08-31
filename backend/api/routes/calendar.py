"""
api/routes/calendar.py
Phase 2 — Content calendar endpoints.
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
from models.db_models import Brand, ContentCalendar

logger = logging.getLogger(__name__)
router = APIRouter()

# Last-run status per brand so the UI can surface a background-run failure
# instead of a silent empty list. In-memory (single-instance admin tool); it
# resets on restart, which is fine — it only mirrors the most recent run.
# Background-run status now lives in core.job_status (shared across stages).


class CalendarRunRequest(BaseModel):
    report_id: Optional[uuid.UUID] = None      # specific approved report; else latest approved
    post_count: Optional[int] = None           # defaults to brand.monthly_post_target
    platforms: Optional[list[str]] = None      # defaults to ["instagram", "linkedin"]


class CalendarRunResponse(BaseModel):
    message: str
    brand_id: str


class CalendarStatusResponse(BaseModel):
    status: str = "idle"     # idle | running | done | error
    message: str = ""
    log: list = []


class CalendarResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    trend_report_card_id: Optional[uuid.UUID] = None
    planning_period: str
    post_count: int
    is_approved: bool
    platforms: Optional[list] = None
    entries: Optional[list] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True


@router.post("/calendar/{brand_id}/run", response_model=CalendarRunResponse)
async def run_calendar(
    brand_id: uuid.UUID,
    payload: CalendarRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers Phase 2 content calendar generation for a brand.
    Requires an APPROVED Trend Report Card (Phase 1). Runs in the background —
    check GET /calendar/{brand_id} for results.
    """
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")

    report_id = payload.report_id
    post_count = payload.post_count
    platforms = payload.platforms

    from core.job_status import start_job, finish_job, fail_job, log_step
    job_key = f"calendar:{brand_id}"
    start_job(job_key, "Building the monthly plan…")

    async def _run():
        from phases.phase2_calendar import Phase2Calendar
        try:
            log_step(job_key, "Allocating solutions and drafting the plan with AI…")
            runner = Phase2Calendar()
            result = await runner.run(
                brand_id=str(brand_id),
                report_id=report_id,
                post_count=post_count,
                platforms=platforms,
            )
            finish_job(job_key, f"Calendar ready — {len(result.entries)} posts planned.")
        except Exception as exc:  # noqa: BLE001 — surface the real reason to the UI
            logger.exception("Calendar run failed for brand %s", brand_id)
            fail_job(job_key, str(exc))

    background_tasks.add_task(_run)

    return CalendarRunResponse(
        message="Phase 2 calendar generation started. Check /calendar/{brand_id} for results.",
        brand_id=str(brand_id),
    )


@router.get("/calendar/{brand_id}/status", response_model=CalendarStatusResponse)
async def calendar_status(brand_id: uuid.UUID):
    """Most recent background calendar-run status for a brand (idle/running/done/error)."""
    from core.job_status import get_job
    job = get_job(f"calendar:{brand_id}")
    if not job:
        return CalendarStatusResponse()
    return CalendarStatusResponse(**job)


@router.get("/calendar/{brand_id}", response_model=list[CalendarResponse])
async def list_calendars(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns all content calendars for a brand, newest first."""
    result = await db.execute(
        select(ContentCalendar)
        .where(ContentCalendar.brand_id == brand_id)
        .order_by(ContentCalendar.created_at.desc())
    )
    return result.scalars().all()


@router.get("/calendar/detail/{calendar_id}", response_model=CalendarResponse)
async def get_calendar(calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Returns a single content calendar."""
    result = await db.execute(
        select(ContentCalendar).where(ContentCalendar.id == calendar_id)
    )
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found.")
    return calendar


@router.patch("/calendar/{calendar_id}/approve")
async def approve_calendar(calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Human approval gate — marks a content calendar as approved (gate before Phase 3)."""
    result = await db.execute(
        select(ContentCalendar).where(ContentCalendar.id == calendar_id)
    )
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found.")

    calendar.is_approved = True
    return {"message": "Calendar approved.", "calendar_id": str(calendar_id)}