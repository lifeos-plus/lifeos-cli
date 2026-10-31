"""Habit action endpoints used by the local planning UI."""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.services import habit_actions as habit_action_services
from lifeos_cli.db.services import habits as habit_services
from lifeos_cli.db.services import notes as note_services
from lifeos_cli.db.services import planning_lifecycle as planning_lifecycle_services
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.habits import (
    HabitActionDateMeta,
    HabitActionListMeta,
    HabitActionRangeMeta,
    HabitActionResponse,
    HabitActionWithHabitResponse,
    HabitAssociationsResponse,
    HabitListMeta,
    HabitNoteListMeta,
    HabitOverviewResponse,
    HabitResponse,
)
from lifeos_web.response_schemas.notes import NoteResponse
from lifeos_web.router_utils import soft_delete
from lifeos_web.schemas import HabitActionUpdate, HabitCreate, HabitUpdate, ListResponse, Pagination
from lifeos_web.serialization import note_payload, to_jsonable

router = APIRouter(prefix="/habits", tags=["habits"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _habit_model_payload(habit: Habit) -> dict[str, object]:
    """Serialize a Habit SQLAlchemy model for the local Web API."""
    area_id = getattr(habit, "area_id", None)
    return {
        "id": str(habit.id),
        "title": habit.title,
        "description": habit.description,
        "start_date": habit.start_date.isoformat(),
        "duration_days": habit.duration_days,
        "cadence_frequency": habit.cadence_frequency,
        "cadence_weekdays": habit.cadence_weekdays,
        "cadence_monthdays": getattr(habit, "cadence_monthdays", None),
        "target_per_cycle": habit.target_per_cycle,
        "status": habit.status,
        "task_id": str(habit.task_id) if habit.task_id else None,
        "area_id": str(area_id) if area_id else None,
    }


def _habit_action_payload(action: object) -> dict[str, object]:
    """Serialize a habit action occurrence for Web consumers."""
    jsonable = to_jsonable(action)
    assert isinstance(jsonable, dict)
    payload = jsonable
    payload.pop("habit_title", None)
    payload.pop("habit_cadence_frequency", None)
    payload.pop("created_at", None)
    payload.pop("updated_at", None)
    payload.pop("deleted_at", None)
    payload.setdefault("linked_notes_count", 0)
    return payload


async def _action_with_habit_summary(
    session: AsyncSession,
    action: object,
) -> dict[str, object]:
    payload = _habit_action_payload(action)
    habit = await habit_services.get_habit(session, habit_id=UUID(str(payload["habit_id"])))
    if habit is None:
        raise HTTPException(status_code=404, detail=f"Habit {payload['habit_id']} was not found")
    area_id = getattr(habit, "area_id", None)
    payload["habit"] = {
        "title": habit.title,
        "description": habit.description,
        "start_date": habit.start_date.isoformat(),
        "duration_days": habit.duration_days,
        "cadence_frequency": habit.cadence_frequency,
        "area_id": str(area_id) if area_id else None,
    }
    return payload


def _habit_stats_payload(stats: dict[str, object]) -> dict[str, object]:
    """Return the documented Web API subset of derived habit statistics."""
    return {
        "habit_id": str(stats["habit_id"]),
        "total_actions": stats["total_actions"],
        "completed_actions": stats["completed_actions"],
        "missed_actions": stats["missed_actions"],
        "skipped_actions": stats["skipped_actions"],
        "progress_percentage": stats["progress_percentage"],
        "current_streak": stats["current_streak"],
        "longest_streak": stats["longest_streak"],
    }


def _habit_overview_payload(overview: dict[str, object]) -> dict[str, object]:
    """Serialize a derived habit overview for the Web API."""
    habit = overview.get("habit")
    stats = overview.get("stats")
    if not isinstance(habit, Habit) or not isinstance(stats, dict):
        raise RuntimeError("Habit overview payload is invalid.")
    return {
        "habit": _habit_model_payload(habit),
        "stats": _habit_stats_payload(stats),
    }


@router.get("/", response_model=ListResponse[HabitResponse, HabitListMeta])
async def list_habits(
    session: SessionDep,
    page: int = 1,
    size: int = 100,
    status_filter: str | None = None,
    area_id: UUID | None = None,
) -> ListResponse:
    """List habits for the local Web UI."""
    rows = await habit_services.list_habits(
        session,
        status=status_filter,
        area_id=area_id,
        limit=size,
        offset=(page - 1) * size,
    )
    total = await habit_services.count_habits(
        session,
        status=status_filter,
        area_id=area_id,
    )
    items = [_habit_model_payload(row) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if total else 0,
        ),
        meta={"status_filter": status_filter, "area_id": str(area_id) if area_id else None},
    )


@router.get(
    "/overviews",
    response_model=ListResponse[HabitOverviewResponse, HabitListMeta],
)
async def list_habit_overviews(
    session: SessionDep,
    page: int = 1,
    size: int = 100,
    status_filter: str | None = None,
    area_id: UUID | None = None,
) -> ListResponse:
    """List habits with derived statistics."""
    total = await habit_services.count_habits(
        session,
        status=status_filter,
        area_id=area_id,
    )
    overviews = await habit_services.list_habit_overviews(
        session,
        status=status_filter,
        area_id=area_id,
        limit=size,
        offset=(page - 1) * size,
    )
    items = [_habit_overview_payload(overview) for overview in overviews]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if total else 0,
        ),
        meta={"status_filter": status_filter, "area_id": str(area_id) if area_id else None},
    )


