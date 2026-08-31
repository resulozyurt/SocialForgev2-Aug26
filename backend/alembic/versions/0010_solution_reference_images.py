"""solution reference images + brand_solutions.visual_notes

Revision ID: 0010_solution_reference_images
Revises: 0009_calendar_package_rejected
Create Date: 2026-08-31

V1 of the redesigned visual step. Adds:
  * brand_solutions.visual_notes (Text, nullable) — per-(brand,solution) style
    note fed into the image prompt.
  * solution_reference_images — uploaded example images per (brand, solution),
    downscaled on upload and stored in Postgres (BYTEA) to avoid new infra.

Reuses the existing `solutionenum` type (create_type=False). Fully guarded and
idempotent so re-runs on the live DB are safe.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_solution_reference_images"
down_revision = "0009_calendar_package_rejected"
branch_labels = None
depends_on = None

solution_enum = postgresql.ENUM(name="solutionenum", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) brand_solutions.visual_notes
    if insp.has_table("brand_solutions"):
        cols = [c["name"] for c in insp.get_columns("brand_solutions")]
        if "visual_notes" not in cols:
            op.add_column("brand_solutions", sa.Column("visual_notes", sa.Text(), nullable=True))

    # 2) solution_reference_images
    if not insp.has_table("solution_reference_images"):
        op.create_table(
            "solution_reference_images",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "brand_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("brands.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("solution", solution_enum, nullable=False),
            sa.Column("image_data", sa.LargeBinary(), nullable=False),
            sa.Column(
                "content_type",
                sa.String(length=64),
                nullable=False,
                server_default="image/png",
            ),
            sa.Column("filename", sa.String(length=255), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_solution_reference_images_brand_id",
            "solution_reference_images",
            ["brand_id"],
        )
        op.create_index(
            "ix_solution_reference_images_solution",
            "solution_reference_images",
            ["solution"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("solution_reference_images"):
        existing_idx = {i["name"] for i in insp.get_indexes("solution_reference_images")}
        if "ix_solution_reference_images_solution" in existing_idx:
            op.drop_index("ix_solution_reference_images_solution", table_name="solution_reference_images")
        if "ix_solution_reference_images_brand_id" in existing_idx:
            op.drop_index("ix_solution_reference_images_brand_id", table_name="solution_reference_images")
        op.drop_table("solution_reference_images")

    if insp.has_table("brand_solutions"):
        cols = [c["name"] for c in insp.get_columns("brand_solutions")]
        if "visual_notes" in cols:
            op.drop_column("brand_solutions", "visual_notes")
