"""Timelog model for actual time records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime


class Timelog(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Actual time record describing what happened and when."""

    __tablename__ = "timelogs"
    __table_args__ = (
        CheckConstraint("end_time >= start_time", name="time_range_valid"),
        CheckConstraint(
            "tracking_method IN ('manual', 'automatic', 'imported')",
            name="tracking_method_valid",
        ),
        CheckConstraint(
            "energy_level IS NULL OR energy_level BETWEEN 1 AND 5",
            name="energy_level_valid",
        ),
        Index("ix_timelogs_task_id", "task_id"),
        Index("ix_timelogs_area_id", "area_id"),
        Index("ix_timelogs_tracking_method", "tracking_method"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    tracking_method: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    energy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("areas.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )

    area = relationship("Area", foreign_keys=[area_id])
    task = relationship("Task", foreign_keys=[task_id])

    def __repr__(self) -> str:
        return (
            f"Timelog(id={self.id!s}, title={self.title!r}, "
            f"tracking_method={self.tracking_method!r})"
        )
