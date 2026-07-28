"""Person activity timeline query helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person_association import person_associations
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision


@dataclass(frozen=True)
class PersonActivity:
    """One timestamped entity shown in a person's activity timeline."""

    id: UUID
    activity_type: str
    title: str
    description: str | None
    activity_date: datetime
    status: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    area_id: UUID | None = None


@dataclass(frozen=True)
class PersonActivityPage:
    """A page of person activity results and derived timelog metadata."""

    items: tuple[PersonActivity, ...]
    total: int
    timelog_count: int | None
    timelog_total_minutes: int | None


def _preview(value: str | None, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}..."


async def _load_person_entity_ids(
    session: AsyncSession,
    *,
    person_id: UUID,
) -> dict[str, list[UUID]]:
    rows = await session.execute(
        select(
            person_associations.c.entity_type,
            person_associations.c.entity_id,
        ).where(person_associations.c.person_id == person_id)
    )
    grouped: dict[str, list[UUID]] = {}
    for entity_type, entity_id in rows.all():
        grouped.setdefault(str(entity_type), []).append(entity_id)
    return grouped


async def _load_person_note_ids(session: AsyncSession, *, person_id: UUID) -> list[UUID]:
    rows = await session.execute(
        select(Association.source_id)
        .distinct()
        .where(
            Association.source_model == "note",
            Association.target_model == "person",
            Association.target_id == person_id,
            Association.link_type == "is_about",
        )
    )
    return list(rows.scalars().all())


async def _load_activity_items(
    session: AsyncSession,
    *,
    person_id: UUID,
    activity_filter: str | None,
) -> list[PersonActivity]:
    entity_ids = await _load_person_entity_ids(session, person_id=person_id)
    items: list[PersonActivity] = []

    if activity_filter in (None, "vision"):
        vision_ids = entity_ids.get("vision", [])
        if vision_ids:
            vision_rows = await session.execute(
                select(Vision).where(Vision.id.in_(vision_ids), Vision.deleted_at.is_(None))
            )
            items.extend(
                PersonActivity(
                    id=vision.id,
                    activity_type="vision",
                    title=vision.name,
                    description=_preview(vision.description),
                    activity_date=vision.updated_at,
                    status=vision.status,
                )
                for vision in vision_rows.scalars()
            )

    if activity_filter in (None, "task"):
        task_ids = entity_ids.get("task", [])
        if task_ids:
            task_rows = await session.execute(
                select(Task).where(Task.id.in_(task_ids), Task.deleted_at.is_(None))
            )
            items.extend(
                PersonActivity(
                    id=task.id,
                    activity_type="task",
                    title=task.content,
                    description=_preview(task.description),
                    activity_date=task.updated_at,
                    status=task.status,
                )
                for task in task_rows.scalars()
            )

    if activity_filter in (None, "planned_event"):
        event_ids = entity_ids.get("event", [])
        if event_ids:
            event_rows = await session.execute(
                select(Event).where(Event.id.in_(event_ids), Event.deleted_at.is_(None))
            )
            items.extend(
                PersonActivity(
                    id=event.id,
                    activity_type="planned_event",
                    title=event.title,
                    description=_preview(event.description),
                    activity_date=event.start_time,
                    status=event.status,
                )
                for event in event_rows.scalars()
            )

    if activity_filter in (None, "timelog"):
        timelog_ids = entity_ids.get("timelog", [])
        if timelog_ids:
            timelog_rows = await session.execute(
                select(Timelog).where(Timelog.id.in_(timelog_ids), Timelog.deleted_at.is_(None))
            )
            items.extend(
                PersonActivity(
                    id=timelog.id,
                    activity_type="timelog",
                    title=timelog.title,
                    description=None,
                    activity_date=timelog.start_time,
                    start_time=timelog.start_time,
                    end_time=timelog.end_time,
                    area_id=timelog.area_id,
                )
                for timelog in timelog_rows.scalars()
            )

    if activity_filter in (None, "note"):
        note_ids = await _load_person_note_ids(session, person_id=person_id)
        if note_ids:
            note_rows = await session.execute(
                select(Note).where(Note.id.in_(note_ids), Note.deleted_at.is_(None))
            )
            items.extend(
                PersonActivity(
                    id=note.id,
                    activity_type="note",
                    title=_preview(note.content) or "Note",
                    description=None,
                    activity_date=note.updated_at,
                )
                for note in note_rows.scalars()
            )

    return sorted(items, key=lambda item: item.activity_date.isoformat(), reverse=True)


def _timelog_total_minutes(items: list[PersonActivity]) -> int:
    total = 0
    for item in items:
        if item.activity_type != "timelog" or item.start_time is None or item.end_time is None:
            continue
        minutes = round((item.end_time - item.start_time).total_seconds() / 60)
        if minutes > 0:
            total += minutes
    return total


async def list_person_activities(
    session: AsyncSession,
    *,
    person_id: UUID,
    activity_filter: str | None,
    limit: int,
    offset: int,
) -> PersonActivityPage:
    """Load a page of activities while preserving the established timeline semantics."""
    all_items = await _load_activity_items(
        session,
        person_id=person_id,
        activity_filter=activity_filter,
    )
    return PersonActivityPage(
        items=tuple(all_items[offset : offset + limit]),
        total=len(all_items),
        timelog_count=len(all_items) if activity_filter == "timelog" else None,
        timelog_total_minutes=(
            _timelog_total_minutes(all_items) if activity_filter == "timelog" else None
        ),
    )
