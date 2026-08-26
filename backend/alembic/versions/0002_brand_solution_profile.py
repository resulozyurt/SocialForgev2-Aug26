"""brand rich profile + solution taxonomy

Revision ID: 0002_brand_solution_profile
Revises: 0001_initial
Create Date: 2026-08-26

Phase B. Adds:
  * brands.language          (enum brandlanguageenum: EN/TR, default EN)
  * brands.visual_identity   (JSONB, nullable)
  * brands.voice_profile     (JSONB, nullable)
  * brand_solutions table    (per-brand solution focus, enum solutionenum)

IMPORTANT — why every op is guarded with an inspector check:
The baseline (0001) builds the schema with `Base.metadata.create_all`, which
reflects the *current* ORM models. On a fresh database, 0001 therefore already
creates the columns/table/enum types added here, and this revision must be a
no-op. On a database that was stamped at 0001 with the *previous* models, this
revision does the real work. The guards make both paths converge safely.

Enum labels intentionally use the Python member NAMES (EN, MERCHANDISING, ...),
because SQLAlchemy's Enum() persists member names by default — this is what
create_all emits, so the hand-written type here matches it exactly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_brand_solution_profile"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


LANG_LABELS = ("EN", "TR")
SOLUTION_LABELS = (
    "MERCHANDISING",
    "FIELD_AUDIT",
    "FIELD_SALES",
    "HOME_SERVICE",
    "AI",
    "GENERAL",
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Enum types (checkfirst so a fresh DB where create_all already made them
    # does not error).
    postgresql.ENUM(*LANG_LABELS, name="brandlanguageenum").create(bind, checkfirst=True)
    postgresql.ENUM(*SOLUTION_LABELS, name="solutionenum").create(bind, checkfirst=True)

    # Reference the existing types without re-emitting CREATE TYPE.
    lang_type = postgresql.ENUM(*LANG_LABELS, name="brandlanguageenum", create_type=False)
    solution_type = postgresql.ENUM(*SOLUTION_LABELS, name="solutionenum", create_type=False)

    brand_cols = {c["name"] for c in insp.get_columns("brands")}
    if "language" not in brand_cols:
        op.add_column(
            "brands",
            sa.Column("language", lang_type, nullable=False, server_default="EN"),
        )
    if "visual_identity" not in brand_cols:
        op.add_column(
            "brands",
            sa.Column("visual_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "voice_profile" not in brand_cols:
        op.add_column(
            "brands",
            sa.Column("voice_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    if not insp.has_table("brand_solutions"):
        op.create_table(
            "brand_solutions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("solution", solution_type, nullable=False),
            sa.Column("is_focus", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("concept_notes", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("brand_id", "solution", name="uq_brand_solution"),
        )
        op.create_index("ix_brand_solutions_brand_id", "brand_solutions", ["brand_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("brand_solutions"):
        existing_indexes = {ix["name"] for ix in insp.get_indexes("brand_solutions")}
        if "ix_brand_solutions_brand_id" in existing_indexes:
            op.drop_index("ix_brand_solutions_brand_id", table_name="brand_solutions")
        op.drop_table("brand_solutions")

    brand_cols = {c["name"] for c in insp.get_columns("brands")}
    for col in ("voice_profile", "visual_identity", "language"):
        if col in brand_cols:
            op.drop_column("brands", col)

    postgresql.ENUM(name="solutionenum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="brandlanguageenum").drop(bind, checkfirst=True)
