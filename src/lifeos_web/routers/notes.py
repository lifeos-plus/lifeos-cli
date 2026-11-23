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
    NoteBatchCreateFailedItem,
    NoteBatchCreateResponse,
    NoteBatchDeleteResponse,
    NoteBatchUpdateResponse,
    NoteListMeta,
    NotePersonStatsResponse,
    NoteResponse,
)
from lifeos_web.router_utils import soft_delete
from lifeos_web.schemas import (
    ListResponse,
    NoteBatchCreate,
    NoteBatchDelete,
    NoteBatchUpdate,
    NoteCreate,
    NoteUpdate,
    Pagination,
)
from lifeos_web.serialization import note_payload

router = APIRouter(prefix="/notes", tags=["notes"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/", response_model=ListResponse[NoteResponse, NoteListMeta])
async def list_notes(
    session: SessionDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    keyword: str | None = None,
    tag_id: UUID | None = None,
    untagged: bool = False,
    person_id: UUID | None = None,
    task_id: UUID | None = None,
    timelog_id: UUID | None = None,
    habit_action_id: UUID | None = None,
) -> ListResponse:
    """List notes for the local Web UI."""
    if untagged and tag_id is not None:
        raise HTTPException(status_code=400, detail="untagged cannot be combined with tag_id")
    offset = (page - 1) * size
    if keyword:
        rows = await note_services.search_notes(
            session,
            query=keyword,
            tag_id=tag_id,
            untagged=untagged,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            habit_action_id=habit_action_id,
            limit=size,
            offset=offset,
        )
        total = await note_services.count_search_notes(
            session,
            query=keyword,
            tag_id=tag_id,
            untagged=untagged,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            habit_action_id=habit_action_id,
        )
    else:
        rows = await note_services.list_notes(
            session,
            tag_id=tag_id,
            untagged=untagged,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            habit_action_id=habit_action_id,
            limit=size,
            offset=offset,
        )
        total = await note_services.count_notes(
            session,
            tag_id=tag_id,
            untagged=untagged,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            habit_action_id=habit_action_id,
        )
    items = [note_payload(row) for row in rows]
    return ListResponse(
        items=items,
        pagination=Pagination(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if total else 0,
        ),
        meta={
            "keyword": keyword,
            "untagged": untagged,
            "tag_id": str(tag_id) if tag_id else None,
            "person_id": str(person_id) if person_id else None,
            "task_id": str(task_id) if task_id else None,
            "timelog_id": str(timelog_id) if timelog_id else None,
            "habit_action_id": str(habit_action_id) if habit_action_id else None,
        },
    )


@router.get("/stats/person", response_model=NotePersonStatsResponse)
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
        "total_person": len(person_stats),
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
    return note_payload(note)


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
            clear_person="person_ids" in fields and payload.person_ids == [],
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
    return note_payload(note)


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: UUID, session: SessionDep) -> None:
    """Soft-delete a note."""
    await soft_delete(note_services.delete_note, session=session, note_id=note_id)


@router.post("/batch-update", response_model=NoteBatchUpdateResponse)
async def batch_update_notes(
    payload: NoteBatchUpdate,
    session: SessionDep,
) -> NoteBatchUpdateResponse:
    """Apply a content find/replace across multiple notes."""
    if not payload.content.find_text.strip():
        raise HTTPException(status_code=400, detail="Find text must not be empty")
    result = await note_services.batch_update_note_content(
        session,
        note_ids=payload.note_ids,
        find_text=payload.content.find_text,
        replace_text=payload.content.replace_text,
        case_sensitive=payload.content.case_sensitive,
    )
    return NoteBatchUpdateResponse(
        updated_count=result.updated_count,
        replacement_count=result.replacement_count,
        unchanged_ids=[str(note_id) for note_id in result.unchanged_ids],
        failed_ids=[str(note_id) for note_id in result.failed_ids],
        errors=list(result.errors),
    )


@router.post("/batch-delete", response_model=NoteBatchDeleteResponse)
async def batch_delete_notes(
    payload: NoteBatchDelete,
    session: SessionDep,
) -> NoteBatchDeleteResponse:
    """Soft-delete multiple notes while reporting per-note failures."""
    result = await note_services.batch_delete_notes(
        session,
        note_ids=payload.note_ids,
    )
    return NoteBatchDeleteResponse(
        deleted_count=result.deleted_count,
        failed_ids=[str(note_id) for note_id in result.failed_ids],
        errors=list(result.errors),
    )


@router.post("/batch-create", response_model=NoteBatchCreateResponse)
async def batch_create_notes(
    payload: NoteBatchCreate,
    session: SessionDep,
) -> NoteBatchCreateResponse:
    """Create multiple notes, reporting per-item failures."""
    created_notes: list[dict[str, object]] = []
    failed_items: list[NoteBatchCreateFailedItem] = []

    for index, item in enumerate(payload.notes):
        try:
            async with session.begin_nested():
                note = await note_services.create_note(
                    session,
                    content=item.content,
                    tag_ids=payload.tag_ids,
                    person_ids=payload.person_ids,
                    task_ids=([payload.task_id] if payload.task_id is not None else None),
                    timelog_ids=payload.timelog_ids,
                    habit_action_ids=payload.habit_action_ids,
                )
        except (ValueError, LookupError) as exc:
            failed_items.append(
                NoteBatchCreateFailedItem(
                    index=index,
                    content_preview=item.content[:80],
                    error=str(exc),
                )
            )
        else:
            created_notes.append(note_payload(note))

    return NoteBatchCreateResponse(
        created_notes=created_notes,
        failed_items=failed_items,
        created_count=len(created_notes),
        failed_count=len(failed_items),
    )
