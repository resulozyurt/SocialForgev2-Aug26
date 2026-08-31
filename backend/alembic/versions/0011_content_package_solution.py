"""content_packages.solution

Revision ID: 0011_content_package_solution
Revises: 0010_solution_reference_images
Create Date: 2026-08-31

V4a. Tags each content package with the solution area it belongs to (carried from
the calendar entry), so Phase-4 visual generation can pull the matching reference
library. Nullable for legacy rows. Reuses the existing `solutionenum` type
(create_type=False). Guarded/idempotent.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_content_package_solution"
down_revision = "0010_solution_reference_images"
branch_labels = None
depends_on = None

solution_enum = postgresql.ENUM(name="solutionenum", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("content_packages"):
        cols = [c["name"] for c in insp.get_columns("content_packages")]
        if "solution" not in cols:
            op.add_column("content_packages", sa.Column("solution", solution_enum, nullable=True))
            existing_idx = {i["name"] for i in insp.get_indexes("content_packages")}
            if "ix_content_packages_solution" not in existing_idx:
                op.create_index(
                    "ix_content_packages_solution", "content_packages", ["solution"]
                )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("content_packages"):
        existing_idx = {i["name"] for i in insp.get_indexes("content_packages")}
        if "ix_content_packages_solution" in existing_idx:
            op.drop_index("ix_content_packages_solution", table_name="content_packages")
        cols = [c["name"] for c in insp.get_columns("content_packages")]
        if "solution" in cols:
            op.drop_column("content_packages", "solution")
