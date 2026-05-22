"""
models/db_models.py
Full database schema for SocialForge AI.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class PlatformEnum(str, PyEnum):
    INSTAGRAM = "instagram"
    LINKEDIN  = "linkedin"
    X         = "x"
    TIKTOK    = "tiktok"
    YOUTUBE   = "youtube"


class ContentTypeEnum(str, PyEnum):
    STATIC   = "static"
    CAROUSEL = "carousel"
    REEL     = "reel"
    STORY    = "story"
    THREAD   = "thread"


class ContentStatusEnum(str, PyEnum):
    DRAFT     = "draft"
    REVIEW    = "review"
    APPROVED  = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED    = "failed"


class PhaseEnum(str, PyEnum):
    RESEARCH = "phase1_research"
    CALENDAR = "phase2_calendar"
    COPY     = "phase3_copy"
    VISUAL   = "phase4_visual"
    PUBLISH  = "phase5_publish"
    METRICS  = "phase6_metrics"


class ProviderEnum(str, PyEnum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    GOOGLE    = "google"
    GROQ      = "groq"


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    primary_color: Mapped[Optional[str]] = mapped_column(String(7))
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7))
    accent_color: Mapped[Optional[str]] = mapped_column(String(7))
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    voice_guide_url: Mapped[Optional[str]] = mapped_column(Text)
    voice_guide_text: Mapped[Optional[str]] = mapped_column(Text)
    monthly_post_target: Mapped[int] = mapped_column(Integer, default=20)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    competitors: Mapped[list["Competitor"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    content_pillars: Mapped[list["ContentPillar"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    ai_configs: Mapped[list["AIProviderConfig"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    content_packages: Mapped[list["ContentPackage"]] = relationship(back_populates="brand", cascade="all, delete-orphan")


class Competitor(Base):
    __tablename__ = "competitors"
    __table_args__ = (UniqueConstraint("brand_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_aspirational: Mapped[bool] = mapped_column(Boolean, default=False)
    instagram_handle: Mapped[Optional[str]] = mapped_column(String(64))
    linkedin_handle: Mapped[Optional[str]] = mapped_column(String(128))
    x_handle: Mapped[Optional[str]] = mapped_column(String(64))

    brand: Mapped["Brand"] = relationship(back_populates="competitors")


class ContentPillar(Base):
    __tablename__ = "content_pillars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    brand: Mapped["Brand"] = relationship(back_populates="content_pillars")


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (UniqueConstraint("brand_id", "phase"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    phase: Mapped[PhaseEnum] = mapped_column(Enum(PhaseEnum), nullable=False)
    provider: Mapped[ProviderEnum] = mapped_column(Enum(ProviderEnum), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_enc: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="ai_configs")


class ContentPackage(Base):
    __tablename__ = "content_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)

    platform: Mapped[PlatformEnum] = mapped_column(Enum(PlatformEnum), nullable=False)
    content_type: Mapped[ContentTypeEnum] = mapped_column(Enum(ContentTypeEnum), nullable=False)
    status: Mapped[ContentStatusEnum] = mapped_column(Enum(ContentStatusEnum), default=ContentStatusEnum.DRAFT, index=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)

    trend_signal: Mapped[Optional[str]] = mapped_column(Text)
    objective: Mapped[Optional[str]] = mapped_column(String(64))
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    strategic_rationale: Mapped[Optional[str]] = mapped_column(Text)

    copy_package_en: Mapped[Optional[dict]] = mapped_column(JSONB)
    copy_package_tr: Mapped[Optional[dict]] = mapped_column(JSONB)
    visual_direction: Mapped[Optional[dict]] = mapped_column(JSONB)
    asset_urls: Mapped[Optional[dict]] = mapped_column(JSONB)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(256))
    publish_error: Mapped[Optional[str]] = mapped_column(Text)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="content_packages")