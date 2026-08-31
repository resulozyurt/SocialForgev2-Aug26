"""content_packages.planning_period + calendar_id

Revision ID: 0012_pkg_calendar_link
Revises: 0011_content_package_solution
Create Date: 2026-08-31

B0. Links each content package to its source calendar and planning period so the
copy list can group by month and show provenance. Both nullable for legacy rows.
Guarded/idempotent.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# NOTE: revision id must be <= 32 chars (alembic_version.version_num is
# VARCHAR(32)). The descriptive filename is fine; the id below is the short form.
revision = "0012_pkg_calendar_link"
down_revision = "0011_content_package_solution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("content_packages"):
        return
    cols = [c["name"] for c in insp.get_columns("content_packages")]
    idx = {i["name"] for i in insp.get_indexes("content_packages")}

    if "planning_period" not in cols:
        op.add_column("content_packages", sa.Column("planning_period", sa.String(length=32), nullable=True))
        if "ix_content_packages_planning_period" not in idx:
            op.create_index("ix_content_packages_planning_period", "content_packages", ["planning_period"])

    if "calendar_id" not in cols:
        op.add_column(
            "content_packages",
            sa.Column("calendar_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        # FK is added guarded; some engines require a named constraint.
        op.create_foreign_key(
            "fk_content_packages_calendar_id",
            "content_packages",
            "content_calendars",
            ["calendar_id"],
            ["id"],
            ondelete="SET NULL",
        )
        idx2 = {i["name"] for i in insp.get_indexes("content_packages")}
        if "ix_content_packages_calendar_id" not in idx2:
            op.create_index("ix_content_packages_calendar_id", "content_packages", ["calendar_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("content_packages"):
        return
    idx = {i["name"] for i in insp.get_indexes("content_packages")}
    cols = [c["name"] for c in insp.get_columns("content_packages")]
    fks = {fk["name"] for fk in insp.get_foreign_keys("content_packages")}

    if "ix_content_packages_calendar_id" in idx:
        op.drop_index("ix_content_packages_calendar_id", table_name="content_packages")
    if "fk_content_packages_calendar_id" in fks:
        op.drop_constraint("fk_content_packages_calendar_id", "content_packages", type_="foreignkey")
    if "calendar_id" in cols:
        op.drop_column("content_packages", "calendar_id")
    if "ix_content_packages_planning_period" in idx:
        op.drop_index("ix_content_packages_planning_period", table_name="content_packages")
    if "planning_period" in cols:
        op.drop_column("content_packages", "planning_period")
