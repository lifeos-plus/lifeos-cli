"""Sleep segment model for dated sleep intervals."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime


class SleepSegment(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """One continuous sleep interval attributed to a local calendar date."""

    __tablename__ = "sleep_segments"
    __table_args__ = (
        Index("ix_sleep_segments_sleep_date", "sleep_date"),
        Index("ix_sleep_segments_start_at", "start_at"),
    )

    sleep_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            f"SleepSegment(id={self.id!s}, sleep_date={self.sleep_date!s}, "
            f"duration_minutes={self.duration_minutes!r})"
        )
