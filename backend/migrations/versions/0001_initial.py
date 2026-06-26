"""initial baseline schema

Creates the full schema from the SQLAlchemy metadata so the baseline is dialect-portable
(Postgres in production, SQLite in tests). Subsequent migrations should be authored with
`alembic revision --autogenerate` and contain explicit operations.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from pocket.db import models  # noqa: F401  -- register models on metadata
from pocket.db.base import Base

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
