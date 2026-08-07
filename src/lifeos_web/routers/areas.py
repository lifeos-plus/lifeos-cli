"""Area endpoints for the local Web UI."""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.models.area import Area
from lifeos_cli.db.services import areas as area_services
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.areas import AreaListMeta, AreaResponse
from lifeos_web.schemas import ListResponse, Pagination

router = APIRouter(prefix="/areas", tags=["areas"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


class AreaCreate(BaseModel):
    """Payload for creating an area from the Web UI."""

    name: str
    description: str | None = None
    color: str = "#3B82F6"
    icon: str | None = None
    display_order: int = 0


class AreaUpdate(BaseModel):
    """Payload for updating an area from the Web UI."""

    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


def _area_payload(area: Area) -> dict[str, object]:
    return {
        "id": str(area.id),
        "name": area.name,
        "description": area.description,
        "color": area.color,
        "icon": area.icon,
        "is_active": area.is_active,
        "display_order": area.display_order,
    }


@router.get("/", response_model=ListResponse[AreaResponse, AreaListMeta])
async def list_areas(
    session: SessionDep,
    include_inactive: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListResponse:
    """List LifeOS areas for frontend selectors and managers."""
    areas = await area_services.list_areas(
        session,
        include_inactive=include_inactive,
        limit=size,
        offset=(page - 1) * size,
    )
    items = [_area_payload(area) for area in areas]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=len(items),
            pages=math.ceil(len(items) / size) if size else 0,
        ),
        meta={"include_inactive": include_inactive},
    )


@router.get("/order", response_model=list[str])
async def get_area_order(session: SessionDep) -> list[str]:
    """Return current area display order as area ids."""
    areas = await area_services.list_areas(session, include_inactive=True, limit=500)
    return [str(area.id) for area in areas]


@router.put("/order", status_code=204)
async def set_area_order(order: list[UUID], session: SessionDep) -> None:
    """Persist area display order from the frontend area sorter."""
    for index, area_id in enumerate(order):
        try:
            await area_services.update_area(session, area_id=area_id, display_order=index)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/order", status_code=204)
async def reset_area_order(session: SessionDep) -> None:
    """Reset area display order to the current list order."""
    areas = await area_services.list_areas(session, include_inactive=True, limit=500)
    for index, area in enumerate(areas):
        await area_services.update_area(session, area_id=area.id, display_order=index)


@router.get("/{area_id}", response_model=AreaResponse)
async def get_area(area_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load one LifeOS area."""
    area = await area_services.get_area(session, area_id=area_id)
    if area is None:
        raise HTTPException(status_code=404, detail=f"Area {area_id} was not found")
    return _area_payload(area)


@router.post("/", response_model=AreaResponse)
async def create_area(payload: AreaCreate, session: SessionDep) -> dict[str, object]:
    """Create a LifeOS area from the Web UI."""
    try:
        area = await area_services.create_area(
            session,
            name=payload.name,
            description=payload.description,
            color=payload.color,
            icon=payload.icon,
            display_order=payload.display_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _area_payload(area)


@router.patch("/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: UUID,
    payload: AreaUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a LifeOS area through the Web UI."""
    fields = payload.model_fields_set
    try:
        area = await area_services.update_area(
            session,
            area_id=area_id,
            name=payload.name,
            description=payload.description,
            clear_description="description" in fields and payload.description in {None, ""},
            color=payload.color,
            icon=payload.icon,
            clear_icon="icon" in fields and payload.icon in {None, ""},
            is_active=payload.is_active,
            display_order=payload.display_order,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _area_payload(area)


@router.delete("/{area_id}", status_code=204)
async def delete_area(area_id: UUID, session: SessionDep) -> None:
    """Soft-delete a LifeOS area."""
    try:
        await area_services.delete_area(session, area_id=area_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{area_id}/activate", response_model=AreaResponse)
async def activate_area(area_id: UUID, session: SessionDep) -> dict[str, object]:
    """Reactivate an inactive LifeOS area."""
    try:
        area = await area_services.update_area(
            session,
            area_id=area_id,
            is_active=True,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _area_payload(area)
