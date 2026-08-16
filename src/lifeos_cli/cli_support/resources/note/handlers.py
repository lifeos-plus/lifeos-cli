"""Async note command handlers and note input helpers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    NOTE_SUMMARY_COLUMNS,
    NOTE_SUMMARY_COLUMNS_WITH_COUNTS,
    format_id_lines,
    format_note_detail,
    format_note_summary,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.config import ConfigurationError
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import notes as note_services


def resolve_note_content(args: argparse.Namespace) -> str:
    """Resolve note content from inline text, stdin, or a file."""
    provided_sources = sum(
        1
        for candidate in (args.content is not None, args.stdin, args.file is not None)
        if candidate
    )
    if provided_sources != 1:
        raise ConfigurationError(
            "Provide note content with exactly one source: inline `content`, `--stdin`, or "
            "`--file`."
        )
    if args.stdin:
        content = sys.stdin.read()
    elif args.file is not None:
        try:
            content = Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Could not read note content from {args.file}: {exc}"
            ) from exc
    else:
        content = args.content
    normalized = content.rstrip("\n")
    if not normalized.strip():
        raise ConfigurationError("Note content must not be empty.")
    return normalized


async def handle_note_add_async(args: argparse.Namespace) -> int:
    """Create a new note."""
    content = resolve_note_content(args)
    try:
        async with db_session.session_scope() as session:
            if (
                args.tag_ids is None
                and args.person_ids is None
                and args.task_ids is None
                and args.vision_ids is None
                and args.event_ids is None
                and args.timelog_ids is None
                and args.habit_action_ids is None
            ):
                note = await note_services.create_note(session, content=content)
            else:
                note = await note_services.create_note(
                    session,
                    content=content,
                    tag_ids=args.tag_ids,
                    person_ids=args.person_ids,
                    task_ids=args.task_ids,
                    vision_ids=args.vision_ids,
                    event_ids=args.event_ids,
                    timelog_ids=args.timelog_ids,
                    habit_action_ids=args.habit_action_ids,
                )
    except (LookupError, note_services.NoteValidationError) as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Created note {note.id}")
    return 0


async def handle_note_list_async(args: argparse.Namespace) -> int:
    """List notes."""
    async with db_session.session_scope() as session:
        if (
            args.tag_id is None
            and args.event_id is None
            and args.person_id is None
            and args.task_id is None
            and args.timelog_id is None
            and args.vision_id is None
            and args.habit_action_id is None
        ):
            notes = await note_services.list_notes(
                session,
                limit=args.limit,
                offset=args.offset,
            )
        else:
            notes = await note_services.list_notes(
                session,
                tag_id=args.tag_id,
                event_id=args.event_id,
                person_id=args.person_id,
                task_id=args.task_id,
                timelog_id=args.timelog_id,
                vision_id=args.vision_id,
                habit_action_id=args.habit_action_id,
                limit=args.limit,
                offset=args.offset,
            )
    if args.json:
        print_json_items(notes)
        return 0
    print_summary_rows(
        items=notes,
        columns=NOTE_SUMMARY_COLUMNS_WITH_COUNTS if args.with_counts else NOTE_SUMMARY_COLUMNS,
        row_formatter=lambda note: format_note_summary(note, include_counts=args.with_counts),
        empty_message="No notes found.",
    )
    return 0


async def handle_note_search_async(args: argparse.Namespace) -> int:
    """Search notes by keyword tokens."""
    normalized_query = args.query.strip()
    if not normalized_query:
        raise ConfigurationError("Search query must not be empty.")

    async with db_session.session_scope() as session:
        if (
            args.tag_id is None
            and args.event_id is None
            and args.person_id is None
            and args.task_id is None
            and args.timelog_id is None
            and args.vision_id is None
            and args.habit_action_id is None
        ):
            notes = await note_services.search_notes(
                session,
                query=normalized_query,
                limit=args.limit,
                offset=args.offset,
            )
        else:
            notes = await note_services.search_notes(
                session,
                query=normalized_query,
                tag_id=args.tag_id,
                event_id=args.event_id,
                person_id=args.person_id,
                task_id=args.task_id,
                timelog_id=args.timelog_id,
                vision_id=args.vision_id,
                habit_action_id=args.habit_action_id,
                limit=args.limit,
                offset=args.offset,
            )
    if args.json:
        print_json_items(notes)
        return 0
    print_summary_rows(
        items=notes,
        columns=NOTE_SUMMARY_COLUMNS_WITH_COUNTS if args.with_counts else NOTE_SUMMARY_COLUMNS,
        row_formatter=lambda note: format_note_summary(note, include_counts=args.with_counts),
        empty_message="No matching notes found.",
    )
    return 0


async def handle_note_show_async(args: argparse.Namespace) -> int:
    """Show a note with full content."""
    async with db_session.session_scope() as session:
        note = await note_services.get_note(
            session,
            note_id=args.note_id,
        )
    if note is None:
        return cli_handler_utils.print_missing_record_error("Note", args.note_id)
    if args.json:
        print_json_payload(note)
        return 0
    print(format_note_detail(note))
    return 0


async def handle_note_update_async(args: argparse.Namespace) -> int:
    """Update note content."""
    conflicts = (
        (args.clear_tags and args.tag_ids is not None, "--tag-id", "--clear-tags"),
        (args.clear_person and args.person_ids is not None, "--person-id", "--clear-person"),
        (args.clear_tasks and args.task_ids is not None, "--task-id", "--clear-tasks"),
        (args.clear_visions and args.vision_ids is not None, "--vision-id", "--clear-visions"),
        (args.clear_events and args.event_ids is not None, "--event-id", "--clear-events"),
        (args.clear_timelogs and args.timelog_ids is not None, "--timelog-id", "--clear-timelogs"),
        (
            args.clear_habit_actions and args.habit_action_ids is not None,
            "--habit-action-id",
            "--clear-habit-actions",
        ),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicts)
    if conflict_error is not None:
        return conflict_error

    try:
        async with db_session.session_scope() as session:
            if (
                args.tag_ids is None
                and not args.clear_tags
                and args.person_ids is None
                and not args.clear_person
                and args.task_ids is None
                and not args.clear_tasks
                and args.vision_ids is None
                and not args.clear_visions
                and args.event_ids is None
                and not args.clear_events
                and args.timelog_ids is None
                and not args.clear_timelogs
                and args.habit_action_ids is None
                and not args.clear_habit_actions
            ):
                note = await note_services.update_note(
                    session,
                    note_id=args.note_id,
                    content=args.content,
                )
            else:
                note = await note_services.update_note(
                    session,
                    note_id=args.note_id,
                    content=args.content,
                    tag_ids=args.tag_ids,
                    clear_tags=args.clear_tags,
                    person_ids=args.person_ids,
                    clear_person=args.clear_person,
                    task_ids=args.task_ids,
                    clear_tasks=args.clear_tasks,
                    vision_ids=args.vision_ids,
                    clear_visions=args.clear_visions,
                    event_ids=args.event_ids,
                    clear_events=args.clear_events,
                    timelog_ids=args.timelog_ids,
                    clear_timelogs=args.clear_timelogs,
                    habit_action_ids=args.habit_action_ids,
                    clear_habit_actions=args.clear_habit_actions,
                )
    except (note_services.NoteNotFoundError, note_services.NoteValidationError, LookupError) as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Updated note {note.id}")
    return 0


async def handle_note_delete_async(args: argparse.Namespace) -> int:
    """Delete a note."""
    if len(args.note_ids) > 1:
        async with db_session.session_scope() as session:
            result = await note_services.batch_delete_notes(
                session,
                note_ids=args.note_ids,
            )
        return print_batch_result(
            success_label="Deleted notes",
            success_count=result.deleted_count,
            failed_label="Failed note IDs",
            result=result,
        )
    try:
        async with db_session.session_scope() as session:
            await note_services.delete_note(session, note_id=args.note_ids[0])
    except note_services.NoteNotFoundError as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted note {args.note_ids[0]}")
    return 0


async def handle_note_batch_update_content_async(args: argparse.Namespace) -> int:
    """Apply a batch content replacement across notes."""
    if not args.find_text.strip():
        raise ConfigurationError("Find text must not be empty.")

    async with db_session.session_scope() as session:
        result = await note_services.batch_update_note_content(
            session,
            note_ids=list(args.note_ids),
            find_text=args.find_text,
            replace_text=args.replace_text,
            case_sensitive=args.case_sensitive,
        )

    print(f"Updated notes: {result.updated_count}")
    print(f"Replacements applied: {result.replacement_count}")
    if result.unchanged_ids:
        print(format_id_lines("Unchanged note IDs", result.unchanged_ids))
    if result.failed_ids:
        print(format_id_lines("Failed note IDs", result.failed_ids), file=sys.stderr)
    for error in result.errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if result.failed_ids else 0
