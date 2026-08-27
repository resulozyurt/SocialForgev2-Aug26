"""
api/routes/brands.py
Brand management endpoints — create, read, update, deactivate, plus per-brand
solution-focus management (Phase B).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import Brand, BrandLanguageEnum, BrandSolution, SolutionEnum

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Brand schemas
# ─────────────────────────────────────────────────────────────────────────────

class BrandCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    industry: Optional[str] = None
    language: BrandLanguageEnum = BrandLanguageEnum.EN
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    voice_guide_url: Optional[str] = None
    voice_guide_text: Optional[str] = None
    visual_identity: Optional[dict[str, Any]] = None
    voice_profile: Optional[dict[str, Any]] = None
    research_sources: Optional[dict[str, Any]] = None
    monthly_post_target: int = Field(default=20, ge=1, le=200)


class BrandUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    industry: Optional[str] = None
    language: Optional[BrandLanguageEnum] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    voice_guide_url: Optional[str] = None
    voice_guide_text: Optional[str] = None
    visual_identity: Optional[dict[str, Any]] = None
    voice_profile: Optional[dict[str, Any]] = None
    research_sources: Optional[dict[str, Any]] = None
    monthly_post_target: Optional[int] = Field(default=None, ge=1, le=200)
    is_active: Optional[bool] = None


class BrandResponse(BaseModel):
    id: uuid.UUID
    slug: str
    display_name: str
    industry: Optional[str]
    is_active: bool
    language: BrandLanguageEnum
    primary_color: Optional[str]
    secondary_color: Optional[str]
    accent_color: Optional[str]
    logo_url: Optional[str]
    voice_guide_url: Optional[str]
    voice_guide_text: Optional[str]
    visual_identity: Optional[dict[str, Any]]
    voice_profile: Optional[dict[str, Any]]
    research_sources: Optional[dict[str, Any]]
    monthly_post_target: int

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Solution-focus schemas
# ─────────────────────────────────────────────────────────────────────────────

class SolutionItem(BaseModel):
    solution: SolutionEnum
    is_focus: bool = True
    priority: int = Field(default=100, ge=0)
    importance: int = Field(default=3, ge=1, le=5)
    concept_notes: Optional[str] = None


class SolutionResponse(BaseModel):
    id: uuid.UUID
    solution: SolutionEnum
    is_focus: bool
    priority: int
    importance: int
    concept_notes: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# Brand endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/brands", response_model=list[BrandResponse])
async def list_brands(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.is_active == True))  # noqa: E712
    return result.scalars().all()


@router.post("/brands", response_model=BrandResponse, status_code=201)
async def create_brand(payload: BrandCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Brand).where(Brand.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Brand '{payload.slug}' already exists.")

    brand = Brand(**payload.model_dump())
    db.add(brand)
    await db.flush()
    await db.refresh(brand)
    return brand


@router.get("/brands/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")
    return brand


@router.patch("/brands/{brand_id}", response_model=BrandResponse)
async def update_brand(brand_id: uuid.UUID, payload: BrandUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    await db.flush()
    await db.refresh(brand)
    return brand


@router.delete("/brands/{brand_id}", status_code=204)
async def deactivate_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")
    brand.is_active = False


# ─────────────────────────────────────────────────────────────────────────────
# Solution-focus endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/brands/{brand_id}/solutions", response_model=list[SolutionResponse])
async def list_brand_solutions(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BrandSolution)
        .where(BrandSolution.brand_id == brand_id)
        .order_by(BrandSolution.priority)
    )
    return result.scalars().all()


@router.put("/brands/{brand_id}/solutions", response_model=list[SolutionResponse])
async def set_brand_solutions(
    brand_id: uuid.UUID,
    payload: list[SolutionItem],
    db: AsyncSession = Depends(get_db),
):
    """
    Upsert the given solution focuses for a brand (non-destructive: solutions
    not listed are left untouched rather than deleted). Uniqueness is per
    (brand, solution).
    """
    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    if not brand_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Brand not found.")

    existing_result = await db.execute(
        select(BrandSolution).where(BrandSolution.brand_id == brand_id)
    )
    existing = {row.solution: row for row in existing_result.scalars().all()}

    for item in payload:
        row = existing.get(item.solution)
        if row:
            row.is_focus = item.is_focus
            row.priority = item.priority
            row.importance = item.importance
            row.concept_notes = item.concept_notes
            row.is_active = True
        else:
            db.add(
                BrandSolution(
                    brand_id=brand_id,
                    solution=item.solution,
                    is_focus=item.is_focus,
                    priority=item.priority,
                    importance=item.importance,
                    concept_notes=item.concept_notes,
                )
            )
    await db.flush()

    refreshed = await db.execute(
        select(BrandSolution)
        .where(BrandSolution.brand_id == brand_id)
        .order_by(BrandSolution.priority)
    )
    return refreshed.scalars().all()


@router.delete("/brands/{brand_id}/solutions/{solution}", status_code=204)
async def delete_brand_solution(
    brand_id: uuid.UUID,
    solution: SolutionEnum,
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a single solution focus from a brand (E2 'remove')."""
    result = await db.execute(
        select(BrandSolution).where(
            BrandSolution.brand_id == brand_id,
            BrandSolution.solution == solution,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Solution not found for this brand.")
    await db.delete(row)
