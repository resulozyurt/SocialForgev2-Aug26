"""month_boards (month-board spine)

Revision ID: 0014_month_boards
Revises: 0013_visual_generations
Create Date: 2026-09-01

F0. A thin, first-class "month board" — one per (brand, planning_period) — that
becomes the organizing unit for the whole pipeline. Owns no content directly:
the report/calendar/package chain already carries `planning_period`, so a board
just groups the month and holds its lifecycle (status/title/notes).

Guarded/idempotent. Revision id kept < 32 chars (alembic_version.version_num is
VARCHAR(32)).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_month_boards"
down_revision = "0013_visual_generations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("month_boards"):
        op.create_table(
            "month_boards",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "brand_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("brands.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("planning_period", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("brand_id", "planning_period", name="uq_month_board_period"),
        )
        op.create_index("ix_month_boards_brand_id", "month_boards", ["brand_id"])
        op.create_index("ix_month_boards_planning_period", "month_boards", ["planning_period"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("month_boards"):
        idx = {i["name"] for i in insp.get_indexes("month_boards")}
        for name in ("ix_month_boards_planning_period", "ix_month_boards_brand_id"):
            if name in idx:
                op.drop_index(name, table_name="month_boards")
        op.drop_table("month_boards")
