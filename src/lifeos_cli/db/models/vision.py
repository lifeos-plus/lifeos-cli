"""Vision model for high-level task tree containers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lifeos_cli.db.base import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from lifeos_cli.db.models.task import Task


class Vision(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """High-level container composed of one or more task trees."""

    __tablename__ = "visions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'fruit')",
            name="ck_visions_status_valid",
        ),
        CheckConstraint(
            "stage >= 0 AND experience_points >= 0",
            name="ck_visions_progress_nonnegative",
        ),
        CheckConstraint(
            "experience_rate_per_hour IS NULL OR experience_rate_per_hour > 0",
            name="ck_visions_experience_rate_positive",
        ),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    experience_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    experience_rate_per_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    area_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("areas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    area = relationship("Area", back_populates="visions")
    tasks = relationship("Task", back_populates="vision", cascade="all, delete-orphan")

    def calculate_task_experience(
        self,
        *,
        experience_rate_per_hour: int,
        tasks: list[Task] | None = None,
    ) -> int:
        """Calculate experience from root task actual effort totals."""
        selected_tasks = tasks if tasks is not None else []
        total_actual_effort = sum(
            task.actual_effort_total or 0 for task in selected_tasks if task.parent_task_id is None
        )
        if experience_rate_per_hour <= 0:
            return 0
        return (total_actual_effort * experience_rate_per_hour) // 60

    def _update_stage_based_on_experience(self) -> bool:
        """Update stage based on current experience points."""
        old_stage = self.stage
        stage_thresholds = [
            0,
            120,
            240,
            480,
            960,
            1920,
            3840,
            7680,
            15360,
            30720,
            61440,
        ]
        new_stage = 0
        for threshold in stage_thresholds:
            if self.experience_points >= threshold:
                new_stage += 1
            else:
                break
        self.stage = min(new_stage - 1, 10)
        return self.stage > old_stage

    def add_experience(self, points: int) -> bool:
        """Add experience points and return whether the stage evolved."""
        self.experience_points += points
        return self._update_stage_based_on_experience()

    def sync_experience_with_actual_effort(
        self,
        *,
        experience_rate_per_hour: int,
        tasks: list[Task] | None = None,
    ) -> bool:
        """Synchronize experience points from current root task effort totals."""
        new_experience = self.calculate_task_experience(
            experience_rate_per_hour=experience_rate_per_hour,
            tasks=tasks,
        )
        if new_experience != self.experience_points:
            self.experience_points = new_experience
            return self._update_stage_based_on_experience()
        return False

    def can_harvest(self) -> bool:
        """Return whether this active vision is ready to become a fruit."""
        return self.stage >= 7 and self.status == "active"

    def harvest(self) -> None:
        """Convert this vision into a fruit when it is ready."""
        if self.can_harvest():
            self.status = "fruit"

    def __repr__(self) -> str:
        return f"Vision(id={self.id!s}, name={self.name!r}, status={self.status!r})"
