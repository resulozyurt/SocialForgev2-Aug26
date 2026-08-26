"""initial schema (baseline)

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-26

Baseline migration. Builds the full schema straight from the ORM metadata so the
first revision can never drift from models/db_models.py. All later revisions are
produced with `alembic revision --autogenerate` and use explicit op.* calls.
"""

from __future__ import annotations

import os
import sys

from alembic import op

# Robust even if this file is imported outside the normal env.py path.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from core.database import Base           # noqa: E402
from models import db_models             # noqa: E402,F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
