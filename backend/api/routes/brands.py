"""
api/routes/brands.py
Brand management endpoints — create, read, update, deactivate.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.db_models import Brand

router = APIRouter()


class BrandCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    industry: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    voice_guide_url: Optional[str] = None
    monthly_post_target: int = Field(default=20, ge=1, le=200)


class BrandResponse(BaseModel):
    id: uuid.UUID
    slug: str
    display_name: str
    industry: Optional[str]
    is_active: bool
    primary_color: Optional[str]
    secondary_color: Optional[str]
    accent_color: Optional[str]
    logo_url: Optional[str]
    voice_guide_url: Optional[str]
    monthly_post_target: int

    class Config:
        from_attributes = True


@router.get("/brands", response_model=list[BrandResponse])
async def list_brands(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.is_active == True))
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


@router.delete("/brands/{brand_id}", status_code=204)
async def deactivate_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found.")
    brand.is_active = False