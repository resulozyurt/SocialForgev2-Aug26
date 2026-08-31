"""content_calendars.is_rejected + rejected_at (and guard content_packages)

Revision ID: 0009_calendar_package_rejected
Revises: 0008_report_rejected
Create Date: 2026-08-31

RV2a. Lets a human reject a calendar / content package (kept for audit, distinct
from delete), mirroring the report reject flow. Guarded + idempotent.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_calendar_package_rejected"
down_revision = "0008_report_rejected"
branch_labels = None
depends_on = None

_TABLES = ("content_calendars", "content_packages")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in _TABLES:
        if not insp.has_table(table):
            continue
        cols = [c["name"] for c in insp.get_columns(table)]
        if "is_rejected" not in cols:
            op.add_column(
                table,
                sa.Column("is_rejected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            )
        if "rejected_at" not in cols:
            op.add_column(
                table,
                sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in _TABLES:
        if not insp.has_table(table):
            continue
        cols = [c["name"] for c in insp.get_columns(table)]
        if "rejected_at" in cols:
            op.drop_column(table, "rejected_at")
        if "is_rejected" in cols:
            op.drop_column(table, "is_rejected")
