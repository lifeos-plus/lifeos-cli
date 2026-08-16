"""CLI output formatting helpers."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol, TypeVar
from uuid import UUID

from lifeos_cli.application.time_preferences import to_preferred_timezone
from lifeos_cli.db.services.read_models import NoteView
from lifeos_cli.i18n import resolve_locale


class BatchResult(Protocol):
    """Protocol for batch command result rendering."""

    @property
    def failed_ids(self) -> Sequence[UUID]: ...

    @property
    def errors(self) -> Sequence[str]: ...


T = TypeVar("T")


def format_timestamp(value: datetime | None) -> str:
    """Render one timestamp for CLI output."""
    if value is None:
        return "-"
    return to_preferred_timezone(value).isoformat()


def format_id_lines(label: str, identifiers: Sequence[UUID]) -> str:
    """Render a labeled list of identifiers."""
    if not identifiers:
        return f"{label}: -"
    return "\n".join([f"{label}:"] + [f"  {identifier}" for identifier in identifiers])


def print_batch_result(
    *,
    success_label: str,
    success_count: int,
    failed_label: str,
    result: BatchResult,
) -> int:
    """Print a standard batch command result and return the command exit code."""
    print(f"{success_label}: {success_count}")
    if result.failed_ids:
        print(format_id_lines(failed_label, result.failed_ids), file=sys.stderr)
    for error in result.errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if result.failed_ids else 0


def format_summary_header(columns: Sequence[str]) -> str:
    """Render a tab-separated header row for summary output."""
    return "\t".join(columns)


def format_summary_column_list(columns: Sequence[str]) -> str:
    """Render one comma-separated column list for help text."""
    locale_tag = resolve_locale().lower().replace("_", "-")
    separator = "、" if locale_tag.startswith("zh") else ", "
    return separator.join(columns)


def print_summary_rows(
    *,
    items: Sequence[T],
    columns: Sequence[str],
    row_formatter: Callable[[T], str],
    empty_message: str,
    trailer_lines: Sequence[str] = (),
) -> None:
    """Print a summary table with an optional trailer section."""
    if not items:
        print(empty_message)
        for line in trailer_lines:
            print(line)
        return
    print(format_summary_header(columns))
    for item in items:
        print(row_formatter(item))
    for line in trailer_lines:
        print(line)


NOTE_SUMMARY_COLUMNS = (
    "note_id",
    "status",
    "created_at",
    "content",
)

NOTE_SUMMARY_COLUMNS_WITH_COUNTS = (
    "note_id",
    "status",
    "created_at",
    "task_count",
    "vision_count",
    "event_count",
    "person_count",
    "timelog_count",
    "habit_action_count",
    "tag_count",
    "content",
)


def format_note_summary(note: NoteView, *, include_counts: bool = False) -> str:
    """Render a note as a single-line summary for CLI output."""
    normalized_content = " ".join(note.content.split())
    if len(normalized_content) > 80:
        normalized_content = f"{normalized_content[:77]}..."
    created_label = format_timestamp(note.created_at)
    status = "deleted" if note.deleted_at is not None else "active"
    if not include_counts:
        return f"{note.id}\t{status}\t{created_label}\t{normalized_content}"
    habit_actions = getattr(note, "habit_actions", ())
    return (
        f"{note.id}\t{status}\t{created_label}\t{len(note.tasks)}\t{len(note.visions)}\t"
        f"{len(note.events)}\t{len(note.person)}\t{len(note.timelogs)}\t"
        f"{len(habit_actions)}\t{len(note.tags)}\t{normalized_content}"
    )


def format_note_detail(note: NoteView) -> str:
    """Render a note with full metadata and multi-line content."""
    status = "deleted" if note.deleted_at is not None else "active"
    tag_names = ", ".join(tag.name for tag in note.tags)
    person_names = ", ".join(person.name for person in note.person)
    task_labels = ", ".join(f"{task.id} | {task.content}" for task in note.tasks)
    vision_labels = ", ".join(f"{vision.id} | {vision.name}" for vision in note.visions)
    event_labels = ", ".join(f"{event.id} | {event.title}" for event in note.events)
    timelog_labels = ", ".join(f"{timelog.id} | {timelog.title}" for timelog in note.timelogs)
    habit_actions = getattr(note, "habit_actions", ())
    habit_action_labels = ", ".join(
        f"{action.id} | {action.action_date} | {action.status}" for action in habit_actions
    )
    lines = [
        f"id: {note.id}",
        f"status: {status}",
        f"created_at: {format_timestamp(note.created_at)}",
        f"updated_at: {format_timestamp(note.updated_at)}",
        f"deleted_at: {format_timestamp(note.deleted_at)}",
        f"tags: {tag_names or '-'}",
        f"tasks: {task_labels or '-'}",
        f"visions: {vision_labels or '-'}",
        f"events: {event_labels or '-'}",
        f"person: {person_names or '-'}",
        f"timelogs: {timelog_labels or '-'}",
        f"habit_actions: {habit_action_labels or '-'}",
        "content:",
        note.content,
    ]
    return "\n".join(lines)
