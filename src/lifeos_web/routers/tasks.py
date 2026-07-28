"""Task endpoints used by the local planning UI."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.services import task_queries
from lifeos_cli.db.services import tasks as task_services
from lifeos_web.deps import get_db_session
from lifeos_web.schemas import (
    ListResponse,
    Pagination,
    TaskCreate,
    TaskReorderRequest,
    TaskStatusUpdate,
    TaskUpdate,
)
from lifeos_web.serialization import to_jsonable, to_jsonable_dict

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
TASK_LIST_FIELD_MODES = {"basic", "full"}
TASK_BASIC_FIELDS = (
    "id",
    "vision_id",
    "parent_task_id",
    "content",
    "status",
    "priority",
    "display_order",
    "planning_cycle_type",
    "planning_cycle_days",
    "planning_cycle_start_date",
    "people",
    "notes_count",
    "timelogs_count",
)


def _collect_task_tree_ids(tasks: list[Any]) -> list[UUID]:
    task_ids: list[UUID] = []

    def visit(task: Any) -> None:
        task_ids.append(task.id)
        for subtask in getattr(task, "subtasks", ()) or ():
            visit(subtask)

    for task in tasks:
        visit(task)
    return task_ids


def _page_envelope(
    *,
    items: list[dict[str, object]],
    page: int,
    size: int,
    total: int,
    meta: dict[str, object],
) -> ListResponse:
    pages = math.ceil(total / size) if size > 0 else 0
    return ListResponse(
        items=items,
        pagination=Pagination(page=page, size=size, total=total, pages=pages),
        meta=meta,
    )


def _task_tree_payload(
    task: Any,
    *,
    notes_count_by_task: dict[UUID, int],
    timelogs_count_by_task: dict[UUID, int],
) -> dict[str, object]:
    """Serialize a nested task read model without leaking SQLAlchemy internals."""
    return {
        "id": str(task.id),
        "vision_id": str(task.vision_id),
        "parent_task_id": str(task.parent_task_id) if task.parent_task_id else None,
        "content": task.content,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "display_order": task.display_order,
        "estimated_effort": task.estimated_effort,
        "planning_cycle_type": task.planning_cycle_type,
        "planning_cycle_days": task.planning_cycle_days,
        "planning_cycle_start_date": (
            task.planning_cycle_start_date.isoformat() if task.planning_cycle_start_date else None
        ),
        "actual_effort_self": task.actual_effort_self,
        "actual_effort_total": task.actual_effort_total,
        "notes_count": notes_count_by_task.get(task.id, 0),
        "timelogs_count": timelogs_count_by_task.get(task.id, 0),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "people": to_jsonable(task.people),
        "subtasks": [
            _task_tree_payload(
                subtask,
                notes_count_by_task=notes_count_by_task,
                timelogs_count_by_task=timelogs_count_by_task,
            )
            for subtask in task.subtasks
        ],
        "completion_percentage": task.completion_percentage,
        "depth": task.depth,
    }


def _task_list_payload(
    task: object,
    *,
    fields: str,
    notes_count_by_task: dict[UUID, int] | None = None,
    timelogs_count_by_task: dict[UUID, int] | None = None,
) -> dict[str, object]:
    payload = to_jsonable_dict(task)
    payload.pop("deleted_at", None)
    task_id = getattr(task, "id", None)
    if isinstance(task_id, UUID):
        payload["notes_count"] = (notes_count_by_task or {}).get(task_id, 0)
        payload["timelogs_count"] = (timelogs_count_by_task or {}).get(task_id, 0)
    if fields == "basic":
        return {field: payload.get(field) for field in TASK_BASIC_FIELDS}
    return payload


@router.get("/", response_model=ListResponse)
async def list_tasks(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
    vision_id: UUID | None = None,
    vision_in: str | None = None,
    status_filter: str | None = None,
    status_in: str | None = None,
    exclude_status: str | None = None,
    planning_cycle_type: str | None = None,
    planning_cycle_start_date: date | None = None,
    calendar_system: str | None = None,
    first_day_of_week: Annotated[int | None, Query(ge=1, le=7)] = None,
    query: str | None = None,
    fields: Annotated[str, Query(pattern="^(basic|full)$")] = "basic",
) -> ListResponse:
    """List tasks using the frontend planning query shape."""
    if fields not in TASK_LIST_FIELD_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported task fields mode: {fields}")
    try:
        rows = await task_services.list_tasks(
            session,
            vision_id=vision_id,
            vision_in=vision_in,
            status=status_filter,
            status_in=status_in,
            exclude_status=exclude_status,
            planning_cycle_type=planning_cycle_type,
            planning_cycle_start_date=planning_cycle_start_date,
            calendar_system=calendar_system,
            first_day_of_week=first_day_of_week,
            query=query,
            limit=size,
            offset=(page - 1) * size,
        )
        total_count = await task_services.count_tasks(
            session,
            vision_id=vision_id,
            vision_in=vision_in,
            status=status_filter,
            status_in=status_in,
            exclude_status=exclude_status,
            planning_cycle_type=planning_cycle_type,
            planning_cycle_start_date=planning_cycle_start_date,
            calendar_system=calendar_system,
            first_day_of_week=first_day_of_week,
            query=query,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    notes_count_by_task, timelogs_count_by_task = await task_queries.load_task_relation_counts(
        session,
        task_ids=[row.id for row in rows],
    )
    return _page_envelope(
        items=[
            _task_list_payload(
                row,
                fields=fields,
                notes_count_by_task=notes_count_by_task,
                timelogs_count_by_task=timelogs_count_by_task,
            )
            for row in rows
        ],
        page=page,
        size=size,
        total=total_count,
        meta={
            "vision_id": str(vision_id) if vision_id else None,
            "vision_in": vision_in,
            "status_filter": status_filter,
            "status_in": status_in,
            "exclude_status": exclude_status,
            "planning_cycle_type": planning_cycle_type,
            "planning_cycle_start_date": (
                planning_cycle_start_date.isoformat() if planning_cycle_start_date else None
            ),
            "calendar_system": calendar_system,
            "first_day_of_week": first_day_of_week,
            "query": query,
            "fields": fields,
        },
    )


@router.post("/")
async def create_task(
    payload: TaskCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create a task."""
    try:
        task = await task_services.create_task(
            session,
            vision_id=payload.vision_id,
            parent_task_id=payload.parent_task_id,
            content=payload.content,
            priority=payload.priority,
            display_order=payload.display_order,
            estimated_effort=payload.estimated_effort,
            planning_cycle_type=payload.planning_cycle_type,
            planning_cycle_days=payload.planning_cycle_days,
            planning_cycle_start_date=payload.planning_cycle_start_date,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_jsonable_dict(task)


@router.get("/vision/{vision_id}/hierarchy")
async def get_vision_hierarchy(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load a frontend-compatible task hierarchy for one vision."""
    try:
        hierarchy = await task_services.get_vision_task_hierarchy(session, vision_id=vision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    task_ids = _collect_task_tree_ids(list(hierarchy.root_tasks))
    notes_count_by_task, timelogs_count_by_task = await task_queries.load_task_relation_counts(
        session,
        task_ids=task_ids,
    )
    return {
        "vision_id": str(hierarchy.vision_id),
        "root_tasks": [
            _task_tree_payload(
                task,
                notes_count_by_task=notes_count_by_task,
                timelogs_count_by_task=timelogs_count_by_task,
            )
            for task in hierarchy.root_tasks
        ],
    }


@router.post("/reorder", status_code=204)
async def reorder_tasks(payload: TaskReorderRequest, session: SessionDep) -> None:
    """Update display order for multiple tasks."""
    task_orders = [(item.id, item.display_order) for item in payload.task_orders]
    try:
        await task_services.reorder_tasks(session, task_orders=task_orders)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}")
async def get_task(task_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load one task."""
    task = await task_services.get_task(session, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} was not found")
    notes_count_by_task, timelogs_count_by_task = await task_queries.load_task_relation_counts(
        session,
        task_ids=[task.id],
    )
    return _task_list_payload(
        task,
        fields="full",
        notes_count_by_task=notes_count_by_task,
        timelogs_count_by_task=timelogs_count_by_task,
    )


@router.put("/{task_id}")
async def replace_task(
    task_id: UUID,
    payload: TaskUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Frontend-compatible alias for partial task update."""
    return await update_task(task_id=task_id, payload=payload, session=session)


@router.patch("/{task_id}")
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a task."""
    fields = payload.model_fields_set
    clear_planning_cycle = "planning_cycle_type" in fields and payload.planning_cycle_type is None
    clear_parent = "parent_task_id" in fields and payload.parent_task_id is None
    clear_estimated_effort = "estimated_effort" in fields and payload.estimated_effort is None
    try:
        task = await task_services.update_task(
            session,
            task_id=task_id,
            content=payload.content,
            status=payload.status,
            priority=payload.priority,
            display_order=payload.display_order,
            estimated_effort=payload.estimated_effort,
            parent_task_id=payload.parent_task_id,
            planning_cycle_type=payload.planning_cycle_type,
            planning_cycle_days=payload.planning_cycle_days,
            planning_cycle_start_date=payload.planning_cycle_start_date,
            clear_planning_cycle=clear_planning_cycle,
            clear_parent=clear_parent,
            clear_estimated_effort=clear_estimated_effort,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_jsonable_dict(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: UUID, session: SessionDep) -> None:
    """Soft-delete one task."""
    try:
        await task_services.delete_task(session, task_id=task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: UUID,
    payload: TaskStatusUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a task status."""
    try:
        task = await task_services.update_task(
            session,
            task_id=task_id,
            status=payload.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_jsonable_dict(task)


@router.get("/{task_id}/with-subtasks")
async def get_task_with_subtasks(task_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load one task with nested subtasks."""
    task = await task_services.get_task_with_subtasks(session, task_id=task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} was not found")
    task_ids = _collect_task_tree_ids([task])
    notes_count_by_task, timelogs_count_by_task = await task_queries.load_task_relation_counts(
        session,
        task_ids=task_ids,
    )
    return _task_tree_payload(
        task,
        notes_count_by_task=notes_count_by_task,
        timelogs_count_by_task=timelogs_count_by_task,
    )


@router.get("/{task_id}/stats")
async def get_task_stats(task_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load task subtree stats."""
    try:
        stats = await task_services.get_task_stats(session, task_id=task_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return to_jsonable_dict(stats)


@router.post("/{task_id}/move")
async def move_task(
    task_id: UUID,
    payload: dict[str, Any],
    session: SessionDep,
) -> dict[str, object]:
    """Move a task to a new parent/vision."""
    try:
        result = await task_services.move_task(
            session,
            task_id=task_id,
            old_parent_task_id=(
                UUID(str(payload["old_parent_task_id"]))
                if payload.get("old_parent_task_id")
                else None
            ),
            new_parent_task_id=(
                UUID(str(payload["new_parent_task_id"]))
                if payload.get("new_parent_task_id")
                else None
            ),
            new_vision_id=(
                UUID(str(payload["new_vision_id"])) if payload.get("new_vision_id") else None
            ),
            new_display_order=payload.get("new_display_order"),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        **to_jsonable_dict(await task_services.get_task(session, task_id=result.task.id)),
        "updated_descendants": [to_jsonable(task) for task in result.updated_descendants],
    }
