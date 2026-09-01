"""
api/routes/boards.py
F0 — Month boards: the first-class organizing unit for the pipeline.

A board is one (brand, planning_period). Every stage (research -> calendar ->
copy -> visual) is scoped to a board's period. The board owns no content: the
report/calendar/package chain already carries `planning_period`, so a board just
groups the month and holds its lifecycle. This module lists boards (with rolled-up
per-stage progress for the board cards), creates them (idempotent per period),
patches status/title/notes, and deletes the board row (content is left intact in
F0; cascade-delete of a month's content comes later).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import (
    Brand,
    ContentCalendar,
    ContentPackage,
    ContentStatusEnum,
    MonthBoard,
    TrendReportCard,
    VisualGeneration,
)

router = APIRouter()

_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")
_STATUSES = {"active", "ready", "archived"}


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class BoardStats(BaseModel):
    """Rolled-up per-stage progress for one board's period, powering the card."""
    report_total: int = 0
    report_approved: int = 0
    calendar_total: int = 0
    calendar_approved: int = 0
    copy_total: int = 0
    copy_approved: int = 0
    visual_posts: int = 0        # approved posts that have >=1 generated visual
    post_target: int = 0         # brand.monthly_post_target (the month's goal)


class BoardResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    planning_period: str
    title: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    stats: BoardStats

    class Config:
        from_attributes = True


class BoardCreate(BaseModel):
    planning_period: str
    title: Optional[str] = None


