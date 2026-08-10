"""Vision endpoints used by the local planning UI."""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.services import visions as vision_services
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.visions import (
    VisionListMeta,
    VisionRecomputeResponse,
    VisionResponse,
    VisionStatsResponse,
    VisionWithTasksResponse,
)
from lifeos_web.schemas import ListResponse, Pagination, VisionCreate, VisionUpdate
from lifeos_web.serialization import task_summary_payload, to_jsonable, to_jsonable_dict

router = APIRouter(prefix="/visions", tags=["visions"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _vision_payload(vision: object, *, include_tasks: bool = False) -> dict[str, object]:
    """Serialize a vision for the Web UI."""
    payload: dict[str, object] = {
        "id": str(vision.id),
        "name": vision.name,
        "description": vision.description,
        "area_id": str(vision.area_id) if vision.area_id else None,
        "status": vision.status,
        "stage": vision.stage,
        "experience_points": vision.experience_points,
        "experience_rate_per_hour": vision.experience_rate_per_hour,
        "created_at": to_jsonable(vision.created_at),
        "people": to_jsonable(vision.people),
    }
    if include_tasks:
        raw_tasks = to_jsonable(vision.tasks)
        payload["tasks"] = (
            [task_summary_payload(task) for task in raw_tasks if isinstance(task, dict)]
            if isinstance(raw_tasks, list)
            else []
        )
    return payload


@router.get("/", response_model=ListResponse[VisionResponse, VisionListMeta])
async def list_visions(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    status_filter: str | None = None,
) -> ListResponse:
    """List active visions for selectors and planning cards."""
    rows = await vision_services.list_visions(
        session,
        status=status_filter,
        limit=size,
        offset=(page - 1) * size,
    )
    items = [_vision_payload(row) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=len(items),
            pages=math.ceil(len(items) / size) if size > 0 else 0,
        ),
        meta={"status_filter": status_filter},
    )


@router.get("/{vision_id}", response_model=VisionResponse)
async def get_vision(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load one vision."""
    vision = await vision_services.get_vision(session, vision_id=vision_id)
    if vision is None:
        raise HTTPException(status_code=404, detail=f"Vision {vision_id} was not found")
    return _vision_payload(vision)


@router.post("/", response_model=VisionWithTasksResponse)
async def create_vision(
    payload: VisionCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create a vision."""
    try:
        vision = await vision_services.create_vision(
            session,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            area_id=payload.area_id,
            experience_rate_per_hour=payload.experience_rate_per_hour,
            person_ids=payload.person_ids,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vision_payload(vision, include_tasks=True)


@router.patch("/{vision_id}", response_model=VisionResponse)
async def update_vision(
    vision_id: UUID,
    payload: VisionUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a vision."""
    fields = payload.model_fields_set
    clear_description = "description" in fields and payload.description is None
    clear_experience_rate = (
        "experience_rate_per_hour" in fields and payload.experience_rate_per_hour is None
    )
    clear_area = "area_id" in fields and payload.area_id is None
    clear_people = "person_ids" in fields and payload.person_ids == []
    try:
        vision = await vision_services.update_vision(
            session,
            vision_id=vision_id,
            name=payload.name,
            description=payload.description,
            clear_description=clear_description,
            status=payload.status,
            area_id=payload.area_id,
            clear_area=clear_area,
            experience_rate_per_hour=payload.experience_rate_per_hour,
            clear_experience_rate=clear_experience_rate,
            person_ids=payload.person_ids,
            clear_people=clear_people,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vision_payload(vision)


@router.delete("/{vision_id}", status_code=204)
async def delete_vision(
    vision_id: UUID,
    session: SessionDep,
) -> None:
    """Soft-delete a vision."""
    try:
        await vision_services.delete_vision(session, vision_id=vision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{vision_id}/with-tasks", response_model=VisionResponse)
async def get_vision_with_tasks(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load a vision with active tasks."""
    try:
        vision = await vision_services.get_vision_with_tasks(session, vision_id=vision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _vision_payload(vision)


@router.get("/{vision_id}/stats", response_model=VisionStatsResponse)
async def get_vision_stats(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load vision task stats."""
    try:
        stats = await vision_services.get_vision_stats(session, vision_id=vision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return to_jsonable_dict(stats)


@router.post("/{vision_id}/add-experience", response_model=VisionResponse)
async def add_experience(
    vision_id: UUID,
    payload: dict[str, int],
    session: SessionDep,
) -> dict[str, object]:
    """Add experience to one vision."""
    try:
        vision = await vision_services.add_experience_to_vision(
            session,
            vision_id=vision_id,
            experience_points=payload.get("experience_points", 0),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vision_payload(vision)


@router.post("/{vision_id}/recompute-efforts", response_model=VisionRecomputeResponse)
async def recompute_vision_efforts(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Recompute task effort totals and derived experience for one vision."""
    try:
        result = await vision_services.recompute_vision_task_efforts(
            session,
            vision_id=vision_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "vision_id": str(result.vision_id),
        "recomputed_roots": [str(task_id) for task_id in result.recomputed_roots],
    }


@router.post("/{vision_id}/sync-experience", response_model=VisionResponse)
async def sync_vision_experience(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Synchronize one vision's experience from current root task effort totals."""
    try:
        vision = await vision_services.sync_vision_experience(session, vision_id=vision_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _vision_payload(vision)


@router.post("/{vision_id}/harvest", response_model=VisionResponse)
async def harvest_vision(vision_id: UUID, session: SessionDep) -> dict[str, object]:
    """Harvest one vision when the underlying LifeOS rules allow it."""
    try:
        vision = await vision_services.harvest_vision(session, vision_id=vision_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vision_payload(vision)
