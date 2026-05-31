from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from models.db_models import Competitor

router = APIRouter()

class CompetitorCreate(BaseModel):
    name: str
    instagram_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None
    x_handle: Optional[str] = None
    is_aspirational: bool = False

class CompetitorResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    instagram_handle: Optional[str]
    linkedin_handle: Optional[str]
    x_handle: Optional[str]
    is_aspirational: bool

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