"""app_settings table

Revision ID: 0005_app_settings
Revises: 0004_trend_report_sources
Create Date: 2026-08-27

Phase R1. Platform-level settings (Brave / Apify keys) managed from the in-app
Settings page. Values are Fernet-encrypted. Inspector-guarded.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_app_settings"
down_revision = "0004_trend_report_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("app_settings"):
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("value_enc", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("app_settings"):
        op.drop_table("app_settings")
