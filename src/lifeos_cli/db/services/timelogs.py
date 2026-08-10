"""Async CRUD helpers for timelogs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lifeos_cli.application.time_preferences import (
    get_utc_window_for_local_date_range,
    to_storage_timezone,
)
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.person_association import person_associations
from lifeos_cli.db.models.tag import Tag
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.services.batching import (
    BatchDeleteResult,
    batch_delete_records,
)
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_associations import (
    count_sources_for_targets,
    load_task_summary_details,
)
from lifeos_cli.db.services.entity_people import load_people_for_entities, sync_entity_people
from lifeos_cli.db.services.entity_tags import load_tags_for_entities, sync_entity_tags
from lifeos_cli.db.services.read_models import TimelogView, build_timelog_view
from lifeos_cli.db.services.task_effort import (
    recompute_task_effort_after_timelog_change,
    recompute_totals_upwards,
)
from lifeos_cli.db.services.timelog_stats import (
    iter_local_dates_for_timelog_window,
    recompute_aggregated_timelog_stats_groupby_area_for_dates,
    recompute_daily_timelog_stats_groupby_area_for_dates,
    recompute_timelog_stats_groupby_area_after_change,
)
from lifeos_cli.db.services.timelog_support import (
    TimelogAreaReferenceNotFoundError,
    TimelogBatchUpdateInput,
    TimelogCreateInput,
    TimelogListInput,
    TimelogNotFoundError,
    TimelogQueryFilters,
    TimelogTaskReferenceNotFoundError,
    TimelogUpdateInput,
    TimelogValidationError,
    ensure_timelog_area_exists,
    ensure_timelog_task_exists,
    validate_energy_level,
    validate_timelog_time_range,
    validate_timelog_title,
    validate_tracking_method,
)
from lifeos_cli.db.services.visions import sync_vision_experience_for_task_ids


@dataclass(frozen=True)
class TimelogBatchUpdateResult:
    """Summary for a batch timelog update operation."""

    updated_count: int
    unchanged_ids: tuple[UUID, ...]
    failed_ids: tuple[UUID, ...]
    errors: tuple[str, ...]


async def _build_timelog_views(
    session: AsyncSession,
    timelogs: list[Timelog],
) -> list[TimelogView]:
    if not timelogs:
        return []
    timelog_ids = [timelog.id for timelog in timelogs]
    tags_map = await load_tags_for_entities(session, entity_ids=timelog_ids, entity_type="timelog")
    people_map = await load_people_for_entities(
        session, entity_ids=timelog_ids, entity_type="timelog"
    )
    note_count_map = await count_sources_for_targets(
        session,
        source_model="note",
        target_model="timelog",
        target_ids=timelog_ids,
        link_type="captured_from",
    )
    task_summary_details = await load_task_summary_details(
        session,
        tasks=[timelog.task for timelog in timelogs if timelog.task is not None],
    )
    return [
        build_timelog_view(
            timelog,
            tags=tags_map.get(timelog.id, ()),
            people=people_map.get(timelog.id, ()),
            linked_notes_count=note_count_map.get(timelog.id, 0),
            task_summary_details=task_summary_details,
        )
        for timelog in timelogs
    ]


async def _build_timelog_view(session: AsyncSession, timelog: Timelog) -> TimelogView:
    refreshed = await _get_timelog_model(
        session,
        timelog_id=timelog.id,
    )
    if refreshed is not None:
        timelog = refreshed
    views = await _build_timelog_views(session, [timelog])
    return views[0]


async def _get_timelog_model(
    session: AsyncSession,
    *,
    timelog_id: UUID,
) -> Timelog | None:
    stmt = (
        select(Timelog)
        .options(
            selectinload(Timelog.area.and_(Area.deleted_at.is_(None))),
            selectinload(Timelog.task.and_(Task.deleted_at.is_(None))),
        )
        .where(Timelog.id == timelog_id)
        .limit(1)
    )
    stmt = stmt.where(Timelog.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


@dataclass(frozen=True)
class _TimelogDependencySnapshot:
    task_id: UUID | None
    start_time: datetime | None
    end_time: datetime | None
    area_id: UUID | None


def _capture_timelog_dependency_snapshot(timelog: Timelog) -> _TimelogDependencySnapshot:
    return _TimelogDependencySnapshot(
        task_id=timelog.task_id,
        start_time=timelog.start_time,
        end_time=timelog.end_time,
        area_id=timelog.area_id,
    )


@dataclass(frozen=True)
class _TimelogDependencyChange:
    previous: _TimelogDependencySnapshot
    current: _TimelogDependencySnapshot


async def _recompute_timelog_dependents(
    session: AsyncSession,
    *,
    change: _TimelogDependencyChange,
) -> None:
    await recompute_task_effort_after_timelog_change(
        session,
        old_task_id=change.previous.task_id,
        new_task_id=change.current.task_id,
    )
    await sync_vision_experience_for_task_ids(
        session,
        task_ids=[
            task_id
            for task_id in (change.previous.task_id, change.current.task_id)
            if task_id is not None
        ],
    )
    await recompute_timelog_stats_groupby_area_after_change(
        session,
        old_start_time=change.previous.start_time,
        old_end_time=change.previous.end_time,
        old_area_id=change.previous.area_id,
        new_start_time=change.current.start_time,
        new_end_time=change.current.end_time,
        new_area_id=change.current.area_id,
    )


async def _flush_and_recompute_timelog_dependents(
    session: AsyncSession,
    *,
    change: _TimelogDependencyChange,
) -> None:
    await session.flush()
    await _recompute_timelog_dependents(session, change=change)
    await session.flush()


def _timelog_change_affects_task_effort(change: _TimelogDependencyChange) -> bool:
    return (
        change.previous.task_id != change.current.task_id
        or change.previous.start_time != change.current.start_time
        or change.previous.end_time != change.current.end_time
    )


def _timelog_change_affects_area_stats(change: _TimelogDependencyChange) -> bool:
    return (
        change.previous.area_id != change.current.area_id
        or change.previous.start_time != change.current.start_time
        or change.previous.end_time != change.current.end_time
    )


def _affected_area_stat_dates(change: _TimelogDependencyChange) -> set[date]:
    affected_dates: set[date] = set()
    if (
        change.previous.area_id is not None
        and change.previous.start_time is not None
        and change.previous.end_time is not None
    ):
        affected_dates.update(
            iter_local_dates_for_timelog_window(
                start_time=change.previous.start_time,
                end_time=change.previous.end_time,
            )
        )
    if (
        change.current.area_id is not None
        and change.current.start_time is not None
        and change.current.end_time is not None
    ):
        affected_dates.update(
            iter_local_dates_for_timelog_window(
                start_time=change.current.start_time,
                end_time=change.current.end_time,
            )
        )
    return affected_dates


async def _flush_and_recompute_batch_timelog_dependents(
    session: AsyncSession,
    *,
    changes: list[_TimelogDependencyChange],
) -> None:
    await session.flush()

    affected_task_ids: list[UUID] = []
    affected_dates: set[date] = set()
    for change in changes:
        if _timelog_change_affects_task_effort(change):
            affected_task_ids.extend(
                task_id
                for task_id in (change.previous.task_id, change.current.task_id)
                if task_id is not None
            )
        if _timelog_change_affects_area_stats(change):
            affected_dates.update(_affected_area_stat_dates(change))

    for task_id in dict.fromkeys(affected_task_ids):
        await recompute_totals_upwards(session, task_id)
    await sync_vision_experience_for_task_ids(
        session,
        task_ids=deduplicate_preserving_order(affected_task_ids),
    )

    local_dates = tuple(sorted(affected_dates))
    if local_dates:
        await recompute_daily_timelog_stats_groupby_area_for_dates(
            session,
            local_dates=local_dates,
        )
        await recompute_aggregated_timelog_stats_groupby_area_for_dates(
            session,
            local_dates=local_dates,
        )

    await session.flush()


def _resolve_timelog_times(
    timelog: Timelog,
    changes: TimelogUpdateInput,
) -> tuple[datetime | None, datetime | None]:
    normalized_start_time = to_storage_timezone(changes.start_time) if changes.start_time else None
    normalized_end_time = to_storage_timezone(changes.end_time) if changes.end_time else None
    next_start_time = (
        normalized_start_time if normalized_start_time is not None else timelog.start_time
    )
    next_end_time = normalized_end_time if normalized_end_time is not None else timelog.end_time
    validate_timelog_time_range(start_time=next_start_time, end_time=next_end_time)
    return normalized_start_time, normalized_end_time


def _apply_timelog_scalar_updates(
    timelog: Timelog,
    changes: TimelogUpdateInput,
    *,
    normalized_start_time: datetime | None,
    normalized_end_time: datetime | None,
) -> None:
    if changes.title is not None:
        timelog.title = validate_timelog_title(changes.title)
    if normalized_start_time is not None:
        timelog.start_time = normalized_start_time
    if normalized_end_time is not None:
        timelog.end_time = normalized_end_time
    if changes.tracking_method is not None:
        timelog.tracking_method = validate_tracking_method(changes.tracking_method)
    if changes.clear_location:
        timelog.location = None
    elif changes.location is not None:
        timelog.location = changes.location
    timelog.energy_level = (
        None
        if changes.clear_energy_level
        else validate_energy_level(changes.energy_level)
        if changes.energy_level is not None
        else timelog.energy_level
    )
    if changes.clear_notes:
        timelog.notes = None
    elif changes.notes is not None:
        timelog.notes = changes.notes


async def _apply_timelog_reference_updates(
    session: AsyncSession,
    *,
    timelog: Timelog,
    changes: TimelogUpdateInput,
) -> None:
    next_area_id = (
        None
        if changes.clear_area
        else changes.area_id
        if changes.area_id is not None
        else timelog.area_id
    )
    next_task_id = (
        None
        if changes.clear_task
        else changes.task_id
        if changes.task_id is not None
        else timelog.task_id
    )
    if next_area_id != timelog.area_id:
        await ensure_timelog_area_exists(session, next_area_id)
        timelog.area_id = next_area_id
    if next_task_id != timelog.task_id:
        await ensure_timelog_task_exists(session, next_task_id)
        timelog.task_id = next_task_id


async def _apply_timelog_association_updates(
    session: AsyncSession,
    *,
    timelog: Timelog,
    changes: TimelogUpdateInput,
) -> None:
    next_tag_ids = [] if changes.clear_tags else changes.tag_ids
    next_person_ids = [] if changes.clear_people else changes.person_ids
    if next_tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=timelog.id,
            entity_type="timelog",
            desired_tag_ids=next_tag_ids,
        )
    if next_person_ids is not None:
        await sync_entity_people(
            session,
            entity_id=timelog.id,
            entity_type="timelog",
            desired_person_ids=next_person_ids,
        )


async def _load_batch_timelog_models(
    session: AsyncSession,
    *,
    timelog_ids: list[UUID],
) -> dict[UUID, Timelog]:
    unique_ids = deduplicate_preserving_order(timelog_ids)
    if not unique_ids:
        return {}
    stmt = select(Timelog).where(
        Timelog.id.in_(unique_ids),
        Timelog.deleted_at.is_(None),
    )
    return {timelog.id: timelog for timelog in (await session.execute(stmt)).scalars()}


async def _ensure_timelog_people_exist(
    session: AsyncSession,
    *,
    person_ids: list[UUID],
) -> list[UUID]:
    unique_person_ids = deduplicate_preserving_order(person_ids)
    if not unique_person_ids:
        return []
    rows = await session.execute(
        select(Person.id).where(
            Person.id.in_(unique_person_ids),
            Person.deleted_at.is_(None),
        )
    )
    existing_person_ids = set(rows.scalars().all())
    missing = [
        str(person_id) for person_id in unique_person_ids if person_id not in existing_person_ids
    ]
    if missing:
        raise LookupError(f"Unknown person IDs for entity type timelog: {', '.join(missing)}")
    return unique_person_ids


async def _ensure_timelog_tags_exist(
    session: AsyncSession,
    *,
    tag_ids: list[UUID],
) -> list[UUID]:
    unique_tag_ids = deduplicate_preserving_order(tag_ids)
    if not unique_tag_ids:
        return []
    rows = await session.execute(
        select(Tag.id).where(
            Tag.id.in_(unique_tag_ids),
            Tag.entity_type == "timelog",
            Tag.deleted_at.is_(None),
        )
    )
    existing_tag_ids = set(rows.scalars().all())
    missing = [str(tag_id) for tag_id in unique_tag_ids if tag_id not in existing_tag_ids]
    if missing:
        raise LookupError(f"Unknown tag IDs for entity type timelog: {', '.join(missing)}")
    return unique_tag_ids


async def _replace_batch_timelog_people(
    session: AsyncSession,
    *,
    timelog_ids: list[UUID],
    desired_person_ids: list[UUID],
    validated_person_ids: list[UUID] | None = None,
) -> None:
    unique_timelog_ids = deduplicate_preserving_order(timelog_ids)
    unique_person_ids = (
        validated_person_ids
        if validated_person_ids is not None
        else await _ensure_timelog_people_exist(
            session,
            person_ids=desired_person_ids,
        )
    )
    if not unique_timelog_ids:
        return
    await session.execute(
        delete(person_associations).where(
            person_associations.c.entity_id.in_(unique_timelog_ids),
            person_associations.c.entity_type == "timelog",
        )
    )
    if not unique_person_ids:
        return
    await session.execute(
        person_associations.insert(),
        [
            {
                "entity_id": timelog_id,
                "entity_type": "timelog",
                "person_id": person_id,
            }
            for timelog_id in unique_timelog_ids
            for person_id in unique_person_ids
        ],
    )


async def _replace_batch_timelog_tags(
    session: AsyncSession,
    *,
    timelog_ids: list[UUID],
    desired_tag_ids: list[UUID],
    validated_tag_ids: list[UUID] | None = None,
) -> None:
    unique_timelog_ids = deduplicate_preserving_order(timelog_ids)
    unique_tag_ids = (
        validated_tag_ids
        if validated_tag_ids is not None
        else await _ensure_timelog_tags_exist(
            session,
            tag_ids=desired_tag_ids,
        )
    )
    if not unique_timelog_ids:
        return
    await session.execute(
        delete(tag_associations).where(
            tag_associations.c.entity_id.in_(unique_timelog_ids),
            tag_associations.c.entity_type == "timelog",
        )
    )
    if not unique_tag_ids:
        return
    await session.execute(
        tag_associations.insert(),
        [
            {
                "entity_id": timelog_id,
                "entity_type": "timelog",
                "tag_id": tag_id,
            }
            for timelog_id in unique_timelog_ids
            for tag_id in unique_tag_ids
        ],
    )


async def batch_add_timelog_people(
    session: AsyncSession,
    *,
    timelog_ids: list[UUID],
    person_ids: list[UUID],
) -> TimelogBatchUpdateResult:
    """Add people links to multiple timelogs without rewriting unchanged links."""
    unique_timelog_ids = deduplicate_preserving_order(timelog_ids)
    timelogs_by_id = await _load_batch_timelog_models(session, timelog_ids=unique_timelog_ids)

    failed_ids: list[UUID] = []
    errors: list[str] = []
    for timelog_id in unique_timelog_ids:
        if timelog_id not in timelogs_by_id:
            failed_ids.append(timelog_id)
            errors.append(f"Timelog {timelog_id} was not found")

    active_ids = [timelog_id for timelog_id in unique_timelog_ids if timelog_id in timelogs_by_id]
    try:
        unique_person_ids = await _ensure_timelog_people_exist(session, person_ids=person_ids)
    except LookupError as exc:
        for timelog_id in active_ids:
            failed_ids.append(timelog_id)
            errors.append(str(exc))
        return TimelogBatchUpdateResult(
            updated_count=0,
            unchanged_ids=(),
            failed_ids=tuple(failed_ids),
            errors=tuple(errors),
        )

    if not active_ids:
        return TimelogBatchUpdateResult(
            updated_count=0,
            unchanged_ids=(),
            failed_ids=tuple(failed_ids),
            errors=tuple(errors),
        )

    rows = await session.execute(
        select(person_associations.c.entity_id, person_associations.c.person_id).where(
            person_associations.c.entity_type == "timelog",
            person_associations.c.entity_id.in_(active_ids),
        )
    )
    existing_by_timelog: dict[UUID, set[UUID]] = {timelog_id: set() for timelog_id in active_ids}
    for timelog_id, person_id in rows.all():
        existing_by_timelog.setdefault(timelog_id, set()).add(person_id)

    insert_rows: list[dict[str, UUID | str]] = []
    updated_ids: list[UUID] = []
    unchanged_ids: list[UUID] = []
    for timelog_id in active_ids:
        existing_person_ids = existing_by_timelog.get(timelog_id, set())
        missing_person_ids = [
            person_id for person_id in unique_person_ids if person_id not in existing_person_ids
        ]
        if not missing_person_ids:
            unchanged_ids.append(timelog_id)
            continue
        updated_ids.append(timelog_id)
        insert_rows.extend(
            {
                "entity_id": timelog_id,
                "entity_type": "timelog",
                "person_id": person_id,
            }
            for person_id in missing_person_ids
        )

    if insert_rows:
        await session.execute(person_associations.insert(), insert_rows)
        await session.flush()

    return TimelogBatchUpdateResult(
        updated_count=len(updated_ids),
        unchanged_ids=tuple(unchanged_ids),
        failed_ids=tuple(failed_ids),
        errors=tuple(errors),
    )


def _apply_timelog_filters(stmt: Any, *, filters: TimelogQueryFilters) -> Any:
    """Apply shared timelog list filters to a SQLAlchemy select."""
    stmt = stmt.where(Timelog.deleted_at.is_(None))
    stmt = _apply_timelog_text_filters(stmt, filters=filters)
    stmt = _apply_timelog_area_task_filters(stmt, filters=filters)
    stmt = _apply_timelog_association_filters(stmt, filters=filters)
    stmt = _apply_timelog_window_filters(stmt, filters=filters)
    return stmt


def _apply_timelog_text_filters(stmt: Any, *, filters: TimelogQueryFilters) -> Any:
    if filters.title_contains:
        stmt = stmt.where(Timelog.title.ilike(f"%{filters.title_contains.strip()}%"))
    if filters.notes_contains:
        stmt = stmt.where(Timelog.notes.ilike(f"%{filters.notes_contains.strip()}%"))
    if filters.query:
        keywords = [keyword.strip() for keyword in filters.query.split() if keyword.strip()]
        if keywords:
            stmt = stmt.where(
                or_(
                    *(
                        or_(
                            Timelog.title.ilike(f"%{keyword}%"),
                            Timelog.notes.ilike(f"%{keyword}%"),
                        )
                        for keyword in keywords
                    )
                )
            )
    if filters.tracking_method is not None:
        stmt = stmt.where(
            Timelog.tracking_method == validate_tracking_method(filters.tracking_method)
        )
    return stmt


def _apply_timelog_area_task_filters(stmt: Any, *, filters: TimelogQueryFilters) -> Any:
    if filters.without_area:
        stmt = stmt.where(Timelog.area_id.is_(None))
    elif filters.area_id is not None:
        stmt = stmt.where(Timelog.area_id == filters.area_id)
    if filters.area_name:
        stmt = stmt.join(Area, Timelog.area_id == Area.id).where(
            Area.name == filters.area_name.strip(),
            Area.deleted_at.is_(None),
        )
    if filters.without_task:
        stmt = stmt.where(Timelog.task_id.is_(None))
    elif filters.with_task:
        stmt = stmt.where(Timelog.task_id.is_not(None))
    elif filters.task_id is not None:
        stmt = stmt.where(Timelog.task_id == filters.task_id)
    return stmt


def _apply_timelog_association_filters(stmt: Any, *, filters: TimelogQueryFilters) -> Any:
    if filters.person_id is not None:
        stmt = stmt.join(
            person_associations,
            (person_associations.c.entity_id == Timelog.id)
            & (person_associations.c.entity_type == "timelog"),
        ).where(person_associations.c.person_id == filters.person_id)
    if filters.tag_id is not None:
        stmt = stmt.join(
            tag_associations,
            (tag_associations.c.entity_id == Timelog.id)
            & (tag_associations.c.entity_type == "timelog"),
        ).where(tag_associations.c.tag_id == filters.tag_id)
    return stmt


def _apply_timelog_window_filters(stmt: Any, *, filters: TimelogQueryFilters) -> Any:
    if filters.date_values:
        date_windows = [
            get_utc_window_for_local_date_range(target_date, target_date)
            for target_date in filters.date_values
        ]
        return stmt.where(
            or_(
                *(
                    and_(Timelog.end_time >= window_start, Timelog.start_time <= window_end)
                    for window_start, window_end in date_windows
                )
            )
        )
    if filters.window_start is not None:
        stmt = stmt.where(Timelog.end_time >= filters.window_start)
    if filters.window_end is not None:
        stmt = stmt.where(Timelog.start_time <= filters.window_end)
    return stmt


def _resolve_timelog_filters(filters: TimelogQueryFilters) -> TimelogQueryFilters:
    if filters.date_values:
        return replace(
            filters,
            date_values=tuple(deduplicate_preserving_order(filters.date_values)),
        )
    if filters.start_date is not None and filters.end_date is not None:
        window_start, window_end = get_utc_window_for_local_date_range(
            filters.start_date,
            filters.end_date,
        )
        return replace(filters, window_start=window_start, window_end=window_end)
    return filters


async def create_timelog(
    session: AsyncSession,
    *,
    payload: TimelogCreateInput,
) -> TimelogView:
    """Create a new timelog."""
    normalized_start_time = to_storage_timezone(payload.start_time)
    normalized_end_time = to_storage_timezone(payload.end_time)
    normalized_title = validate_timelog_title(payload.title)
    validate_timelog_time_range(
        start_time=normalized_start_time,
        end_time=normalized_end_time,
    )
    normalized_tracking_method = validate_tracking_method(payload.tracking_method)
    normalized_energy_level = validate_energy_level(payload.energy_level)
    await ensure_timelog_area_exists(session, payload.area_id)
    await ensure_timelog_task_exists(session, payload.task_id)
    timelog = Timelog(
        title=normalized_title,
        start_time=normalized_start_time,
        end_time=normalized_end_time,
        tracking_method=normalized_tracking_method,
        location=payload.location,
        energy_level=normalized_energy_level,
        notes=payload.notes,
        area_id=payload.area_id,
        task_id=payload.task_id,
    )
    session.add(timelog)
    await session.flush()
    if payload.tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=timelog.id,
            entity_type="timelog",
            desired_tag_ids=payload.tag_ids,
        )
    if payload.person_ids is not None:
        await sync_entity_people(
            session,
            entity_id=timelog.id,
            entity_type="timelog",
            desired_person_ids=payload.person_ids,
        )
    await _flush_and_recompute_timelog_dependents(
        session,
        change=_TimelogDependencyChange(
            previous=_TimelogDependencySnapshot(
                task_id=None,
                start_time=None,
                end_time=None,
                area_id=None,
            ),
            current=_capture_timelog_dependency_snapshot(timelog),
        ),
    )
    await session.refresh(timelog)
    return await _build_timelog_view(session, timelog)


async def get_timelog(
    session: AsyncSession,
    *,
    timelog_id: UUID,
) -> TimelogView | None:
    """Load a timelog by identifier."""
    timelog = await _get_timelog_model(
        session,
        timelog_id=timelog_id,
    )
    if timelog is None:
        return None
    return await _build_timelog_view(session, timelog)


async def get_latest_timelog_end_time(session: AsyncSession) -> datetime | None:
    """Return the latest active timelog end time for quick-add cursor inheritance."""
    stmt = (
        select(Timelog.end_time)
        .where(Timelog.deleted_at.is_(None))
        .order_by(Timelog.end_time.desc(), Timelog.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_timelogs(
    session: AsyncSession,
    *,
    query: TimelogListInput,
) -> list[TimelogView]:
    """List timelogs with optional filters."""
    resolved_filters = _resolve_timelog_filters(query.filters)
    stmt = select(Timelog).options(
        selectinload(Timelog.area.and_(Area.deleted_at.is_(None))),
        selectinload(Timelog.task.and_(Task.deleted_at.is_(None))),
    )
    stmt = _apply_timelog_filters(stmt, filters=resolved_filters)
    stmt = (
        stmt.order_by(Timelog.start_time.desc(), Timelog.id.desc())
        .offset(query.offset)
        .limit(query.limit)
    )
    timelogs = list((await session.execute(stmt)).scalars())
    return await _build_timelog_views(session, timelogs)


async def count_timelogs(
    session: AsyncSession,
    *,
    filters: TimelogQueryFilters,
) -> int:
    """Count timelogs with the same filters used by list_timelogs."""
    id_stmt = _apply_timelog_filters(
        select(Timelog.id),
        filters=_resolve_timelog_filters(filters),
    )
    count_stmt = select(func.count()).select_from(id_stmt.subquery())
    return int((await session.execute(count_stmt)).scalar_one())


async def update_timelog(
    session: AsyncSession,
    *,
    timelog_id: UUID,
    changes: TimelogUpdateInput,
) -> TimelogView:
    """Update one timelog."""
    timelog = await _get_timelog_model(session, timelog_id=timelog_id)
    if timelog is None:
        raise TimelogNotFoundError(f"Timelog {timelog_id} was not found")
    previous_state = _capture_timelog_dependency_snapshot(timelog)
    normalized_start_time, normalized_end_time = _resolve_timelog_times(timelog, changes)
    _apply_timelog_scalar_updates(
        timelog,
        changes,
        normalized_start_time=normalized_start_time,
        normalized_end_time=normalized_end_time,
    )
    await _apply_timelog_reference_updates(session, timelog=timelog, changes=changes)
    await _apply_timelog_association_updates(session, timelog=timelog, changes=changes)
    await _flush_and_recompute_timelog_dependents(
        session,
        change=_TimelogDependencyChange(
            previous=previous_state,
            current=_capture_timelog_dependency_snapshot(timelog),
        ),
    )
    await session.refresh(timelog)
    return await _build_timelog_view(session, timelog)


async def batch_update_timelogs(
    session: AsyncSession,
    *,
    timelog_ids: list[UUID],
    changes: TimelogBatchUpdateInput,
) -> TimelogBatchUpdateResult:
    """Update multiple active timelogs while preserving per-record errors."""
    if changes.title is not None and changes.find_title_text is not None:
        raise TimelogValidationError("Use either title or title find/replace, not both.")
    if changes.find_title_text is not None and not changes.find_title_text.strip():
        raise TimelogValidationError("Title find text must not be empty.")
    if not changes.has_update():
        raise TimelogValidationError("At least one batch update option is required.")

    unique_timelog_ids = deduplicate_preserving_order(timelog_ids)
    timelogs_by_id = await _load_batch_timelog_models(session, timelog_ids=unique_timelog_ids)
    updated_count = 0
    unchanged_ids: list[UUID] = []
    failed_ids: list[UUID] = []
    errors: list[str] = []

    reference_error: Exception | None = None
    if changes.changes.area_id is not None and not changes.changes.clear_area:
        try:
            await ensure_timelog_area_exists(session, changes.changes.area_id)
        except TimelogAreaReferenceNotFoundError as exc:
            reference_error = exc
    if (
        reference_error is None
        and changes.changes.task_id is not None
        and not changes.changes.clear_task
    ):
        try:
            await ensure_timelog_task_exists(session, changes.changes.task_id)
        except TimelogTaskReferenceNotFoundError as exc:
            reference_error = exc

    person_error: Exception | None = None
    validated_person_ids: list[UUID] | None = None
    next_person_ids = [] if changes.changes.clear_people else changes.changes.person_ids
    if next_person_ids is not None:
        try:
            validated_person_ids = await _ensure_timelog_people_exist(
                session,
                person_ids=next_person_ids,
            )
        except LookupError as exc:
            person_error = exc

    tag_error: Exception | None = None
    validated_tag_ids: list[UUID] | None = None
    next_tag_ids = [] if changes.changes.clear_tags else changes.changes.tag_ids
    if next_tag_ids is not None:
        try:
            validated_tag_ids = await _ensure_timelog_tags_exist(
                session,
                tag_ids=next_tag_ids,
            )
        except LookupError as exc:
            tag_error = exc

    updated_timelog_ids: list[UUID] = []
    dependency_changes: list[_TimelogDependencyChange] = []
    for timelog_id in unique_timelog_ids:
        timelog = timelogs_by_id.get(timelog_id)
        if timelog is None:
            failed_ids.append(timelog_id)
            errors.append(f"Timelog {timelog_id} was not found")
            continue

        next_title = changes.title
        if changes.find_title_text is not None:
            replaced_title = timelog.title.replace(
                changes.find_title_text,
                changes.replace_title_text,
            )
            if replaced_title != timelog.title:
                next_title = replaced_title
            elif not changes.has_non_title_update():
                unchanged_ids.append(timelog_id)
                continue
            else:
                next_title = None

        if reference_error is not None and changes.has_non_title_update():
            failed_ids.append(timelog_id)
            errors.append(str(reference_error))
            continue
        if person_error is not None and next_person_ids is not None:
            failed_ids.append(timelog_id)
            errors.append(str(person_error))
            continue
        if tag_error is not None and next_tag_ids is not None:
            failed_ids.append(timelog_id)
            errors.append(str(tag_error))
            continue

        try:
            normalized_title = (
                validate_timelog_title(next_title) if next_title is not None else None
            )
        except TimelogValidationError as exc:
            failed_ids.append(timelog_id)
            errors.append(str(exc))
            continue

        previous_state = _capture_timelog_dependency_snapshot(timelog)
        if normalized_title is not None:
            timelog.title = normalized_title
        if changes.changes.clear_area:
            timelog.area_id = None
        elif changes.changes.area_id is not None:
            timelog.area_id = changes.changes.area_id
        if changes.changes.clear_task:
            timelog.task_id = None
        elif changes.changes.task_id is not None:
            timelog.task_id = changes.changes.task_id

        updated_timelog_ids.append(timelog_id)
        dependency_changes.append(
            _TimelogDependencyChange(
                previous=previous_state,
                current=_capture_timelog_dependency_snapshot(timelog),
            )
        )
        updated_count += 1

    if updated_timelog_ids and next_person_ids is not None:
        await _replace_batch_timelog_people(
            session,
            timelog_ids=updated_timelog_ids,
            desired_person_ids=next_person_ids,
            validated_person_ids=validated_person_ids,
        )
    if updated_timelog_ids and next_tag_ids is not None:
        await _replace_batch_timelog_tags(
            session,
            timelog_ids=updated_timelog_ids,
            desired_tag_ids=next_tag_ids,
            validated_tag_ids=validated_tag_ids,
        )

    if updated_timelog_ids:
        await _flush_and_recompute_batch_timelog_dependents(
            session,
            changes=dependency_changes,
        )

    return TimelogBatchUpdateResult(
        updated_count=updated_count,
        unchanged_ids=tuple(unchanged_ids),
        failed_ids=tuple(failed_ids),
        errors=tuple(errors),
    )


async def delete_timelog(session: AsyncSession, *, timelog_id: UUID) -> None:
    """Soft-delete one timelog."""
    timelog = await _get_timelog_model(session, timelog_id=timelog_id)
    if timelog is None:
        raise TimelogNotFoundError(f"Timelog {timelog_id} was not found")
    old_task_id = timelog.task_id
    old_area_id = timelog.area_id
    old_start_time = timelog.start_time
    old_end_time = timelog.end_time
    timelog.soft_delete()
    await _flush_and_recompute_timelog_dependents(
        session,
        change=_TimelogDependencyChange(
            previous=_TimelogDependencySnapshot(
                task_id=old_task_id,
                start_time=old_start_time,
                end_time=old_end_time,
                area_id=old_area_id,
            ),
            current=_TimelogDependencySnapshot(
                task_id=None,
                start_time=None,
                end_time=None,
                area_id=None,
            ),
        ),
    )


async def batch_delete_timelogs(
    session: AsyncSession,
    *,
    timelog_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple timelogs."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(timelog_ids),
        delete_record=lambda timelog_id: delete_timelog(session, timelog_id=timelog_id),
        handled_exceptions=(TimelogNotFoundError,),
    )
