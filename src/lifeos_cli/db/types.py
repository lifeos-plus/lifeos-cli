"""SQLAlchemy storage types for LifeOS."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Persist datetimes in UTC and return UTC-aware values from every dialect."""

    impl = DateTime
    cache_ok = True

    @property
    def python_type(self) -> type[datetime]:
        """Return the Python value type used by this SQL type."""
        return datetime

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        """Use timezone-capable DateTime where the backend supports it."""
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        """Normalize bound values to UTC before persistence."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        """Restore UTC tzinfo for backends such as SQLite that drop offsets."""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
