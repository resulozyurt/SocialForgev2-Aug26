"""
api/routes/copy.py
Phase 3 — Content generation (copywriting) endpoints.
"""

from __future__ import annotations

import json
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
from models.db_models import (
    AIProviderConfig,
    Brand,
    ContentPackage,
    ContentStatusEnum,
    ContentTypeEnum,
    PhaseEnum,
    PlatformEnum,
    SolutionEnum,
)

router = APIRouter()


class CopyRunRequest(BaseModel):
    calendar_id: Optional[uuid.UUID] = None   # specific approved calendar; else latest approved
    limit: Optional[int] = None               # generate only first N entries (quick test)
    generate_tr: bool = True                  # also produce Turkish copy


class CopyRunResponse(BaseModel):
    message: str
    brand_id: str


class BulkDeletePayload(BaseModel):
    # Provide exactly one selector. package_ids = explicit selection; else delete all
    # packages for the brand under a planning_period or a source calendar_id.
    package_ids: Optional[list[uuid.UUID]] = None
    planning_period: Optional[str] = None
    calendar_id: Optional[uuid.UUID] = None


class ContentPackageResponse(BaseModel):
    id: uuid.UUID
    post_id: str
    brand_id: uuid.UUID
    platform: PlatformEnum
    content_type: ContentTypeEnum
    status: ContentStatusEnum
    is_rejected: bool = False
    solution: Optional[SolutionEnum] = None
    planning_period: Optional[str] = None
    calendar_id: Optional[uuid.UUID] = None
    scheduled_at: Optional[datetime] = None
    objective: Optional[str] = None
    trend_signal: Optional[str] = None
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
    package.is_rejected = False
    return {"message": "Content package approved.", "package_id": str(package_id)}


@router.patch("/copy/{package_id}/reject")
async def reject_package(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Human reject — keeps the package for audit but marks it dismissed and
    reverts it out of the approved state."""
    result = await db.execute(
        select(ContentPackage).where(ContentPackage.id == package_id)
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Content package not found.")
    package.is_rejected = True
    package.rejected_at = datetime.now(timezone.utc)
    if package.status == ContentStatusEnum.APPROVED:
        package.status = ContentStatusEnum.DRAFT
    return {"message": "Content package rejected.", "package_id": str(package_id)}


@router.post("/copy/{brand_id}/bulk-delete")
async def bulk_delete_packages(
    brand_id: uuid.UUID,
    payload: BulkDeletePayload,
    db: AsyncSession = Depends(get_db),
):
    """Delete many content packages at once. Selector precedence: explicit
    `package_ids` (scoped to this brand), else all packages for a `planning_period`,
    else all for a `calendar_id`. Returns how many were removed."""
    conditions = [ContentPackage.brand_id == brand_id]
    if payload.package_ids:
        conditions.append(ContentPackage.id.in_(payload.package_ids))
    elif payload.planning_period:
        conditions.append(ContentPackage.planning_period == payload.planning_period)
    elif payload.calendar_id:
        conditions.append(ContentPackage.calendar_id == payload.calendar_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide package_ids, planning_period, or calendar_id to delete.",
        )

    result = await db.execute(select(ContentPackage).where(*conditions))
    rows = result.scalars().all()
    count = 0
    try:
        for row in rows:
            await db.delete(row)
            count += 1
        await db.flush()
    except Exception as exc:  # noqa: BLE001 — surface the real reason to the client
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Could not delete packages: {exc}") from exc
    return {"message": f"Deleted {count} package(s).", "deleted": count}


@router.delete("/copy/{package_id}", status_code=204)
async def delete_package(package_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a content package. Idempotent: deleting an
    already-removed package is treated as success so a stale UI never sees a 404."""
    result = await db.execute(
        select(ContentPackage).where(ContentPackage.id == package_id)
    )
    package = result.scalar_one_or_none()
    if package is None:
        return
    try:
        await db.delete(package)
        await db.flush()
    except Exception as exc:  # noqa: BLE001 — surface the real reason to the client
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"Could not delete package: {exc}") from exc


