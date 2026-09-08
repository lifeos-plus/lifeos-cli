"""Event model for planned schedule blocks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin
from lifeos_cli.db.types import UTCDateTime


class Event(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Planned calendar event that may optionally point to a task and area."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('appointment', 'timeblock', 'deadline')",
            name="ck_events_event_type_valid",
        ),
        CheckConstraint(
            "status IN ('planned', 'cancelled', 'completed')",
            name="status_valid",
        ),
        CheckConstraint(
            "priority BETWEEN 0 AND 5",
            name="priority_valid",
        ),
        CheckConstraint(
            "end_time IS NULL OR end_time >= start_time",
            name="time_range_valid",
        ),
        CheckConstraint(
            "recurrence_frequency IS NULL OR recurrence_frequency IN "
            "('daily', 'weekly', 'monthly', 'yearly')",
            name="recurrence_frequency_valid",
        ),
        CheckConstraint(
            "(recurrence_frequency IS NULL AND recurrence_interval IS NULL AND "
            "recurrence_count IS NULL AND recurrence_until IS NULL AND recurrence_rule IS NULL) OR "
            "(recurrence_frequency IS NOT NULL AND "
            "(recurrence_interval IS NULL OR recurrence_interval > 0) AND "
            "(recurrence_count IS NULL OR recurrence_count > 0))",
            name="recurrence_details_valid",
        ),
        Index("ix_events_status_start_time", "status", "start_time"),
        Index("ix_events_event_type", "event_type"),
        Index("ix_events_area_id", "area_id"),
        Index("ix_events_task_id", "task_id"),
        Index("ix_events_recurrence_parent_event_id", "recurrence_parent_event_id"),
        Index("ix_events_recurrence_instance_start", "recurrence_instance_start"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    end_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, default="appointment")
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrence_frequency: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    recurrence_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recurrence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recurrence_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True, index=True
    )
    recurrence_rule: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
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
    recurrence_parent_event_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
    )
    recurrence_instance_start: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    area = relationship("Area", foreign_keys=[area_id])
    task = relationship("Task", foreign_keys=[task_id])

    def __repr__(self) -> str:
        return (
            "Event("
            f"id={self.id!s}, title={self.title!r}, status={self.status!r}, "
            f"event_type={self.event_type!r})"
        )
