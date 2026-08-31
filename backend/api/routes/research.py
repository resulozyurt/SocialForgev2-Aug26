"""
api/routes/research.py
Phase 1 — Competitive intelligence endpoints.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai_provider import build_provider_from_config
from core.config import get_settings
from core.database import get_db
from models.db_models import AIProviderConfig, Brand, PhaseEnum, TrendReportCard

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
    is_rejected: bool = False
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

    from core.job_status import start_job, finish_job, fail_job, log_step
    job_key = f"research:{brand_id}"
    start_job(job_key, "Starting research…")

    async def _run():
        from phases.phase1_research import Phase1Research
        try:
            runner = Phase1Research(
                apify_key=apify_key,
                search_provider=search_provider,
                search_key=search_key,
            )
            await runner.run(
                brand_id=str(brand_id),
                planning_period=payload.planning_period,
                max_posts_per_competitor=payload.max_posts,
                progress=lambda m: log_step(job_key, m),
            )
            finish_job(job_key, "Research complete — draft ready to review.")
        except Exception as exc:  # noqa: BLE001 — surface the real reason to the UI
            fail_job(job_key, str(exc))

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


class ResearchStatusResponse(BaseModel):
    status: str = "idle"      # idle | running | done | error
    message: str = ""
    log: list = []


@router.get("/research/{brand_id}/status", response_model=ResearchStatusResponse)
async def research_status(brand_id: uuid.UUID):
    """Most recent background research-run status + real step log for a brand."""
    from core.job_status import get_job
    job = get_job(f"research:{brand_id}")
    if not job:
        return ResearchStatusResponse()
    return ResearchStatusResponse(**job)


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
    report.is_rejected = False
    report.approved_at = datetime.now(timezone.utc)
    return {"message": "Report approved.", "report_id": str(report_id)}


# ── E4a: reject / delete / AI-edit ───────────────────────────────────────────

AI_EDIT_SYSTEM = (
    "You are revising an existing Trend Report Card for a brand based on a human "
    "editor's instruction. Apply the instruction precisely, keep everything else "
    "intact, and preserve each field's structure. Respond with valid JSON only — "
    "no preamble, no markdown."
)

AI_EDIT_PROMPT = """BRAND: {brand}

EDITOR INSTRUCTION:
{instruction}

CURRENT REPORT (JSON):
{report}

Return the FULL revised report as a JSON object with exactly these keys:
"trending_topics" (list), "hot_formats" (list), "content_gaps" (list),
"algorithm_notes" (object), "recommended_pillars" (list). Keep the content specific
and grounded; do not invent sources."""

_REPORT_KEYS = ["trending_topics", "hot_formats", "content_gaps", "algorithm_notes", "recommended_pillars"]


def _parse_report_json(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise HTTPException(status_code=502, detail="AI returned invalid JSON for the edited report.")


class AiEditRequest(BaseModel):
    instruction: str


async def _get_report(report_id: uuid.UUID, db: AsyncSession) -> TrendReportCard:
    result = await db.execute(select(TrendReportCard).where(TrendReportCard.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.patch("/research/reports/{report_id}/reject")
async def reject_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Human reject — keeps the report for audit but marks it dismissed."""
    report = await _get_report(report_id, db)
    report.is_rejected = True
    report.is_approved = False
    report.rejected_at = datetime.now(timezone.utc)
    return {"message": "Report rejected.", "report_id": str(report_id)}


@router.delete("/research/reports/{report_id}", status_code=204)
async def delete_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a Trend Report Card. Idempotent: deleting an
    already-removed report is treated as success, so a stale UI never sees a 404.
    Any real delete failure surfaces a clear message instead of a bare 500."""
    result = await db.execute(select(TrendReportCard).where(TrendReportCard.id == report_id))
    report = result.scalar_one_or_none()
    if report is None:
        return  # already gone — the desired end state is reached
    try:
        await db.delete(report)
        await db.flush()
    except Exception as exc:  # noqa: BLE001 — surface the real reason to the client
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Could not delete report: {exc}",
        ) from exc


@router.post("/research/reports/{report_id}/ai-edit", response_model=TrendReportResponse)
async def ai_edit_report(
    report_id: uuid.UUID,
    payload: AiEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revise a report with the Research AI using a human instruction (whole report
    or a specific area, driven by the instruction text). Result is a fresh, unapproved
    draft."""
    if not payload.instruction.strip():
        raise HTTPException(status_code=422, detail="Instruction is required.")
    report = await _get_report(report_id, db)

    brand_res = await db.execute(select(Brand).where(Brand.id == report.brand_id))
    brand = brand_res.scalar_one_or_none()

    cfg_res = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.brand_id == report.brand_id,
            AIProviderConfig.phase == PhaseEnum.RESEARCH,
        )
    )
    ai_config = cfg_res.scalar_one_or_none()
    if not ai_config:
        raise HTTPException(
            status_code=400,
            detail="No Research AI provider configured for this brand. Add one under AI Providers.",
        )

    current = {
        "trending_topics": report.trending_topics or [],
        "hot_formats": report.hot_formats or [],
        "content_gaps": report.content_gaps or [],
        "algorithm_notes": report.algorithm_notes or {},
        "recommended_pillars": report.recommended_pillars or [],
    }
    prompt = AI_EDIT_PROMPT.format(
        brand=brand.display_name if brand else "the brand",
        instruction=payload.instruction.strip(),
        report=json.dumps(current, ensure_ascii=False, indent=2),
    )
    provider = build_provider_from_config(
        provider_name=ai_config.provider.value,
        model=ai_config.model,
        encrypted_api_key=ai_config.api_key_enc,
    )
    response = await provider.complete(
        user_message=prompt,
        system_prompt=AI_EDIT_SYSTEM,
        temperature=ai_config.temperature,
        max_tokens=max(ai_config.max_tokens or 4096, 4096),
    )
    data = _parse_report_json(response.content)
    for key in _REPORT_KEYS:
        if data.get(key) is not None:
            setattr(report, key, data[key])
    report.raw_ai_output = response.content
    report.is_approved = False
    report.is_rejected = False
    await db.flush()
    await db.refresh(report)
    return report