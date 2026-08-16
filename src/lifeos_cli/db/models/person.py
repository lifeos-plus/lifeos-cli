"""Person model for social relationships and person context."""

from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Person(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """A person in the user's social graph."""

    __tablename__ = "people"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    nicknames: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"Person(id={self.id!s}, name={self.name!r})"
