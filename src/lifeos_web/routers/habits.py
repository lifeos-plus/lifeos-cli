"""Habit action endpoints used by the local planning UI."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.services import habit_actions as habit_action_services
from lifeos_cli.db.services import habits as habit_services
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
    HabitOverviewResponse,
    HabitResponse,
)
from lifeos_web.schemas import HabitActionUpdate, HabitCreate, HabitUpdate, ListResponse, Pagination
from lifeos_web.serialization import to_jsonable

router = APIRouter(prefix="/habits", tags=["habits"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _habit_model_payload(habit: Habit) -> dict[str, object]:
    """Serialize a Habit SQLAlchemy model for the local Web API."""
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
    }


async def _habit_payload(session: AsyncSession, habit_id: UUID) -> dict[str, object]:
    habit = await habit_services.get_habit(session, habit_id=habit_id)
    if habit is None:
        raise HTTPException(status_code=404, detail=f"Habit {habit_id} was not found")
    return _habit_model_payload(habit)


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
    payload["habit"] = {
        "title": habit.title,
        "description": habit.description,
        "start_date": habit.start_date.isoformat(),
        "duration_days": habit.duration_days,
        "cadence_frequency": habit.cadence_frequency,
    }
    return payload


def _zero_stats(habit_id: UUID) -> dict[str, object]:
    return {
        "habit_id": str(habit_id),
        "total_actions": 0,
        "completed_actions": 0,
        "missed_actions": 0,
        "skipped_actions": 0,
        "progress_percentage": 0,
        "current_streak": 0,
        "longest_streak": 0,
    }


@router.get("/", response_model=ListResponse[HabitResponse, HabitListMeta])
async def list_habits(
    session: SessionDep,
    page: int = 1,
    size: int = 100,
    status_filter: str | None = None,
) -> ListResponse:
    """List habits for the local Web UI."""
    rows = await habit_services.list_habits(
        session,
        status=status_filter,
        limit=size,
        offset=(page - 1) * size,
    )
    items = [_habit_model_payload(row) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(page=page, size=size, total=len(items), pages=1 if items else 0),
        meta={"status_filter": status_filter},
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
) -> ListResponse:
    """List habits with frontend-compatible zeroed stats."""
    habits = await habit_services.list_habits(
        session,
        status=status_filter,
        limit=size,
        offset=(page - 1) * size,
    )
    items = [
        {
            "habit": _habit_model_payload(habit),
            "stats": _zero_stats(habit.id),
        }
        for habit in habits
    ]
    return ListResponse(
        items=items,
        pagination=Pagination(page=page, size=size, total=len(items), pages=1 if items else 0),
        meta={"status_filter": status_filter},
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
    """Load one habit overview with frontend-compatible stats."""
    habit = await _habit_payload(session, habit_id)
    return {"habit": habit, "stats": _zero_stats(habit_id)}


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
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _habit_model_payload(habit)


@router.delete("/{habit_id}", status_code=204)
async def delete_habit(
    habit_id: UUID,
    session: SessionDep,
) -> None:
    """Soft-delete a habit."""
    try:
        await habit_services.delete_habit(session, habit_id=habit_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/actions/by-date/{action_date}",
    response_model=ListResponse[HabitActionWithHabitResponse, HabitActionDateMeta],
)
async def list_actions_by_date(
    action_date: date,
    session: SessionDep,
) -> ListResponse:
    """List materialized habit actions for one local date."""
    actions = await habit_action_services.list_habit_actions(
        session,
        date_values=(action_date,),
        limit=500,
    )
    items = [await _action_with_habit_summary(session, action) for action in actions]
    return ListResponse(
        items=items,
        pagination=Pagination(page=1, size=500, total=len(items), pages=1 if items else 0),
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
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListResponse:
    """List materialized/scheduled actions for one habit."""
    effective_start_date = start_date
    effective_end_date = end_date
    if center_date is not None and start_date is None and end_date is None:
        effective_start_date = center_date - timedelta(days=days_before or 0)
        effective_end_date = center_date + timedelta(days=days_after or 0)

    try:
        actions = await habit_action_services.list_habit_actions(
            session,
            habit_id=habit_id,
            status=status_filter,
            start_date=effective_start_date,
            end_date=effective_end_date,
            limit=size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = [_habit_action_payload(action) for action in actions]
    return ListResponse(
        items=items,
        pagination=Pagination(page=1, size=size, total=len(items), pages=1 if items else 0),
        meta={
            "status_filter": status_filter,
            "center_date": center_date.isoformat() if center_date else None,
            "days_before": days_before,
            "days_after": days_after,
        },
    )


@router.patch("/{habit_id}/actions/{action_id}", response_model=HabitActionResponse)
async def update_action(
    habit_id: UUID,
    action_id: UUID,
    payload: HabitActionUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update one habit action."""
    del habit_id
    fields = payload.model_fields_set
    clear_notes = "notes" in fields and payload.notes is None
    try:
        action = await habit_action_services.update_habit_action(
            session,
            action_id=action_id,
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
