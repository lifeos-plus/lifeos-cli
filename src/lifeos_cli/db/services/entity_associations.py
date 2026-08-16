"""Helpers for generic weak entity-to-entity associations."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from lifeos_cli.db.models.association import (
    ASSOCIATION_MODEL_MAP,
    ASSOCIATION_SOURCE_MODELS,
    ASSOCIATION_TARGET_MODELS,
    VALID_ASSOCIATION_LINK_TYPES,
    Association,
)
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.habit_action import HabitAction
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.validation_utils import DomainValidationError, choice_validator

MODEL_MAP = ASSOCIATION_MODEL_MAP


class AssociationValidationError(DomainValidationError):
    """Raised when a weak-association input is invalid."""


_validate_association_source = choice_validator(
    ASSOCIATION_SOURCE_MODELS,
    error_cls=AssociationValidationError,
    label="association model",
    error_verb="Unsupported",
)

_validate_association_target = choice_validator(
    ASSOCIATION_TARGET_MODELS,
    error_cls=AssociationValidationError,
    label="association target model",
    error_verb="Unsupported",
)

_validate_association_link_type = choice_validator(
    VALID_ASSOCIATION_LINK_TYPES,
    error_cls=AssociationValidationError,
    label="association link type",
    error_verb="Unsupported",
)


async def _load_existing_ids(
    session: AsyncSession,
    *,
    model_name: str,
    identifiers: list[UUID],
) -> set[UUID]:
    if not identifiers:
        return set()
    model_cls = MODEL_MAP[model_name]
    stmt = select(model_cls.id).where(model_cls.id.in_(identifiers), model_cls.deleted_at.is_(None))
    rows = await session.execute(stmt)
    return set(rows.scalars().all())


async def set_association_links(
    session: AsyncSession,
    *,
    source_model: str,
    source_id: UUID,
    target_model: str,
    target_ids: list[UUID],
    link_type: str,
    replace: bool = True,
) -> None:
    """Create or replace weak links after validating both endpoints exist."""
    normalized_source_model = _validate_association_source(source_model)
    normalized_target_model = _validate_association_target(target_model)
    normalized_link_type = _validate_association_link_type(link_type)
    unique_target_ids = deduplicate_preserving_order(target_ids)

    if source_id not in await _load_existing_ids(
        session,
        model_name=normalized_source_model,
        identifiers=[source_id],
    ):
        raise LookupError(
            f"Unknown source ID for association {normalized_source_model}: {source_id}"
        )

    existing_target_ids = await _load_existing_ids(
        session,
        model_name=normalized_target_model,
        identifiers=unique_target_ids,
    )
    missing_target_ids = [
        str(target_id) for target_id in unique_target_ids if target_id not in existing_target_ids
    ]
    if missing_target_ids:
        raise LookupError(
            "Unknown target IDs for association "
            f"{normalized_source_model}->{normalized_target_model}: {', '.join(missing_target_ids)}"
        )

    if replace:
        await session.execute(
            delete(Association).where(
                Association.source_model == normalized_source_model,
                Association.source_id == source_id,
                Association.target_model == normalized_target_model,
                Association.link_type == normalized_link_type,
            )
        )

    existing_links: set[UUID] = set()
    if existing_target_ids and not replace:
        stmt = select(Association.target_id).where(
            Association.source_model == normalized_source_model,
            Association.source_id == source_id,
            Association.target_model == normalized_target_model,
            Association.target_id.in_(existing_target_ids),
            Association.link_type == normalized_link_type,
        )
        rows = await session.execute(stmt)
        existing_links = set(rows.scalars().all())

    for target_id in unique_target_ids:
        if target_id in existing_links:
            continue
        session.add(
            Association(
                source_model=normalized_source_model,
                source_id=source_id,
                target_model=normalized_target_model,
                target_id=target_id,
                link_type=normalized_link_type,
            )
        )


async def get_target_ids_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    target_model: str,
    link_type: str | None = None,
) -> dict[UUID, list[UUID]]:
    """Return mapping source_id -> target_ids for one weak link family."""
    if not source_ids:
        return {}
    normalized_source_model = _validate_association_source(source_model)
    normalized_target_model = _validate_association_target(target_model)
    source_cls = aliased(MODEL_MAP[normalized_source_model])
    target_cls = aliased(MODEL_MAP[normalized_target_model])
    stmt = (
        select(Association.source_id, Association.target_id)
        .join(source_cls, source_cls.id == Association.source_id)
        .join(target_cls, target_cls.id == Association.target_id)
        .where(
            Association.source_model == normalized_source_model,
            Association.source_id.in_(source_ids),
            Association.target_model == normalized_target_model,
            source_cls.deleted_at.is_(None),
            target_cls.deleted_at.is_(None),
        )
        .order_by(Association.created_at.asc(), Association.id.asc())
    )
    if link_type is not None:
        normalized_link_type = _validate_association_link_type(link_type)
        stmt = stmt.where(Association.link_type == normalized_link_type)
    rows = await session.execute(stmt)
    mapping: dict[UUID, list[UUID]] = defaultdict(list)
    for source_id, target_id in rows.all():
        mapping[source_id].append(target_id)
    return dict(mapping)


async def count_sources_for_targets(
    session: AsyncSession,
    *,
    source_model: str,
    target_model: str,
    target_ids: list[UUID],
    link_type: str | None = None,
) -> dict[UUID, int]:
    """Return mapping target_id -> linked source count."""
    if not target_ids:
        return {}
    normalized_source_model = _validate_association_source(source_model)
    normalized_target_model = _validate_association_target(target_model)
    source_cls = aliased(MODEL_MAP[normalized_source_model])
    target_cls = aliased(MODEL_MAP[normalized_target_model])
    stmt = (
        select(Association.target_id, func.count(Association.id))
        .join(source_cls, source_cls.id == Association.source_id)
        .join(target_cls, target_cls.id == Association.target_id)
        .where(
            Association.source_model == normalized_source_model,
            Association.target_model == normalized_target_model,
            Association.target_id.in_(target_ids),
            source_cls.deleted_at.is_(None),
            target_cls.deleted_at.is_(None),
        )
        .group_by(Association.target_id)
    )
    if link_type is not None:
        normalized_link_type = _validate_association_link_type(link_type)
        stmt = stmt.where(Association.link_type == normalized_link_type)
    rows = await session.execute(stmt)
    return {target_id: count for target_id, count in rows.all()}


async def load_person_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    link_type: str | None = None,
) -> dict[UUID, list[Person]]:
    """Load person grouped by source identifier.

    When ``link_type`` is omitted, every person-targeted association counts as
    a person link; entity-to-person writes canonicalize to ``is_about``.
    """
    mapping = await get_target_ids_for_sources(
        session,
        source_model=source_model,
        source_ids=source_ids,
        target_model="person",
        link_type=link_type,
    )
    all_person_ids = {person_id for person_ids in mapping.values() for person_id in person_ids}
    if not all_person_ids:
        return {}
    stmt = select(Person).where(Person.id.in_(all_person_ids), Person.deleted_at.is_(None))
    rows = await session.execute(stmt)
    person_by_id = {person.id: person for person in rows.scalars().all()}
    return {
        source_id: [
            person_by_id[person_id] for person_id in person_ids if person_id in person_by_id
        ]
        for source_id, person_ids in mapping.items()
    }


async def load_task_lists_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    link_type: str,
) -> dict[UUID, list[Task]]:
    """Load zero or more linked tasks per source identifier."""
    mapping = await get_target_ids_for_sources(
        session,
        source_model=source_model,
        source_ids=source_ids,
        target_model="task",
        link_type=link_type,
    )
    all_task_ids = {task_id for task_ids in mapping.values() for task_id in task_ids}
    if not all_task_ids:
        return {}
    stmt = select(Task).where(Task.id.in_(all_task_ids), Task.deleted_at.is_(None))
    rows = await session.execute(stmt)
    tasks_by_id = {task.id: task for task in rows.scalars().all()}
    return {
        source_id: [tasks_by_id[task_id] for task_id in task_ids if task_id in tasks_by_id]
        for source_id, task_ids in mapping.items()
    }


async def load_task_summary_details(
    session: AsyncSession,
    *,
    tasks: list[Task],
) -> dict[UUID, tuple[str | None, str | None]]:
    """Load vision names and direct parent contents for task tooltip summaries.

    Returns a mapping of task id to ``(vision_name, parent_content)``; either
    value may be ``None`` when the related record is missing or deleted.
    """
    if not tasks:
        return {}
    vision_ids = {task.vision_id for task in tasks if task.vision_id is not None}
    parent_ids = {task.parent_task_id for task in tasks if task.parent_task_id is not None}
    vision_names: dict[UUID, str] = {}
    if vision_ids:
        vision_rows = (
            await session.execute(select(Vision.id, Vision.name).where(Vision.id.in_(vision_ids)))
        ).all()
        vision_names = {row.id: row.name for row in vision_rows}
    parent_contents: dict[UUID, str] = {}
    if parent_ids:
        parent_rows = (
            await session.execute(
                select(Task.id, Task.content).where(
                    Task.id.in_(parent_ids),
                    Task.deleted_at.is_(None),
                )
            )
        ).all()
        parent_contents = {row.id: row.content for row in parent_rows}
    return {
        task.id: (
            vision_names.get(task.vision_id) if task.vision_id is not None else None,
            parent_contents.get(task.parent_task_id) if task.parent_task_id is not None else None,
        )
        for task in tasks
    }


async def load_timelogs_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    link_type: str,
) -> dict[UUID, list[Timelog]]:
    """Load timelogs grouped by source identifier."""
    mapping = await get_target_ids_for_sources(
        session,
        source_model=source_model,
        source_ids=source_ids,
        target_model="timelog",
        link_type=link_type,
    )
    all_timelog_ids = {timelog_id for timelog_ids in mapping.values() for timelog_id in timelog_ids}
    if not all_timelog_ids:
        return {}
    stmt = select(Timelog).where(Timelog.id.in_(all_timelog_ids), Timelog.deleted_at.is_(None))
    rows = await session.execute(stmt)
    timelogs_by_id = {timelog.id: timelog for timelog in rows.scalars().all()}
    return {
        source_id: [
            timelogs_by_id[timelog_id] for timelog_id in timelog_ids if timelog_id in timelogs_by_id
        ]
        for source_id, timelog_ids in mapping.items()
    }


async def load_events_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    link_type: str,
) -> dict[UUID, list[Event]]:
    """Load zero or more linked events per source identifier."""
    mapping = await get_target_ids_for_sources(
        session,
        source_model=source_model,
        source_ids=source_ids,
        target_model="event",
        link_type=link_type,
    )
    all_event_ids = {event_id for event_ids in mapping.values() for event_id in event_ids}
    if not all_event_ids:
        return {}
    stmt = select(Event).where(Event.id.in_(all_event_ids), Event.deleted_at.is_(None))
    rows = await session.execute(stmt)
    events_by_id = {event.id: event for event in rows.scalars().all()}
    return {
        source_id: [events_by_id[event_id] for event_id in event_ids if event_id in events_by_id]
        for source_id, event_ids in mapping.items()
    }


async def load_habit_actions_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    link_type: str,
) -> dict[UUID, list[HabitAction]]:
    """Load zero or more linked habit actions per source identifier."""
    mapping = await get_target_ids_for_sources(
        session,
        source_model=source_model,
        source_ids=source_ids,
        target_model="habit_action",
        link_type=link_type,
    )
    all_action_ids = {action_id for action_ids in mapping.values() for action_id in action_ids}
    if not all_action_ids:
        return {}
    stmt = (
        select(HabitAction)
        .options(selectinload(HabitAction.habit))
        .where(
            HabitAction.id.in_(all_action_ids),
            HabitAction.deleted_at.is_(None),
        )
    )
    rows = await session.execute(stmt)
    actions_by_id = {action.id: action for action in rows.scalars().all()}
    return {
        source_id: [
            actions_by_id[action_id] for action_id in action_ids if action_id in actions_by_id
        ]
        for source_id, action_ids in mapping.items()
    }


async def load_visions_for_sources(
    session: AsyncSession,
    *,
    source_model: str,
    source_ids: list[UUID],
    link_type: str,
) -> dict[UUID, list[Vision]]:
    """Load zero or more linked visions per source identifier."""
    mapping = await get_target_ids_for_sources(
        session,
        source_model=source_model,
        source_ids=source_ids,
        target_model="vision",
        link_type=link_type,
    )
    all_vision_ids = {vision_id for vision_ids in mapping.values() for vision_id in vision_ids}
    if not all_vision_ids:
        return {}
    stmt = select(Vision).where(Vision.id.in_(all_vision_ids), Vision.deleted_at.is_(None))
    rows = await session.execute(stmt)
    visions_by_id = {vision.id: vision for vision in rows.scalars().all()}
    return {
        source_id: [
            visions_by_id[vision_id] for vision_id in vision_ids if vision_id in visions_by_id
        ]
        for source_id, vision_ids in mapping.items()
    }
