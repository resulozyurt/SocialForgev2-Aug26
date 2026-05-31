"""
api/routes/calendar.py
Phase 2 — Content calendar endpoints.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import Brand, ContentCalendar

router = APIRouter()


class CalendarRunRequest(BaseModel):
    report_id: Optional[uuid.UUID] = None      # specific approved report; else latest approved
    post_count: Optional[int] = None           # defaults to brand.monthly_post_target
    platforms: Optional[list[str]] = None      # defaults to ["instagram", "linkedin"]


class CalendarRunResponse(BaseModel):
    message: str
    brand_id: str


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

    async def _run():
        from phases.phase2_calendar import Phase2Calendar
        runner = Phase2Calendar()
        await runner.run(
            brand_id=str(brand_id),
            report_id=report_id,
            post_count=post_count,
            platforms=platforms,
        )

    background_tasks.add_task(_run)

    return CalendarRunResponse(
        message="Phase 2 calendar generation started. Check /calendar/{brand_id} for results.",
        brand_id=str(brand_id),
    )


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