class AiEditRequest(BaseModel):
    instruction: str


COPY_AI_EDIT_SYSTEM = (
    "You are revising an existing social content package for a brand based on a human "
    "editor's instruction. Apply the instruction precisely, keep everything else "
    "intact, and preserve each field's structure. Respond with valid JSON only — no "
    "preamble, no markdown. Inside JSON string values use single quotes, never raw "
    "double quotes."
)

COPY_AI_EDIT_PROMPT = """BRAND: {brand}

EDITOR INSTRUCTION:
{instruction}

CURRENT CONTENT PACKAGE (JSON):
{package}

Return the FULL revised package as a JSON object with exactly these keys:
"copy_en" (object), "copy_tr" (object), "visual_direction" (object),
"strategic_rationale" (string), "target_audience" (string). Keep copy_en and copy_tr
in the same shape they have now (hooks, caption, cta, hashtags, alt_text,
carousel_slides, thread). Keep visual_direction's fields (concept, mood,
color_palette, composition, image_prompt, text_overlay). Keep it on-brand and
specific; do not drop fields."""


@router.post("/copy/{package_id}/ai-edit", response_model=ContentPackageResponse)
async def ai_edit_package(
    package_id: uuid.UUID,
    payload: AiEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revise a content package with the Copy AI using a human instruction. Result is a
    fresh, unapproved draft."""
    if not payload.instruction.strip():
        raise HTTPException(status_code=422, detail="Instruction is required.")
    res = await db.execute(select(ContentPackage).where(ContentPackage.id == package_id))
    package = res.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=404, detail="Content package not found.")

    brand_res = await db.execute(select(Brand).where(Brand.id == package.brand_id))
    brand = brand_res.scalar_one_or_none()

    cfg_res = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.brand_id == package.brand_id,
            AIProviderConfig.phase == PhaseEnum.COPY,
        )
    )
    ai_config = cfg_res.scalar_one_or_none()
    if not ai_config:
        raise HTTPException(
            status_code=400,
            detail="No Copy AI provider configured for this brand. Add one under AI Providers.",
        )

    current = {
        "copy_en": package.copy_package_en or {},
        "copy_tr": package.copy_package_tr or {},
        "visual_direction": package.visual_direction or {},
        "strategic_rationale": package.strategic_rationale or "",
        "target_audience": package.target_audience or "",
    }
    prompt = COPY_AI_EDIT_PROMPT.format(
        brand=brand.display_name if brand else "the brand",
        instruction=payload.instruction.strip(),
        package=json.dumps(current, ensure_ascii=False, indent=2),
    )
    provider = build_provider_from_config(
        provider_name=ai_config.provider.value,
        model=ai_config.model,
        encrypted_api_key=ai_config.api_key_enc,
    )
    response = await provider.complete(
        user_message=prompt,
        system_prompt=COPY_AI_EDIT_SYSTEM,
        temperature=ai_config.temperature,
        max_tokens=max(ai_config.max_tokens or 4096, 4096),
    )
    data = parse_ai_json(response.content)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="AI returned invalid JSON for the edited package.")
    if data.get("copy_en") is not None:
        package.copy_package_en = data["copy_en"]
    if data.get("copy_tr") is not None:
        package.copy_package_tr = data["copy_tr"]
    if data.get("visual_direction") is not None:
        package.visual_direction = data["visual_direction"]
    if isinstance(data.get("strategic_rationale"), str):
        package.strategic_rationale = data["strategic_rationale"]
    if isinstance(data.get("target_audience"), str):
        package.target_audience = data["target_audience"]
    package.status = ContentStatusEnum.DRAFT
    package.is_rejected = False
    await db.flush()
    await db.refresh(package)
    return package
