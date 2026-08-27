"""
api/routes/research.py
Phase 1 — Competitive intelligence endpoints.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from models.db_models import Brand, TrendReportCard

router = APIRouter()


class ResearchRunRequest(BaseModel):
    planning_period: str   # e.g. "2025-06"
    max_posts: int = 20


class ResearchRunResponse(BaseModel):
    message: str
    brand_id: str
    planning_period: str


class TrendReportResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    planning_period: str
    is_approved: bool
    trending_topics: Optional[list] = None
    hot_formats: Optional[list] = None
    content_gaps: Optional[list] = None
    algorithm_notes: Optional[dict] = None
    recommended_pillars: Optional[list] = None
    sources: Optional[dict] = None

    class Config:
        from_attributes = True


@router.post("/research/{brand_id}/run", response_model=ResearchRunResponse)
async def run_research(
    brand_id: uuid.UUID,
    payload: ResearchRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers Phase 1 competitive intelligence run for a brand.
    Runs in the background — check /research/{brand_id}/reports for results.
    """
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")

    settings = get_settings()
    from core.settings_store import get_app_setting

    # Search provider + keys come from the in-app Settings page (encrypted in DB).
    search_provider = (await get_app_setting("search_provider")) or "serper"
    search_key = await get_app_setting("search_api_key")

    sources = brand.research_sources or {}
    apify_key = None
    if sources.get("use_apify"):
        apify_key = (await get_app_setting("apify_api_key")) or settings.bootstrap_apify_key

    async def _run():
        from phases.phase1_research import Phase1Research
        runner = Phase1Research(
            apify_key=apify_key,
            search_provider=search_provider,
            search_key=search_key,
        )
        await runner.run(
            brand_id=str(brand_id),
            planning_period=payload.planning_period,
            max_posts_per_competitor=payload.max_posts,
        )

    background_tasks.add_task(_run)

    return ResearchRunResponse(
        message="Phase 1 research started. Check /reports for results.",
        brand_id=str(brand_id),
        planning_period=payload.planning_period,
    )


@router.get("/research/{brand_id}/reports", response_model=list[TrendReportResponse])
async def list_trend_reports(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Returns all Trend Report Cards for a brand."""
    result = await db.execute(
        select(TrendReportCard)
        .where(TrendReportCard.brand_id == brand_id)
        .order_by(TrendReportCard.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/research/reports/{report_id}/approve")
async def approve_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Human approval gate — marks a Trend Report Card as approved."""
    result = await db.execute(
        select(TrendReportCard).where(TrendReportCard.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    report.is_approved = True
    return {"message": "Report approved.", "report_id": str(report_id)}