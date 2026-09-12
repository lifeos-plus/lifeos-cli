"""Read-only diagnostics for aggregates and recoverable soft-deleted references."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models import Event, Task, Vision
from lifeos_cli.db.models.event_occurrence_exception import EventOccurrenceException
from lifeos_cli.db.services.task_effort import expected_task_efforts
from lifeos_cli.db.services.visions import resolve_experience_rate_for_vision


async def audit_derived_data(session: AsyncSession) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Report effort errors and non-destructive experience/reference warnings."""
    expected = await expected_task_efforts(session)
    tasks = list((await session.scalars(select(Task))).all())
    projected_by_vision: dict[UUID, list[Task]] = defaultdict(list)
    issues = []
    for task in tasks:
        direct, total = expected[task.id]
        projected_by_vision[task.vision_id].append(
            Task(parent_task_id=task.parent_task_id, actual_effort_total=total)
        )
        if (task.actual_effort_self, task.actual_effort_total) != (direct, total):
            issues.append(
                f"Task {task.id}: effort self/total "
                f"{task.actual_effort_self}/{task.actual_effort_total}; expected {direct}/{total}."
            )
    warnings = []
    for vision in (await session.scalars(select(Vision))).all():
        points = vision.calculate_task_experience(
            experience_rate_per_hour=resolve_experience_rate_for_vision(vision),
            tasks=projected_by_vision[vision.id],
        )
        if vision.experience_points != points:
            warnings.append(
                f"Vision {vision.id}: experience {vision.experience_points}; "
                f"effort-derived {points}. Manual experience may explain the difference; "
                "use explicit vision sync-experience only if replacement is intended."
            )
    return tuple(issues), tuple(warnings)


async def audit_soft_deleted_references(session: AsyncSession) -> tuple[str, ...]:
    """Preserve recoverable links while making hidden ownership visible."""
    warnings = []
    for child, parent, field in (
        (Task.__table__, Vision.__table__, "vision_id"),
        (Event.__table__, Task.__table__, "task_id"),
        (EventOccurrenceException.__table__, Event.__table__, "master_event_id"),
    ):
        statement = (
            select(child.c.id)
            .join(parent, child.c[field] == parent.c.id)
            .where(child.c.deleted_at.is_(None), parent.c.deleted_at.is_not(None))
        )
        for record_id in (await session.scalars(statement)).all():
            warnings.append(
                f"{child.description} {record_id}: {field} references a soft-deleted "
                f"{parent.description} record; preserved as recoverable history."
            )
    return tuple(warnings)
