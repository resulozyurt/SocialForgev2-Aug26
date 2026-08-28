"""trend_report_cards.is_rejected + rejected_at

Revision ID: 0008_report_rejected
Revises: 0007_competitor_solution
Create Date: 2026-08-27

E4a. Lets a human reject a report (kept for audit, distinct from delete). Guarded.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_report_rejected"
down_revision = "0007_competitor_solution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("trend_report_cards"):
        cols = [c["name"] for c in insp.get_columns("trend_report_cards")]
        if "is_rejected" not in cols:
            op.add_column(
                "trend_report_cards",
                sa.Column("is_rejected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            )
        if "rejected_at" not in cols:
            op.add_column(
                "trend_report_cards",
                sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("trend_report_cards"):
        cols = [c["name"] for c in insp.get_columns("trend_report_cards")]
        if "rejected_at" in cols:
            op.drop_column("trend_report_cards", "rejected_at")
        if "is_rejected" in cols:
            op.drop_column("trend_report_cards", "is_rejected")
