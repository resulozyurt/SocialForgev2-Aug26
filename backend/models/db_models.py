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
    Integer, LargeBinary, String, Text, UniqueConstraint, func,
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


class BrandLanguageEnum(str, PyEnum):
    """Primary content language of a brand. Drives which copy package is the
    native one in Phase 3 (FieldPie -> EN, Evatro -> TR)."""
    EN = "en"
    TR = "tr"


class SolutionEnum(str, PyEnum):
    """The fixed set of product solution areas. Content is produced per
    solution area, so this taxonomy is read by every downstream phase."""
    MERCHANDISING = "merchandising"
    FIELD_AUDIT   = "field_audit"
    FIELD_SALES   = "field_sales"
    HOME_SERVICE  = "home_service"
    AI            = "ai"
    GENERAL       = "general"


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

    # ── Phase B: rich brand identity ─────────────────────────────────────────
    # Primary content language (queryable, drives Phase 3 language wiring).
    language: Mapped[BrandLanguageEnum] = mapped_column(
        Enum(BrandLanguageEnum), nullable=False,
        default=BrandLanguageEnum.EN, server_default="EN",
    )
    # Fast-evolving visual design spec kept as JSONB to avoid migration churn.
    # Shape: {
    #   "ground_color": "#FFFFFF",
    #   "block_color": "#0B1E3B",
    #   "pill": {"bg_color": "#E4002B", "text_color": "#FFFFFF", "shape": "rounded-full"},
    #   "logo": {"url": "...", "position": "top-left"},
    #   "motifs": ["half-circle pie graphic bottom-left", ...],
    #   "style_keywords": ["clean", "modern SaaS", ...],
    #   "reference_images": [{"url": "...", "note": "..."}]
    # }
    visual_identity: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Structured voice/tone spec. Shape: {
    #   "tone_keywords": ["clear", "reassuring"],
    #   "narrative_structure": "problem -> solution",
    #   "example_headlines": ["Photos Don't Fix Shelves. Actions Do."],
    #   "avoid": ["translated phrasing", "corporate fluff"]
    # }
    voice_profile: Mapped[Optional[dict]] = mapped_column(JSONB)
    # research_sources (Phase C2): {"rss_feeds": ["https://..."], "trends_geo":
    #   "US"|"TR", "use_apify": false}. When null, Phase 1 falls back to
    #   language-based defaults.
    research_sources: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    competitors: Mapped[list["Competitor"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    content_pillars: Mapped[list["ContentPillar"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    solutions: Mapped[list["BrandSolution"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    reference_images: Mapped[list["SolutionReferenceImage"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    ai_configs: Mapped[list["AIProviderConfig"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    content_packages: Mapped[list["ContentPackage"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    content_calendars: Mapped[list["ContentCalendar"]] = relationship(back_populates="brand", cascade="all, delete-orphan")
    month_boards: Mapped[list["MonthBoard"]] = relationship(back_populates="brand", cascade="all, delete-orphan")


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
    # E3: which solution area this competitor is tracked under (nullable = general).
    solution: Mapped[Optional[SolutionEnum]] = mapped_column(Enum(SolutionEnum), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

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


class BrandSolution(Base):
    """
    Phase B: which solution areas a brand covers, with per-brand focus flag,
    priority (lower = higher priority), and free-form concept notes describing
    how that solution is positioned for this brand. Unique per (brand, solution).
    """
    __tablename__ = "brand_solutions"
    __table_args__ = (UniqueConstraint("brand_id", "solution", name="uq_brand_solution"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    solution: Mapped[SolutionEnum] = mapped_column(Enum(SolutionEnum), nullable=False)
    is_focus: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    # E2: content-weight intensity (1-5). Drives the per-solution calendar split.
    importance: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    concept_notes: Mapped[Optional[str]] = mapped_column(Text)
    # V1: per-(brand,solution) visual style note fed into the image prompt at
    # generation time (kept separate from concept_notes, which is content-side).
    visual_notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="solutions")


class SolutionReferenceImage(Base):
    """
    V1: reference example images uploaded per (brand, solution). At visual
    generation time these are passed to the image model (gpt-image-1 edits) so a
    new post inherits the brand's proven style for that solution. Bytes are
    downscaled on upload (Pillow) and stored in Postgres to avoid new infra.
    Keyed by brand_id + solution (mirrors the Competitor pattern), independent of
    brand_solutions activation.
    """
    __tablename__ = "solution_reference_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    solution: Mapped[SolutionEnum] = mapped_column(Enum(SolutionEnum), nullable=False, index=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png", server_default="image/png")
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    note: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="reference_images")


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
    # V4: the solution area this post belongs to (carried from the calendar entry)
    # so the visual step can pull the matching reference library. Nullable for
    # legacy rows created before this column existed.
    solution: Mapped[Optional[SolutionEnum]] = mapped_column(Enum(SolutionEnum), nullable=True, index=True)
    # B0: link each package to its source calendar + period, so the UI can group by
    # month and show provenance ("which copy belongs where"). Nullable for legacy rows.
    planning_period: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    calendar_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_calendars.id", ondelete="SET NULL"), nullable=True, index=True
    )
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


class VisualGeneration(Base):
    """B3: image-generation history. Every generated candidate is persisted here
    (bytes in Postgres, like reference images) so all runs stay selectable — not
    just the latest run. The chosen one is tracked by
    `ContentPackage.asset_urls['selected_generation_id']`."""
    __tablename__ = "visual_generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_packages.id", ondelete="CASCADE"), index=True
    )
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png", server_default="image/png")
    used_references: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reference_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    scene_prompt: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrendReportCard(Base):
    __tablename__ = "trend_report_cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    planning_period: Mapped[str] = mapped_column(String(32), nullable=False)

    trending_topics: Mapped[Optional[dict]] = mapped_column(JSONB)
    hot_formats: Mapped[Optional[dict]] = mapped_column(JSONB)
    content_gaps: Mapped[Optional[dict]] = mapped_column(JSONB)
    algorithm_notes: Mapped[Optional[dict]] = mapped_column(JSONB)
    recommended_pillars: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_ai_output: Mapped[Optional[str]] = mapped_column(Text)
    # sources (Phase R1): the actual gathered inputs for traceability:
    #   {"search": [...], "rss": [...], "trends": [...]}
    sources: Mapped[Optional[dict]] = mapped_column(JSONB)

    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # E4a: human can reject a report (kept for audit, distinct from delete).
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContentCalendar(Base):
    """
    Phase 2 output: a monthly content calendar scaffolded from an APPROVED
    Trend Report Card. `entries` holds the planned posts (date, pillar,
    platform, content type, hook concept). Phase 3 later turns each entry
    into a full ContentPackage with copy and visuals.
    """
    __tablename__ = "content_calendars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    trend_report_card_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trend_report_cards.id", ondelete="SET NULL"), nullable=True, index=True
    )
    planning_period: Mapped[str] = mapped_column(String(32), nullable=False)

    post_count: Mapped[int] = mapped_column(Integer, default=0)
    platforms: Mapped[Optional[dict]] = mapped_column(JSONB)   # list[str]
    entries: Mapped[Optional[dict]] = mapped_column(JSONB)     # list[dict]
    summary: Mapped[Optional[str]] = mapped_column(Text)
    raw_ai_output: Mapped[Optional[str]] = mapped_column(Text)

    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="content_calendars")


class MonthBoard(Base):
    """
    F0: a first-class "month board" — the organizing unit for the whole pipeline.
    One board per (brand, planning_period); every stage (research -> calendar ->
    copy -> visual) is scoped to a board's period. Thin by design: the
    report/calendar/package chain already carries `planning_period`, so a board
    owns no content directly — it groups the month and holds its lifecycle
    (status/title/notes).
    """
    __tablename__ = "month_boards"
    __table_args__ = (
        UniqueConstraint("brand_id", "planning_period", name="uq_month_board_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    planning_period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(128))
    # active (in progress) | ready (all stages approved) | archived
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    brand: Mapped["Brand"] = relationship(back_populates="month_boards")


class AppSetting(Base):
    """
    Phase R1: platform-level settings (e.g. Brave / Apify API keys) managed from
    the in-app Settings page instead of server env vars. Secret values are
    Fernet-encrypted at rest, like per-brand provider keys.
    """
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_enc: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