@router.get("/habit-task-associations/", response_model=HabitAssociationsResponse)
async def get_habit_task_associations(session: SessionDep) -> dict[str, object]:
    """Return habits grouped by associated task for frontend planning components."""
    habits = await habit_services.list_habits(session, limit=500, offset=0)
    associations: dict[str, list[dict[str, object]]] = {}
    for habit in habits:
        if habit.task_id is None:
            continue
        task_id = str(habit.task_id)
        associations.setdefault(task_id, []).append(_habit_model_payload(habit))
    return {"associations": associations}


@router.get("/{habit_id}/overview", response_model=HabitOverviewResponse)
async def get_habit_overview(habit_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load one habit overview with derived statistics."""
    try:
        overview = await habit_services.get_habit_overview(session, habit_id=habit_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _habit_overview_payload(overview)


@router.post("/", response_model=HabitResponse)
async def create_habit(
    payload: HabitCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create a habit."""
    try:
        habit = await habit_services.create_habit(
            session,
            title=payload.title,
            description=payload.description,
            start_date=payload.start_date,
            duration_days=payload.duration_days,
            end_date=payload.end_date,
            repeat_count=payload.repeat_count,
            cadence_frequency=payload.cadence_frequency,
            cadence_weekdays=payload.cadence_weekdays,
            cadence_monthdays=payload.cadence_monthdays,
            target_per_cycle=payload.target_per_cycle,
            task_id=payload.task_id,
            area_id=payload.area_id,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _habit_model_payload(habit)


@router.patch("/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: UUID,
    payload: HabitUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a habit."""
    fields = payload.model_fields_set
    clear_description = "description" in fields and payload.description is None
    clear_weekdays = "cadence_weekdays" in fields and payload.cadence_weekdays is None
    clear_monthdays = "cadence_monthdays" in fields and payload.cadence_monthdays is None
    clear_task = "task_id" in fields and payload.task_id is None
    try:
        habit = await habit_services.update_habit(
            session,
            habit_id=habit_id,
            title=payload.title,
            description=payload.description,
            clear_description=clear_description,
            start_date=payload.start_date,
            duration_days=payload.duration_days,
            end_date=payload.end_date,
            repeat_count=payload.repeat_count,
            cadence_frequency=payload.cadence_frequency,
            cadence_weekdays=payload.cadence_weekdays,
            clear_weekdays=clear_weekdays,
            cadence_monthdays=payload.cadence_monthdays,
            clear_monthdays=clear_monthdays,
            target_per_cycle=payload.target_per_cycle,
            status=payload.status,
            task_id=payload.task_id,
            clear_task=clear_task,
            area_id=payload.area_id,
            clear_area="area_id" in fields and payload.area_id is None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _habit_model_payload(habit)


@router.delete("/{habit_id}", status_code=204)
async def delete_habit(habit_id: UUID, session: SessionDep) -> None:
    """Soft-delete a habit."""
    await soft_delete(habit_services.delete_habit, session=session, habit_id=habit_id)


@router.get(
    "/actions/by-date/{action_date}",
    response_model=ListResponse[HabitActionWithHabitResponse, HabitActionDateMeta],
)
async def list_actions_by_date(
    action_date: date,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
) -> ListResponse:
    """List materialized habit actions for one local date."""
    actions, total = await habit_action_services.list_habit_actions_with_total(
        session,
        date_values=(action_date,),
        limit=500,
        offset=(page - 1) * 500,
    )
    items = [await _action_with_habit_summary(session, action) for action in actions]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=500,
            total=total,
            pages=math.ceil(total / 500) if total else 0,
        ),
        meta={"action_date": action_date.isoformat()},
    )


@router.get(
    "/actions",
    response_model=ListResponse[HabitActionWithHabitResponse, HabitActionRangeMeta],
)
async def list_actions_in_range(
    session: SessionDep,
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    reference_date: Annotated[date, Query()],
    cadence_frequency: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=1000)] = 1000,
) -> ListResponse:
    """List materialized habit actions for one local planning date range."""
    try:
        await planning_lifecycle_services.reconcile_planning_habit_action_lifecycle(
            session,
            reference_date=reference_date,
            start_date=start_date,
            end_date=end_date,
        )
        actions, total = await habit_action_services.list_habit_actions_with_total(
            session,
            start_date=start_date,
            end_date=end_date,
            cadence_frequency=cadence_frequency,
            limit=size,
            offset=(page - 1) * size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = [await _action_with_habit_summary(session, action) for action in actions]
    pages = (total + size - 1) // size if total else 0
    return ListResponse(
        items=items,
        pagination=Pagination(page=page, size=size, total=total, pages=pages),
        meta={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "reference_date": reference_date.isoformat(),
            "cadence_frequency": cadence_frequency,
        },
    )


@router.get(
    "/{habit_id}/actions",
    response_model=ListResponse[HabitActionResponse, HabitActionListMeta],
)
async def list_actions_for_habit(
    habit_id: UUID,
    session: SessionDep,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    status_filter: Annotated[str | None, Query()] = None,
    center_date: Annotated[date | None, Query()] = None,
    days_before: Annotated[int | None, Query(ge=0, le=500)] = None,
    days_after: Annotated[int | None, Query(ge=0, le=500)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListResponse:
    """List materialized/scheduled actions for one habit."""
    effective_start_date = start_date
    effective_end_date = end_date
    if center_date is not None and start_date is None and end_date is None:
        effective_start_date = center_date - timedelta(days=days_before or 0)
        effective_end_date = center_date + timedelta(days=days_after or 0)

    try:
        actions, total = await habit_action_services.list_habit_actions_with_total(
            session,
            habit_id=habit_id,
            status=status_filter,
            start_date=effective_start_date,
            end_date=effective_end_date,
            limit=size,
            offset=(page - 1) * size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = [_habit_action_payload(action) for action in actions]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if total else 0,
        ),
        meta={
            "status_filter": status_filter,
            "center_date": center_date.isoformat() if center_date else None,
            "days_before": days_before,
            "days_after": days_after,
        },
    )


@router.get(
    "/{habit_id}/notes",
    response_model=ListResponse[NoteResponse, HabitNoteListMeta],
)
async def list_notes_for_habit(
    habit_id: UUID,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ListResponse:
    """List all active notes linked to an active habit through its actions."""
    habit = await habit_services.get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail=f"Habit {habit_id} was not found")

    offset = (page - 1) * size
    notes = await note_services.list_notes(
        session,
        habit_id=habit_id,
        limit=size,
        offset=offset,
    )
    total = await note_services.count_notes(session, habit_id=habit_id)
    return ListResponse(
        items=[note_payload(note) for note in notes],
        pagination=Pagination(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if total else 0,
        ),
        meta={"habit_id": str(habit_id)},
    )


@router.patch("/{habit_id}/actions/{action_id}", response_model=HabitActionResponse)
async def update_action(
    habit_id: UUID,
    action_id: UUID,
    payload: HabitActionUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one habit action."""
    fields = payload.model_fields_set
    clear_notes = "notes" in fields and payload.notes is None
    try:
        action = await habit_action_services.update_habit_action(
            session,
            action_id=action_id,
            habit_id=habit_id,
            status=payload.status,
            notes=payload.notes,
            clear_notes=clear_notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _habit_action_payload(action)


@router.patch(
    "/{habit_id}/actions/by-date/{action_date}",
    response_model=HabitActionResponse,
)
async def update_action_by_date(
    habit_id: UUID,
    action_date: date,
    payload: HabitActionUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one habit action by habit/date, materializing it when needed."""
    fields = payload.model_fields_set
    clear_notes = "notes" in fields and payload.notes is None
    try:
        action = await habit_action_services.update_habit_action_by_date(
            session,
            habit_id=habit_id,
            action_date=action_date,
            status=payload.status,
            notes=payload.notes,
            clear_notes=clear_notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _habit_action_payload(action)
