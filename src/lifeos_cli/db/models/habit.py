"""Habit model for recurring practices with on-demand dated occurrences."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class Habit(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """Recurring habit definition that materializes dated actions on demand."""

    __tablename__ = "habits"
    __table_args__ = (
        CheckConstraint(
            "duration_days BETWEEN 1 AND 10000",
            name="duration_days_valid",
        ),
        CheckConstraint(
            "target_per_cycle > 0",
            name="target_per_cycle_positive",
        ),
        CheckConstraint(
            "cadence_frequency IN ('daily', 'weekly', 'monthly', 'yearly')",
            name="cadence_frequency_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'paused', 'expired')",
            name="status_valid",
        ),
        Index("ix_habits_title", "title"),
        Index("ix_habits_start_date", "start_date"),
        Index("ix_habits_status", "status"),
        Index("ix_habits_task_id", "task_id"),
        Index("ix_habits_area_id", "area_id"),
        Index("ix_habits_cadence_frequency", "cadence_frequency"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    cadence_frequency: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    cadence_weekdays: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    cadence_monthdays: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    target_per_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    status_changed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    area_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("areas.id", ondelete="SET NULL"),
        nullable=True,
    )

    task = relationship("Task", foreign_keys=[task_id])
    area = relationship("Area", foreign_keys=[area_id])
    actions = relationship(
        "HabitAction",
        back_populates="habit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def end_date(self) -> date:
        """Return the computed final date covered by the habit."""
        return self.start_date + timedelta(days=self.duration_days - 1)

    def __repr__(self) -> str:
        return (
            f"Habit(id={self.id!s}, title={self.title!r}, "
            f"status={self.status!r}, duration_days={self.duration_days}, "
            f"cadence_frequency={self.cadence_frequency!r})"
        )
