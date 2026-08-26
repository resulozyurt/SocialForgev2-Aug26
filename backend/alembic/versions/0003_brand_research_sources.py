"""brand research_sources column

Revision ID: 0003_brand_research_sources
Revises: 0002_brand_solution_profile
Create Date: 2026-08-26

Phase C2. Adds brands.research_sources (JSONB, nullable): the per-brand RSS feed
list, Google Trends region, and Apify flag used by the free Phase 1 research
path. Inspector-guarded so it composes with the create_all baseline (see 0002).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_brand_research_sources"
down_revision = "0002_brand_solution_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    brand_cols = {c["name"] for c in insp.get_columns("brands")}
    if "research_sources" not in brand_cols:
        op.add_column(
            "brands",
            sa.Column("research_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    brand_cols = {c["name"] for c in insp.get_columns("brands")}
    if "research_sources" in brand_cols:
        op.drop_column("brands", "research_sources")
