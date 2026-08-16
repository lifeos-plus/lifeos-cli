"""Async CRUD helpers for notes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from lifeos_cli.db.models.association import Association
from lifeos_cli.db.models.event import Event
from lifeos_cli.db.models.habit_action import HabitAction
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.tag import Tag
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.models.task import Task
from lifeos_cli.db.models.timelog import Timelog
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services.batching import BatchDeleteResult, batch_delete_records
from lifeos_cli.db.services.collection_utils import deduplicate_preserving_order
from lifeos_cli.db.services.entity_associations import (
    load_events_for_sources,
    load_habit_actions_for_sources,
    load_person_for_sources,
    load_task_lists_for_sources,
    load_task_summary_details,
    load_timelogs_for_sources,
    load_visions_for_sources,
    set_association_links,
)
from lifeos_cli.db.services.entity_tags import load_tags_for_entities, sync_entity_tags
from lifeos_cli.db.services.read_models import NoteView, build_note_view
from lifeos_cli.db.services.validation_utils import DomainValidationError


class NoteNotFoundError(LookupError):
    """Raised when a note cannot be found."""


class NoteValidationError(DomainValidationError):
    """Raised when note input cannot be applied."""


@dataclass(frozen=True)
class NoteBatchUpdateResult:
    """Summary for a batch note content update operation."""

    updated_count: int
    unchanged_ids: tuple[UUID, ...]
    failed_ids: tuple[UUID, ...]
    errors: tuple[str, ...]
    replacement_count: int


@dataclass(frozen=True)
class NotePersonUsage:
    """Aggregated active-note usage for one associated person."""

    id: UUID
    name: str
    display_name: str
    usage_count: int


def _normalize_note_content(content: str) -> str:
    """Validate note content while preserving intentional formatting."""
    if not content.strip():
        raise NoteValidationError("Note content must not be empty.")
    return content


def _association_exists_clause(
    *,
    target_model: str,
    target_id: UUID,
    link_type: str,
) -> ColumnElement[bool]:
    target_table_by_model: dict[str, Any] = {
        "event": Event,
        "habit_action": HabitAction,
        "person": Person,
        "task": Task,
        "timelog": Timelog,
        "vision": Vision,
    }
    target_table = target_table_by_model[target_model]
    return exists(
        select(1).where(
            Association.source_model == "note",
            Association.source_id == Note.id,
            Association.target_model == target_model,
            Association.target_id == target_id,
            Association.link_type == link_type,
            target_table.id == Association.target_id,
            target_table.id == target_id,
            target_table.deleted_at.is_(None),
        )
    )


def _note_query(
    *,
    tag_id: UUID | None = None,
    event_id: UUID | None = None,
    person_id: UUID | None = None,
    task_id: UUID | None = None,
    timelog_id: UUID | None = None,
    vision_id: UUID | None = None,
    habit_action_id: UUID | None = None,
) -> Select[tuple[Note]]:
    stmt = select(Note)
    stmt = stmt.where(Note.deleted_at.is_(None))
    if tag_id is not None:
        stmt = stmt.where(
            exists(
                select(1).where(
                    tag_associations.c.entity_type == "note",
                    tag_associations.c.entity_id == Note.id,
                    tag_associations.c.tag_id == tag_id,
                    Tag.id == tag_associations.c.tag_id,
                    Tag.id == tag_id,
                    Tag.deleted_at.is_(None),
                )
            )
        )
    if person_id is not None:
        stmt = stmt.where(
            _association_exists_clause(
                target_model="person",
                target_id=person_id,
                link_type="is_about",
            )
        )
    if task_id is not None:
        stmt = stmt.where(
            _association_exists_clause(
                target_model="task",
                target_id=task_id,
                link_type="relates_to",
            )
        )
    if vision_id is not None:
        stmt = stmt.where(
            _association_exists_clause(
                target_model="vision",
                target_id=vision_id,
                link_type="relates_to",
            )
        )
    if event_id is not None:
        stmt = stmt.where(
            _association_exists_clause(
                target_model="event",
                target_id=event_id,
                link_type="relates_to",
            )
        )
    if timelog_id is not None:
        stmt = stmt.where(
            _association_exists_clause(
                target_model="timelog",
                target_id=timelog_id,
                link_type="captured_from",
            )
        )
    if habit_action_id is not None:
        stmt = stmt.where(
            _association_exists_clause(
                target_model="habit_action",
                target_id=habit_action_id,
                link_type="captured_from",
            )
        )
    return stmt


def _tokenize_search_query(query: str) -> list[str]:
    """Split a search query into normalized non-empty tokens."""
    return [token.strip() for token in query.split() if token.strip()]


def _apply_content_batch_operation(
    *,
    note: Note,
    find_text: str,
    replace_text: str,
    case_sensitive: bool,
) -> int:
    """Apply a content find/replace operation and return the number of replacements."""
    original = note.content
    if case_sensitive:
        replacements = original.count(find_text)
        if replacements:
            note.content = original.replace(find_text, replace_text)
        return replacements

    pattern = re.compile(re.escape(find_text), re.IGNORECASE)
    updated_content, replacements = pattern.subn(replace_text, original)
    if replacements:
        note.content = updated_content
    return replacements


async def _get_note_model(
    session: AsyncSession,
    *,
    note_id: UUID,
) -> Note | None:
    stmt = _note_query().where(Note.id == note_id).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _build_note_views(
    session: AsyncSession,
    note_records: list[Note],
) -> list[NoteView]:
    if not note_records:
        return []
    note_ids = [note.id for note in note_records]
    tags_map = await load_tags_for_entities(session, entity_ids=note_ids, entity_type="note")
    person_map = await load_person_for_sources(
        session,
        source_model="note",
        source_ids=note_ids,
        link_type="is_about",
    )
    task_map = await load_task_lists_for_sources(
        session,
        source_model="note",
        source_ids=note_ids,
        link_type="relates_to",
    )
    task_summary_details = await load_task_summary_details(
        session,
        tasks=[task for tasks in task_map.values() for task in tasks],
    )
    vision_map = await load_visions_for_sources(
        session,
        source_model="note",
        source_ids=note_ids,
        link_type="relates_to",
    )
    event_map = await load_events_for_sources(
        session,
        source_model="note",
        source_ids=note_ids,
        link_type="relates_to",
    )
    timelog_map = await load_timelogs_for_sources(
        session,
        source_model="note",
        source_ids=note_ids,
        link_type="captured_from",
    )
    habit_action_map = await load_habit_actions_for_sources(
        session,
        source_model="note",
        source_ids=note_ids,
        link_type="captured_from",
    )
    return [
        build_note_view(
            note,
            tags=tags_map.get(note.id, ()),
            person_records=person_map.get(note.id, ()),
            tasks=task_map.get(note.id, ()),
            visions=vision_map.get(note.id, ()),
            events=event_map.get(note.id, ()),
            timelogs=timelog_map.get(note.id, ()),
            habit_actions=habit_action_map.get(note.id, ()),
            task_summary_details=task_summary_details,
        )
        for note in note_records
    ]


async def _build_note_view(session: AsyncSession, note: Note) -> NoteView:
    views = await _build_note_views(session, [note])
    return views[0]


async def create_note(
    session: AsyncSession,
    *,
    content: str,
    tag_ids: list[UUID] | None = None,
    person_ids: list[UUID] | None = None,
    task_ids: list[UUID] | None = None,
    vision_ids: list[UUID] | None = None,
    event_ids: list[UUID] | None = None,
    timelog_ids: list[UUID] | None = None,
    habit_action_ids: list[UUID] | None = None,
) -> NoteView:
    """Create and persist a note."""
    note = Note(content=_normalize_note_content(content))
    session.add(note)
    await session.flush()
    if tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=note.id,
            entity_type="note",
            desired_tag_ids=tag_ids,
        )
    if person_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="person",
            target_ids=person_ids,
            link_type="is_about",
        )
    if task_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="task",
            target_ids=task_ids,
            link_type="relates_to",
        )
    if vision_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="vision",
            target_ids=vision_ids,
            link_type="relates_to",
        )
    if event_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="event",
            target_ids=event_ids,
            link_type="relates_to",
        )
    if timelog_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="timelog",
            target_ids=timelog_ids,
            link_type="captured_from",
        )
    if habit_action_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="habit_action",
            target_ids=habit_action_ids,
            link_type="captured_from",
        )
    await session.refresh(note)
    return await _build_note_view(session, note)


async def get_note(
    session: AsyncSession,
    *,
    note_id: UUID,
) -> NoteView | None:
    """Fetch a note by identifier."""
    note = await _get_note_model(session, note_id=note_id)
    if note is None:
        return None
    return await _build_note_view(session, note)


async def list_notes(
    session: AsyncSession,
    *,
    tag_id: UUID | None = None,
    event_id: UUID | None = None,
    person_id: UUID | None = None,
    task_id: UUID | None = None,
    timelog_id: UUID | None = None,
    vision_id: UUID | None = None,
    habit_action_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[NoteView]:
    """Return notes ordered from newest to oldest."""
    stmt = (
        _note_query(
            tag_id=tag_id,
            event_id=event_id,
            person_id=person_id,
            task_id=task_id,
            timelog_id=timelog_id,
            vision_id=vision_id,
            habit_action_id=habit_action_id,
        )
        .order_by(Note.created_at.desc(), Note.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return await _build_note_views(session, list((await session.execute(stmt)).scalars()))


async def count_note_usage_by_person(session: AsyncSession) -> list[NotePersonUsage]:
    """Count active notes by associated active person."""
    stmt = (
        select(
            Person.id,
            Person.name,
            func.count(func.distinct(Note.id)).label("usage_count"),
        )
        .join(
            Association,
            (Association.target_id == Person.id)
            & (Association.source_model == "note")
            & (Association.target_model == "person")
            & (Association.link_type == "is_about"),
        )
        .join(Note, Note.id == Association.source_id)
        .where(
            Note.deleted_at.is_(None),
            Person.deleted_at.is_(None),
        )
        .group_by(Person.id, Person.name)
        .order_by(Person.name.asc(), Person.id.asc())
    )
    rows = await session.execute(stmt)
    return [
        NotePersonUsage(
            id=person_id,
            name=name,
            display_name=name,
            usage_count=int(usage_count),
        )
        for person_id, name, usage_count in rows.all()
    ]


async def search_notes(
    session: AsyncSession,
    *,
    query: str,
    tag_id: UUID | None = None,
    event_id: UUID | None = None,
    person_id: UUID | None = None,
    task_id: UUID | None = None,
    timelog_id: UUID | None = None,
    vision_id: UUID | None = None,
    habit_action_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[NoteView]:
    """Return notes whose content matches any token from the query."""
    tokens = _tokenize_search_query(query)
    stmt = _note_query(
        tag_id=tag_id,
        event_id=event_id,
        person_id=person_id,
        task_id=task_id,
        timelog_id=timelog_id,
        vision_id=vision_id,
        habit_action_id=habit_action_id,
    )
    if tokens:
        stmt = stmt.where(or_(*[Note.content.ilike(f"%{token}%") for token in tokens]))
    stmt = stmt.order_by(Note.created_at.desc(), Note.id.desc()).offset(offset).limit(limit)
    return await _build_note_views(session, list((await session.execute(stmt)).scalars()))


async def update_note(
    session: AsyncSession,
    *,
    note_id: UUID,
    content: str | None = None,
    tag_ids: list[UUID] | None = None,
    clear_tags: bool = False,
    person_ids: list[UUID] | None = None,
    clear_person: bool = False,
    task_ids: list[UUID] | None = None,
    clear_tasks: bool = False,
    vision_ids: list[UUID] | None = None,
    clear_visions: bool = False,
    event_ids: list[UUID] | None = None,
    clear_events: bool = False,
    timelog_ids: list[UUID] | None = None,
    clear_timelogs: bool = False,
    habit_action_ids: list[UUID] | None = None,
    clear_habit_actions: bool = False,
) -> NoteView:
    """Update note content and weak associations."""
    note = await _get_note_model(session, note_id=note_id)
    if note is None:
        raise NoteNotFoundError(f"Note {note_id} was not found")
    if (
        content is None
        and tag_ids is None
        and not clear_tags
        and person_ids is None
        and not clear_person
        and task_ids is None
        and not clear_tasks
        and vision_ids is None
        and not clear_visions
        and event_ids is None
        and not clear_events
        and timelog_ids is None
        and not clear_timelogs
        and habit_action_ids is None
        and not clear_habit_actions
    ):
        raise NoteValidationError("Provide at least one note field or association to update.")

    if content is not None:
        note.content = _normalize_note_content(content)
    if clear_tags:
        await sync_entity_tags(session, entity_id=note.id, entity_type="note", desired_tag_ids=[])
    elif tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=note.id,
            entity_type="note",
            desired_tag_ids=tag_ids,
        )
    if clear_person:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="person",
            target_ids=[],
            link_type="is_about",
        )
    elif person_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="person",
            target_ids=person_ids,
            link_type="is_about",
        )
    if clear_tasks:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="task",
            target_ids=[],
            link_type="relates_to",
        )
    elif task_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="task",
            target_ids=task_ids,
            link_type="relates_to",
        )
    if clear_visions:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="vision",
            target_ids=[],
            link_type="relates_to",
        )
    elif vision_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="vision",
            target_ids=vision_ids,
            link_type="relates_to",
        )
    if clear_events:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="event",
            target_ids=[],
            link_type="relates_to",
        )
    elif event_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="event",
            target_ids=event_ids,
            link_type="relates_to",
        )
    if clear_timelogs:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="timelog",
            target_ids=[],
            link_type="captured_from",
        )
    elif timelog_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="timelog",
            target_ids=timelog_ids,
            link_type="captured_from",
        )
    if clear_habit_actions:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="habit_action",
            target_ids=[],
            link_type="captured_from",
        )
    elif habit_action_ids is not None:
        await set_association_links(
            session,
            source_model="note",
            source_id=note.id,
            target_model="habit_action",
            target_ids=habit_action_ids,
            link_type="captured_from",
        )
    await session.flush()
    await session.refresh(note)
    return await _build_note_view(session, note)


async def delete_note(
    session: AsyncSession,
    *,
    note_id: UUID,
) -> None:
    """Soft-delete a note."""
    note = await _get_note_model(session, note_id=note_id)
    if note is None:
        raise NoteNotFoundError(f"Note {note_id} was not found")
    note.soft_delete()
    await session.flush()


async def batch_update_note_content(
    session: AsyncSession,
    *,
    note_ids: list[UUID],
    find_text: str,
    replace_text: str = "",
    case_sensitive: bool = False,
) -> NoteBatchUpdateResult:
    """Apply a find/replace operation across multiple active notes."""
    updated_count = 0
    replacement_count = 0
    unchanged_ids: list[UUID] = []
    failed_ids: list[UUID] = []
    errors: list[str] = []

    for note_id in deduplicate_preserving_order(note_ids):
        try:
            note = await _get_note_model(session, note_id=note_id)
            if note is None:
                raise NoteNotFoundError(f"Note {note_id} was not found")
            replacements = _apply_content_batch_operation(
                note=note,
                find_text=find_text,
                replace_text=replace_text,
                case_sensitive=case_sensitive,
            )
            if replacements:
                await session.flush()
                await session.refresh(note)
                updated_count += 1
                replacement_count += replacements
            else:
                unchanged_ids.append(note_id)
        except NoteNotFoundError as exc:
            failed_ids.append(note_id)
            errors.append(str(exc))

    return NoteBatchUpdateResult(
        updated_count=updated_count,
        unchanged_ids=tuple(unchanged_ids),
        failed_ids=tuple(failed_ids),
        errors=tuple(errors),
        replacement_count=replacement_count,
    )


async def batch_delete_notes(
    session: AsyncSession,
    *,
    note_ids: list[UUID],
) -> BatchDeleteResult:
    """Soft-delete multiple notes while preserving per-note error reporting."""
    return await batch_delete_records(
        identifiers=deduplicate_preserving_order(note_ids),
        delete_record=lambda note_id: delete_note(session, note_id=note_id),
        handled_exceptions=(NoteNotFoundError,),
    )
