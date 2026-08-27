"""brand_solutions.importance

Revision ID: 0006_solution_importance
Revises: 0005_app_settings
Create Date: 2026-08-27

E2. Adds an `importance` intensity (1-5, default 3) to brand_solutions so the
Phase 2 calendar splits the month across solutions by weight. Inspector-guarded.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_solution_importance"
down_revision = "0005_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("brand_solutions"):
        cols = [c["name"] for c in insp.get_columns("brand_solutions")]
        if "importance" not in cols:
            op.add_column(
                "brand_solutions",
                sa.Column("importance", sa.Integer(), server_default="3", nullable=False),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("brand_solutions"):
        cols = [c["name"] for c in insp.get_columns("brand_solutions")]
        if "importance" in cols:
            op.drop_column("brand_solutions", "importance")
