"""competitors.solution + notes

Revision ID: 0007_competitor_solution
Revises: 0006_solution_importance
Create Date: 2026-08-27

E3. Tags each competitor with a solution area (nullable) and adds free-form
notes. Reuses the existing `solutionenum` type (create_type=False). Guarded.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_competitor_solution"
down_revision = "0006_solution_importance"
branch_labels = None
depends_on = None

solution_enum = postgresql.ENUM(name="solutionenum", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("competitors"):
        cols = [c["name"] for c in insp.get_columns("competitors")]
        if "solution" not in cols:
            op.add_column("competitors", sa.Column("solution", solution_enum, nullable=True))
        if "notes" not in cols:
            op.add_column("competitors", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("competitors"):
        cols = [c["name"] for c in insp.get_columns("competitors")]
        if "notes" in cols:
            op.drop_column("competitors", "notes")
        if "solution" in cols:
            op.drop_column("competitors", "solution")
