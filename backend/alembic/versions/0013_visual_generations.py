"""visual_generations (image history)

Revision ID: 0013_visual_generations
Revises: 0012_pkg_calendar_link
Create Date: 2026-08-31

B3. Persists every generated visual (bytes in Postgres) so all runs stay
selectable, not just the latest. Guarded/idempotent. Revision id kept < 32 chars
(alembic_version.version_num is VARCHAR(32)).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_visual_generations"
down_revision = "0012_pkg_calendar_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("visual_generations"):
        op.create_table(
            "visual_generations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "package_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("content_packages.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("image_data", sa.LargeBinary(), nullable=False),
            sa.Column("content_type", sa.String(length=64), nullable=False, server_default="image/png"),
            sa.Column("used_references", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("reference_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("provider", sa.String(length=64), nullable=True),
            sa.Column("scene_prompt", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_visual_generations_package_id", "visual_generations", ["package_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("visual_generations"):
        idx = {i["name"] for i in insp.get_indexes("visual_generations")}
        if "ix_visual_generations_package_id" in idx:
            op.drop_index("ix_visual_generations_package_id", table_name="visual_generations")
        op.drop_table("visual_generations")
