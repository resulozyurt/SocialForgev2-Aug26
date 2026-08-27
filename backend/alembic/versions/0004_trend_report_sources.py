"""trend report sources column

Revision ID: 0004_trend_report_sources
Revises: 0003_brand_research_sources
Create Date: 2026-08-27

Phase R1. Adds trend_report_cards.sources (JSONB, nullable): the actual gathered
research inputs (Brave search results, RSS items, Google Trends) so each report
is auditable. Inspector-guarded to compose with the create_all baseline.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_trend_report_sources"
down_revision = "0003_brand_research_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("trend_report_cards")}
    if "sources" not in cols:
        op.add_column(
            "trend_report_cards",
            sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("trend_report_cards")}
    if "sources" in cols:
        op.drop_column("trend_report_cards", "sources")
