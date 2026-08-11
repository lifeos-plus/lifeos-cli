"""Note endpoints for the local Web UI."""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.services import notes as note_services
from lifeos_web.deps import get_db_session
from lifeos_web.response_schemas.notes import (
    NoteListMeta,
    NotePersonStatsResponse,
    NoteResponse,
)
from lifeos_web.router_utils import soft_delete
from lifeos_web.schemas import ListResponse, NoteCreate, NoteUpdate, Pagination
from lifeos_web.serialization import task_summary_payload, to_jsonable_dict

router = APIRouter(prefix="/notes", tags=["notes"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def _note_tag_payload(tag: object) -> dict[str, object]:
    """Return a frontend-compatible tag summary for note associations."""
    if not isinstance(tag, dict):
        return {}
    return {
        "id": tag.get("id"),
        "name": tag.get("name"),
        "entity_type": tag.get("entity_type") or "note",
        "category": tag.get("category") or "general",
        "description": tag.get("description"),
        "color": tag.get("color"),
        "created_at": tag.get("created_at") or "",
        "updated_at": tag.get("updated_at") or "",
    }


def _note_person_payload(person: object) -> dict[str, object]:
    """Return a frontend-compatible person summary for note associations."""
    if not isinstance(person, dict):
        return {}
    name = str(person.get("name") or "")
    display_name = str(person.get("display_name") or name)
    return {
        "id": person.get("id"),
        "name": person.get("name"),
        "display_name": display_name,
        "primary_nickname": person.get("primary_nickname") or display_name,
        "birth_date": person.get("birth_date"),
        "location": person.get("location"),
        "tags": person.get("tags") if isinstance(person.get("tags"), list) else [],
    }


def _note_payload(note: object) -> dict[str, object]:
    """Return a Web UI-compatible note payload."""
    payload = to_jsonable_dict(note)
    tags = payload.get("tags")
    if isinstance(tags, list):
        payload["tags"] = [_note_tag_payload(tag) for tag in tags]
    people = payload.get("people")
    payload["people"] = (
        [_note_person_payload(person) for person in people] if isinstance(people, list) else []
    )
    tasks = payload.get("tasks")
    if isinstance(tasks, list):
        reshaped_tasks = [task_summary_payload(task) for task in tasks if isinstance(task, dict)]
        payload["tasks"] = reshaped_tasks
        payload["task"] = reshaped_tasks[0] if reshaped_tasks else None
    else:
        payload["task"] = None
    return payload


@router.get("/", response_model=ListResponse[NoteResponse, NoteListMeta])
async def list_notes(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    keyword: str | None = None,
    tag_id: UUID | None = None,
    person_id: UUID | None = None,
    task_id: UUID | None = None,
    timelog_id: UUID | None = None,
    habit_action_id: UUID | None = None,
) -> ListResponse:
    """List notes for the local Web UI."""
    offset = (page - 1) * size
    rows = (
        await note_services.search_notes(
            session,
            query=keyword,
            tag_id=tag_id,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            habit_action_id=habit_action_id,
            limit=size,
            offset=offset,
        )
        if keyword
        else await note_services.list_notes(
            session,
            tag_id=tag_id,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            habit_action_id=habit_action_id,
            limit=size,
            offset=offset,
        )
    )
    items = [_note_payload(row) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=len(items),
            pages=math.ceil(len(items) / size) if size else 0,
        ),
        meta={
            "keyword": keyword,
            "tag_id": str(tag_id) if tag_id else None,
            "person_id": str(person_id) if person_id else None,
            "task_id": str(task_id) if task_id else None,
            "timelog_id": str(timelog_id) if timelog_id else None,
            "habit_action_id": str(habit_action_id) if habit_action_id else None,
        },
    )


@router.get("/stats/persons", response_model=NotePersonStatsResponse)
async def get_note_person_usage_stats(session: SessionDep) -> dict[str, object]:
    """Return active-note usage counts grouped by associated person."""
    person_stats = await note_services.count_note_usage_by_person(session)
    return {
        "person_stats": [
            {
                "id": str(row.id),
                "name": row.name,
                "display_name": row.display_name,
                "usage_count": row.usage_count,
            }
            for row in person_stats
        ],
        "total_persons": len(person_stats),
    }


@router.post("/", response_model=NoteResponse)
async def create_note(
    payload: NoteCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Create a note."""
    try:
        note = await note_services.create_note(
            session,
            content=payload.content,
            tag_ids=payload.tag_ids,
            person_ids=payload.person_ids,
            task_ids=[payload.task_id] if payload.task_id is not None else None,
            timelog_ids=payload.timelog_ids,
            habit_action_ids=payload.habit_action_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _note_payload(note)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    payload: NoteUpdate,
    session: SessionDep,
) -> dict[str, object]:
    """Update a note."""
    try:
        fields = payload.model_fields_set
        note = await note_services.update_note(
            session,
            note_id=note_id,
            content=payload.content,
            tag_ids=payload.tag_ids,
            clear_tags="tag_ids" in fields and payload.tag_ids == [],
            person_ids=payload.person_ids,
            clear_people="person_ids" in fields and payload.person_ids == [],
            task_ids=[payload.task_id] if payload.task_id is not None else None,
            clear_tasks="task_id" in fields and payload.task_id is None,
            timelog_ids=payload.timelog_ids,
            clear_timelogs=("timelog_ids" in fields and payload.timelog_ids == []),
            habit_action_ids=payload.habit_action_ids,
            clear_habit_actions=("habit_action_ids" in fields and payload.habit_action_ids == []),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _note_payload(note)


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: UUID, session: SessionDep) -> None:
    """Soft-delete a note."""
    await soft_delete(note_services.delete_note, session=session, note_id=note_id)
