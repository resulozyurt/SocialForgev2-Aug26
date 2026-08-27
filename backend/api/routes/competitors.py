from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from models.db_models import Competitor, SolutionEnum

router = APIRouter()


class CompetitorCreate(BaseModel):
    name: str
    solution: Optional[SolutionEnum] = None
    instagram_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None
    x_handle: Optional[str] = None
    is_aspirational: bool = False
    notes: Optional[str] = None


class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    solution: Optional[SolutionEnum] = None
    instagram_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None
    x_handle: Optional[str] = None
    is_aspirational: Optional[bool] = None
    notes: Optional[str] = None


class CompetitorResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    solution: Optional[SolutionEnum]
    instagram_handle: Optional[str]
    linkedin_handle: Optional[str]
    x_handle: Optional[str]
    is_aspirational: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.get("/brands/{brand_id}/competitors", response_model=list[CompetitorResponse])
async def list_competitors(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Competitor).where(Competitor.brand_id == brand_id))
    return result.scalars().all()


@router.post("/brands/{brand_id}/competitors", response_model=CompetitorResponse, status_code=201)
async def create_competitor(brand_id: uuid.UUID, payload: CompetitorCreate, db: AsyncSession = Depends(get_db)):
    competitor = Competitor(brand_id=brand_id, **payload.model_dump())
    db.add(competitor)
    await db.flush()
    await db.refresh(competitor)
    return competitor


@router.patch("/brands/{brand_id}/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    brand_id: uuid.UUID,
    competitor_id: uuid.UUID,
    payload: CompetitorUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id,
            Competitor.brand_id == brand_id,
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(competitor, field, value)
    await db.flush()
    await db.refresh(competitor)
    return competitor


@router.delete("/brands/{brand_id}/competitors/{competitor_id}", status_code=204)
async def delete_competitor(
    brand_id: uuid.UUID,
    competitor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id,
            Competitor.brand_id == brand_id,
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found.")
    await db.delete(competitor)
