"""
api/routes/calendar.py
Phase 2 — Content calendar endpoints.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai_provider import build_provider_from_config
from core.database import get_db
from core.json_utils import parse_ai_json
from models.db_models import AIProviderConfig, Brand, ContentCalendar, PhaseEnum

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
    is_rejected: bool = False
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
    calendar.is_rejected = False
    calendar.approved_at = datetime.now(timezone.utc)
    return {"message": "Calendar approved.", "calendar_id": str(calendar_id)}


@router.patch("/calendar/{calendar_id}/reject")
async def reject_calendar(calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Human reject — keeps the calendar for audit but marks it dismissed."""
    result = await db.execute(
        select(ContentCalendar).where(ContentCalendar.id == calendar_id)
    )
    calendar = result.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found.")
    calendar.is_rejected = True
    calendar.is_approved = False
    calendar.rejected_at = datetime.now(timezone.utc)
    return {"message": "Calendar rejected.", "calendar_id": str(calendar_id)}


@router.delete("/calendar/{calendar_id}", status_code=204)
async def delete_calendar(calendar_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a content calendar. Idempotent: deleting an
    already-removed calendar is treated as success so a stale UI never sees a 404."""
    result = await db.execute(
        select(ContentCalendar).where(ContentCalendar.id == calendar_id)
    )
    calendar = result.scalar_one_or_none()
    if calendar is None:
        return
    try:
        await db.delete(calendar)
        await db.flush()
    except Exception as exc:  # noqa: BLE001 — surface the real reason to the client
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Could not delete calendar: {exc}") from exc


class AiEditRequest(BaseModel):
    instruction: str


CAL_AI_EDIT_SYSTEM = (
    "You are revising an existing monthly content calendar for a brand based on a "
    "human editor's instruction. Apply the instruction precisely, keep everything "
    "else intact, and preserve each entry's fields and structure. Respond with valid "
    "JSON only — no preamble, no markdown."
)

CAL_AI_EDIT_PROMPT = """BRAND: {brand}

EDITOR INSTRUCTION:
{instruction}

CURRENT CALENDAR (JSON):
{calendar}

Return the FULL revised calendar as a JSON object with exactly these keys:
"summary" (string) and "entries" (list). Each entry keeps the same fields it has now
(date, solution, platform, content_type, pillar, hook_concept, headline, ai_angle,
objective, rationale). Keep dates within the same planning period and keep the plan
balanced across the brand's solutions. Do not drop fields."""


@router.post("/calendar/{calendar_id}/ai-edit", response_model=CalendarResponse)
async def ai_edit_calendar(
    calendar_id: uuid.UUID,
    payload: AiEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revise a calendar with the Calendar AI using a human instruction. Result is a
    fresh, unapproved draft."""
    if not payload.instruction.strip():
        raise HTTPException(status_code=422, detail="Instruction is required.")
    res = await db.execute(select(ContentCalendar).where(ContentCalendar.id == calendar_id))
    calendar = res.scalar_one_or_none()
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendar not found.")

    brand_res = await db.execute(select(Brand).where(Brand.id == calendar.brand_id))
    brand = brand_res.scalar_one_or_none()

    cfg_res = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.brand_id == calendar.brand_id,
            AIProviderConfig.phase == PhaseEnum.CALENDAR,
        )
    )
    ai_config = cfg_res.scalar_one_or_none()
    if not ai_config:
        raise HTTPException(
            status_code=400,
            detail="No Calendar AI provider configured for this brand. Add one under AI Providers.",
        )

    current = {"summary": calendar.summary or "", "entries": calendar.entries or []}
    prompt = CAL_AI_EDIT_PROMPT.format(
        brand=brand.display_name if brand else "the brand",
        instruction=payload.instruction.strip(),
        calendar=json.dumps(current, ensure_ascii=False, indent=2),
    )
    provider = build_provider_from_config(
        provider_name=ai_config.provider.value,
        model=ai_config.model,
        encrypted_api_key=ai_config.api_key_enc,
    )
    n = len(current["entries"]) if isinstance(current["entries"], list) else 20
    response = await provider.complete(
        user_message=prompt,
        system_prompt=CAL_AI_EDIT_SYSTEM,
        temperature=ai_config.temperature,
        max_tokens=min(max(ai_config.max_tokens or 4096, n * 200 + 1200), 8000),
    )
    data = parse_ai_json(response.content)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="AI returned invalid JSON for the edited calendar.")
    entries = data.get("entries")
    if isinstance(entries, list):
        try:
            from phases.phase2_calendar import Phase2Calendar
            entries = Phase2Calendar._normalize_entries(entries)
        except Exception:  # noqa: BLE001 — normalization is best-effort
            pass
        calendar.entries = entries
        calendar.post_count = len(entries)
    if isinstance(data.get("summary"), str):
        calendar.summary = data["summary"]
    calendar.raw_ai_output = response.content
    calendar.is_approved = False
    calendar.is_rejected = False
    await db.flush()
    await db.refresh(calendar)
    return calendar
