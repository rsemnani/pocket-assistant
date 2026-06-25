"""Portable column types so the same models run on Postgres (prod) and SQLite (tests).

- GUID: stores UUIDs as native UUID on Postgres, as CHAR(32) hex on SQLite.
- JSONColumn: JSONB on Postgres, JSON elsewhere.
This lets unit tests run on in-memory SQLite with zero setup while production uses Postgres.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CHAR, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator[uuid.UUID]):
    """Platform-independent UUID type."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return value.hex if isinstance(value, uuid.UUID) else uuid.UUID(str(value)).hex

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def json_column() -> Any:
    """JSONB on Postgres, JSON elsewhere."""
    return JSON().with_variant(JSONB(), "postgresql")
