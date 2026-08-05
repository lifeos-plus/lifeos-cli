"""Timelog endpoints for the local Web UI."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.db.services import timelogs as timelog_services
from lifeos_cli.db.services.timelog_support import (
    TimelogBatchUpdateInput,
    TimelogCreateInput,
    TimelogListInput,
    TimelogQueryFilters,
    TimelogUpdateInput,
)
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.timelogs import (
    LatestTimelogEndResponse,
    TimelogBatchUpdateResponse,
    TimelogListMeta,
    TimelogResponse,
)
from lifeos_web.schemas import (
    ListResponse,
    Pagination,
    TimelogBatchUpdate,
    TimelogCreate,
    TimelogUpdate,
)
from lifeos_web.serialization import to_jsonable

router = APIRouter(prefix="/timelogs", tags=["timelogs"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _timelog_payload(timelog: object) -> dict[str, object]:
    payload = to_jsonable(timelog)
    if not isinstance(payload, dict):
        raise TypeError("Timelog serialization did not produce a dictionary.")
    area_id = payload.get("area_id")
    if area_id is not None:
        payload["area_summary"] = {
            "id": area_id,
            "name": None,
            "color": None,
        }
    return payload


@router.get("/latest-end-time", response_model=LatestTimelogEndResponse)
async def get_latest_timelog_end_time(session: SessionDep) -> dict[str, str | None]:
    """Return the latest active timelog end time for cursor inheritance."""
    latest_end_time = await timelog_services.get_latest_timelog_end_time(session)
    return {
        "end_time": latest_end_time.isoformat() if latest_end_time else None,
    }


@router.get(
    "/",
    response_model=ListResponse[TimelogResponse, TimelogListMeta],
    response_model_exclude_unset=True,
)
async def list_timelogs(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    start_date: date | None = None,
    end_date: date | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    query: str | None = None,
    tracking_method: str | None = None,
    area_id: UUID | None = None,
    area_name: str | None = None,
    without_area: bool = False,
    task_id: UUID | None = None,
    without_task: bool = False,
    with_task: bool = False,
) -> ListResponse:
    """List timelogs for the local Web UI."""
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date must be provided together.",
        )
    if (start_date is not None or end_date is not None) and (
        window_start is not None or window_end is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="Use either start_date/end_date or window_start/window_end, not both.",
        )
    if without_task and task_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Use either task_id or without_task, not both.",
        )
    if with_task and (without_task or task_id is not None):
        raise HTTPException(
            status_code=400,
            detail="Use only one of task_id, without_task, or with_task.",
        )

    normalized_window_start = to_storage_timezone(window_start) if window_start else None
    normalized_window_end = to_storage_timezone(window_end) if window_end else None
    filters = TimelogQueryFilters(
        start_date=start_date,
        end_date=end_date,
        query=query,
        tracking_method=tracking_method,
        area_id=area_id,
        area_name=area_name,
        without_area=without_area,
        task_id=task_id,
        without_task=without_task,
        with_task=with_task,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
    )
    total_count = await timelog_services.count_timelogs(session, filters=filters)
    rows = await timelog_services.list_timelogs(
        session,
        query=TimelogListInput(
            filters=filters,
            limit=size,
            offset=(page - 1) * size,
        ),
    )
    items = [_timelog_payload(row) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=total_count,
            pages=math.ceil(total_count / size) if size else 0,
        ),
        meta={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "window_start": normalized_window_start.isoformat()
            if normalized_window_start
            else None,
            "window_end": normalized_window_end.isoformat() if normalized_window_end else None,
            "query": query,
            "tracking_method": tracking_method,
            "area_id": str(area_id) if area_id else None,
            "area_name": area_name,
            "without_area": without_area,
            "task_id": str(task_id) if task_id else None,
            "without_task": without_task,
            "with_task": with_task,
            "limit": size,
            "returned_count": len(items),
            "total_count": total_count,
            "truncated": len(items) < total_count,
        },
    )


@router.post("/", response_model=TimelogResponse, response_model_exclude_unset=True)
async def create_timelog(
    payload: TimelogCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create a timelog."""
    try:
        timelog = await timelog_services.create_timelog(
            session,
            payload=TimelogCreateInput(
                title=payload.title,
                start_time=payload.start_time,
                end_time=payload.end_time,
                tracking_method=payload.tracking_method,
                location=payload.location,
                energy_level=payload.energy_level,
                notes=payload.notes,
                area_id=payload.area_id,
                task_id=payload.task_id,
                person_ids=payload.person_ids,
            ),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _timelog_payload(timelog)


@router.post("/batch-update", response_model=TimelogBatchUpdateResponse)
async def batch_update_timelogs(
    payload: TimelogBatchUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Batch-update timelogs through LifeOS native batch semantics."""
    title: str | None = None
    find_title_text: str | None = None
    replace_title_text = ""
    changes = TimelogUpdateInput()

    if payload.update_type == "title":
        if payload.title is None:
            raise HTTPException(status_code=400, detail="Title update payload is required")
        if payload.title.mode == "find_replace":
            find_title_text = payload.title.find
            replace_title_text = payload.title.value
        else:
            title = payload.title.value
    elif payload.update_type == "task":
        if payload.task is None:
            raise HTTPException(status_code=400, detail="Task update payload is required")
        changes = TimelogUpdateInput(
            task_id=payload.task.task_id,
            clear_task=payload.task.mode == "clear" or payload.task.task_id is None,
        )
    elif payload.update_type == "area":
        if payload.area is None:
            raise HTTPException(status_code=400, detail="Area update payload is required")
        changes = TimelogUpdateInput(
            area_id=payload.area.area_id,
            clear_area=payload.area.area_id is None,
        )
    elif payload.update_type == "people":
        if payload.people is None:
            raise HTTPException(status_code=400, detail="Person update payload is required")
        if payload.people.mode == "add":
            result = await timelog_services.batch_add_timelog_people(
                session,
                timelog_ids=payload.timelog_ids,
                person_ids=payload.people.person_ids,
            )
            return {
                "updated_count": result.updated_count,
                "unchanged_ids": [str(timelog_id) for timelog_id in result.unchanged_ids],
                "failed_ids": [str(timelog_id) for timelog_id in result.failed_ids],
                "errors": list(result.errors),
            }
        changes = TimelogUpdateInput(
            person_ids=payload.people.person_ids,
            clear_people=payload.people.mode == "clear",
        )
    else:
        raise HTTPException(
            status_code=400, detail=f"Unsupported update type: {payload.update_type}"
        )

    try:
        result = await timelog_services.batch_update_timelogs(
            session,
            timelog_ids=payload.timelog_ids,
            changes=TimelogBatchUpdateInput(
                title=title,
                find_title_text=find_title_text,
                replace_title_text=replace_title_text,
                changes=changes,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "updated_count": result.updated_count,
        "unchanged_ids": [str(timelog_id) for timelog_id in result.unchanged_ids],
        "failed_ids": [str(timelog_id) for timelog_id in result.failed_ids],
        "errors": list(result.errors),
    }


@router.patch(
    "/{timelog_id}",
    response_model=TimelogResponse,
    response_model_exclude_unset=True,
)
async def update_timelog(
    timelog_id: UUID,
    payload: TimelogUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a timelog."""
    fields = payload.model_fields_set
    try:
        timelog = await timelog_services.update_timelog(
            session,
            timelog_id=timelog_id,
            changes=TimelogUpdateInput(
                title=payload.title,
                start_time=payload.start_time,
                end_time=payload.end_time,
                tracking_method=payload.tracking_method,
                location=payload.location,
                clear_location="location" in fields and payload.location is None,
                energy_level=payload.energy_level,
                clear_energy_level="energy_level" in fields and payload.energy_level is None,
                notes=payload.notes,
                clear_notes="notes" in fields and payload.notes is None,
                area_id=payload.area_id,
                clear_area="area_id" in fields and payload.area_id is None,
                task_id=payload.task_id,
                clear_task="task_id" in fields and payload.task_id is None,
                person_ids=payload.person_ids,
                clear_people="person_ids" in payload.model_fields_set and payload.person_ids == [],
            ),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _timelog_payload(timelog)


@router.delete("/{timelog_id}", status_code=204)
async def delete_timelog(
    timelog_id: UUID,
    session: SessionDep,
) -> None:
    """Soft-delete a timelog."""
    try:
        await timelog_services.delete_timelog(session, timelog_id=timelog_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