class BoardPatch(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _stats_by_period(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, BoardStats]:
    """Aggregate per-stage counts grouped by planning_period for a brand.

    A few grouped queries (not one per board), then mapped onto boards by period.
    """
    out: dict[str, BoardStats] = {}

    def bucket(period: Optional[str]) -> BoardStats:
        key = period or ""
        if key not in out:
            out[key] = BoardStats()
        return out[key]

    # Reports
    rq = await db.execute(
        select(
            TrendReportCard.planning_period,
            func.count().label("total"),
            func.count().filter(TrendReportCard.is_approved.is_(True)).label("approved"),
        )
        .where(TrendReportCard.brand_id == brand_id)
        .group_by(TrendReportCard.planning_period)
    )
    for period, total, approved in rq.all():
        s = bucket(period)
        s.report_total = int(total or 0)
        s.report_approved = int(approved or 0)

    # Calendars
    cq = await db.execute(
        select(
            ContentCalendar.planning_period,
            func.count().label("total"),
            func.count().filter(ContentCalendar.is_approved.is_(True)).label("approved"),
        )
        .where(ContentCalendar.brand_id == brand_id)
        .group_by(ContentCalendar.planning_period)
    )
    for period, total, approved in cq.all():
        s = bucket(period)
        s.calendar_total = int(total or 0)
        s.calendar_approved = int(approved or 0)

    # Copy packages
    pq = await db.execute(
        select(
            ContentPackage.planning_period,
            func.count().label("total"),
            func.count()
            .filter(ContentPackage.status == ContentStatusEnum.APPROVED)
            .label("approved"),
        )
        .where(ContentPackage.brand_id == brand_id)
        .group_by(ContentPackage.planning_period)
    )
    for period, total, approved in pq.all():
        s = bucket(period)
        s.copy_total = int(total or 0)
        s.copy_approved = int(approved or 0)

    # Visuals: distinct posts (of that period) that have >=1 generation
    vq = await db.execute(
        select(
            ContentPackage.planning_period,
            func.count(func.distinct(VisualGeneration.package_id)).label("posts"),
        )
        .select_from(VisualGeneration)
        .join(ContentPackage, ContentPackage.id == VisualGeneration.package_id)
        .where(ContentPackage.brand_id == brand_id)
        .group_by(ContentPackage.planning_period)
    )
    for period, posts in vq.all():
        s = bucket(period)
        s.visual_posts = int(posts or 0)

    return out


def _to_response(board: MonthBoard, stats: BoardStats) -> BoardResponse:
    return BoardResponse(
        id=board.id,
        brand_id=board.brand_id,
        planning_period=board.planning_period,
        title=board.title,
        status=board.status,
        notes=board.notes,
        created_at=board.created_at,
        updated_at=board.updated_at,
        stats=stats,
    )


async def _get_board_or_404(db: AsyncSession, board_id: uuid.UUID) -> MonthBoard:
    board = (
        await db.execute(select(MonthBoard).where(MonthBoard.id == board_id))
    ).scalar_one_or_none()
    if not board:
        raise HTTPException(status_code=404, detail="Board not found.")
    return board


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/brands/{brand_id}/boards", response_model=list[BoardResponse])
async def list_boards(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """All month boards for a brand, newest period first, each with stage stats."""
    brand = (
        await db.execute(select(Brand).where(Brand.id == brand_id))
    ).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")

    boards = (
        (
            await db.execute(
                select(MonthBoard)
                .where(MonthBoard.brand_id == brand_id)
                .order_by(MonthBoard.planning_period.desc())
            )
        )
        .scalars()
        .all()
    )
    stats_map = await _stats_by_period(db, brand_id)
    target = brand.monthly_post_target or 0

    result = []
    for b in boards:
        stats = stats_map.get(b.planning_period, BoardStats())
        stats.post_target = target
        result.append(_to_response(b, stats))
    return result


@router.post("/brands/{brand_id}/boards", response_model=BoardResponse)
async def create_board(
    brand_id: uuid.UUID,
    payload: BoardCreate,
    db: AsyncSession = Depends(get_db),
):
    """Open a month board. Idempotent: if one already exists for the period, it
    is returned unchanged (no duplicate months)."""
    period = (payload.planning_period or "").strip()
    if not _PERIOD_RE.match(period):
        raise HTTPException(status_code=422, detail="planning_period must be 'YYYY-MM'.")

    brand = (
        await db.execute(select(Brand).where(Brand.id == brand_id))
    ).scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")

    existing = (
        await db.execute(
            select(MonthBoard).where(
                MonthBoard.brand_id == brand_id,
                MonthBoard.planning_period == period,
            )
        )
    ).scalar_one_or_none()
    if existing:
        stats_map = await _stats_by_period(db, brand_id)
        stats = stats_map.get(period, BoardStats())
        stats.post_target = brand.monthly_post_target or 0
        return _to_response(existing, stats)

    board = MonthBoard(
        brand_id=brand_id,
        planning_period=period,
        title=(payload.title or None),
        status="active",
    )
    db.add(board)
    await db.commit()
    await db.refresh(board)

    stats = BoardStats(post_target=brand.monthly_post_target or 0)
    return _to_response(board, stats)


@router.patch("/boards/{board_id}", response_model=BoardResponse)
async def patch_board(
    board_id: uuid.UUID,
    payload: BoardPatch,
    db: AsyncSession = Depends(get_db),
):
    """Update a board's status / title / notes."""
    board = await _get_board_or_404(db, board_id)

    if payload.status is not None:
        if payload.status not in _STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of {sorted(_STATUSES)}.",
            )
        board.status = payload.status
    if payload.title is not None:
        board.title = payload.title or None
    if payload.notes is not None:
        board.notes = payload.notes or None

    await db.commit()
    await db.refresh(board)

    stats_map = await _stats_by_period(db, board.brand_id)
    stats = stats_map.get(board.planning_period, BoardStats())
    brand = (
        await db.execute(select(Brand).where(Brand.id == board.brand_id))
    ).scalar_one_or_none()
    stats.post_target = (brand.monthly_post_target if brand else 0) or 0
    return _to_response(board, stats)


@router.delete("/boards/{board_id}")
async def delete_board(board_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Remove the board row only. The month's content (reports/calendars/
    packages) is left intact in F0 — cascade-delete of a month comes later."""
    board = await _get_board_or_404(db, board_id)
    await db.delete(board)
    await db.commit()
    return {"deleted": True}
