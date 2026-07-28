"""Person endpoints used by the local LifeOS Web UI."""

from __future__ import annotations

import math
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.services import people as people_services
from lifeos_cli.db.services import person_activity_queries
from lifeos_cli.db.services.read_models import PersonView, TagSummaryView
from lifeos_web.deps import get_db_session
from lifeos_web.schemas import ListResponse, Pagination

router = APIRouter(prefix="/persons", tags=["persons"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


class PersonCreate(BaseModel):
    """Frontend-compatible person creation payload."""

    name: str
    description: str | None = None
    nicknames: list[str] | None = None
    birth_date: date | None = None
    location: str | None = None
    tag_ids: list[UUID] | None = None


class PersonUpdate(BaseModel):
    """Frontend-compatible person update payload."""

    name: str | None = None
    description: str | None = None
    nicknames: list[str] | None = None
    birth_date: date | None = None
    location: str | None = None
    tag_ids: list[UUID] | None = None


def _tag_payload(tag: TagSummaryView) -> dict[str, object]:
    return {
        "id": str(tag.id),
        "name": tag.name,
        "entity_type": tag.entity_type or "person",
        "category": tag.category or "general",
        "description": tag.description,
        "color": tag.color,
        "created_at": "",
        "updated_at": "",
    }


def _person_payload(person: PersonView) -> dict[str, object]:
    nicknames = list(person.nicknames)
    primary_nickname = nicknames[0] if nicknames else person.name
    tags = [_tag_payload(tag) for tag in person.tags]
    return {
        "id": str(person.id),
        "name": person.name,
        "description": person.description,
        "nicknames": nicknames,
        "birth_date": person.birth_date.isoformat() if person.birth_date else None,
        "location": person.location,
        "tags": tags,
        "anniversaries": [],
        "display_name": person.name,
        "primary_nickname": primary_nickname,
    }


def _activity_payload(item: person_activity_queries.PersonActivity) -> dict[str, object]:
    """Convert a person activity query result to the established JSON shape."""
    payload: dict[str, object] = {
        "id": str(item.id),
        "type": item.activity_type,
        "title": item.title,
        "description": item.description,
        "date": item.activity_date.isoformat(),
        "status": item.status,
    }
    if item.start_time is not None:
        payload["start_time"] = item.start_time.isoformat()
    if item.end_time is not None:
        payload["end_time"] = item.end_time.isoformat()
    if item.activity_type == "timelog":
        payload["area_id"] = str(item.area_id) if item.area_id else None
    return payload


@router.get("/", response_model=ListResponse)
async def list_persons(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 100,
    search: str | None = None,
    tag_id: UUID | None = None,
    tag_filter: str | None = None,
) -> ListResponse:
    """List people for frontend person selectors and pages."""
    del tag_filter
    people = await people_services.list_people(
        session,
        search=search,
        tag_id=tag_id,
        limit=size,
        offset=(page - 1) * size,
    )
    items = [_person_payload(person) for person in people]
    return ListResponse(
        items=items,
        pagination=Pagination(page=page, size=size, total=len(items), pages=1 if items else 0),
        meta={"search": search, "tag_filter": None, "tag_id": str(tag_id) if tag_id else None},
    )


@router.get("/search-by-tag", response_model=ListResponse)
async def search_persons_by_tag(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ListResponse:
    """Return an empty tag-name search result until LifeOS supports tag-name lookup."""
    del session
    return ListResponse(
        items=[],
        pagination=Pagination(page=page, size=size, total=0, pages=0),
        meta={"search": None, "tag_filter": None, "tag_id": None},
    )


@router.get("/{person_id}")
async def get_person(person_id: UUID, session: SessionDep) -> dict[str, object]:
    """Load one person."""
    person = await people_services.get_person(session, person_id=person_id)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person {person_id} was not found")
    return _person_payload(person)


@router.post("/")
async def create_person(payload: PersonCreate, session: SessionDep) -> dict[str, object]:
    """Create a person."""
    try:
        person = await people_services.create_person(
            session,
            name=payload.name,
            description=payload.description,
            nicknames=payload.nicknames,
            birth_date=payload.birth_date,
            location=payload.location,
            tag_ids=payload.tag_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _person_payload(person)


@router.patch("/{person_id}")
async def update_person(
    person_id: UUID,
    payload: PersonUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a person."""
    provided_fields = payload.model_fields_set
    try:
        person = await people_services.update_person(
            session,
            person_id=person_id,
            name=payload.name,
            description=payload.description,
            clear_description="description" in provided_fields and payload.description == "",
            nicknames=payload.nicknames,
            clear_nicknames="nicknames" in provided_fields and payload.nicknames == [],
            birth_date=payload.birth_date,
            clear_birth_date="birth_date" in provided_fields and payload.birth_date is None,
            location=payload.location,
            clear_location="location" in provided_fields and payload.location == "",
            tag_ids=payload.tag_ids,
            clear_tags="tag_ids" in provided_fields and payload.tag_ids == [],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _person_payload(person)


@router.delete("/{person_id}", status_code=204)
async def delete_person(person_id: UUID, session: SessionDep) -> None:
    """Soft-delete a person."""
    try:
        await people_services.delete_person(session, person_id=person_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{person_id}/activities/", response_model=ListResponse)
async def list_person_activities(
    person_id: UUID,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=500)] = 50,
    activity_type: str | None = None,
    type: str | None = None,
) -> ListResponse:
    """Return person-linked activity timeline data."""
    person = await people_services.get_person(session, person_id=person_id)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person {person_id} was not found")
    activity_filter = activity_type or type
    if activity_filter == "all":
        activity_filter = None
    if activity_filter not in {None, "vision", "task", "planned_event", "timelog", "note"}:
        raise HTTPException(status_code=400, detail=f"Unsupported activity type: {activity_filter}")

    result = await person_activity_queries.list_person_activities(
        session,
        person_id=person_id,
        activity_filter=activity_filter,
        limit=size,
        offset=(page - 1) * size,
    )
    return ListResponse(
        items=[_activity_payload(item) for item in result.items],
        pagination=Pagination(
            page=page,
            size=size,
            total=result.total,
            pages=math.ceil(result.total / size) if size else 0,
        ),
        meta={
            "person_id": str(person_id),
            "person_name": person.name,
            "activity_type": activity_filter,
            "timelog_count": result.timelog_count,
            "timelog_total_minutes": result.timelog_total_minutes,
        },
    )


@router.get("/{person_id}/anniversaries/", response_model=ListResponse)
async def list_person_anniversaries(
    person_id: UUID,
    session: SessionDep,
) -> ListResponse:
    """Return empty anniversaries until LifeOS has an anniversary model."""
    person = await people_services.get_person(session, person_id=person_id)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person {person_id} was not found")
    return ListResponse(
        items=[],
        pagination=Pagination(page=1, size=100, total=0, pages=0),
        meta={"person_id": str(person_id)},
    )
