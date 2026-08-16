"""Habit-action resource handlers."""

from __future__ import annotations

import argparse
import sys

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import DateArgumentError, resolve_date_selection_arguments
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import habit_actions as habit_action_services
from lifeos_cli.db.services.read_models import HabitActionView

HABIT_ACTION_SUMMARY_COLUMNS = (
    "habit_action_id",
    "status",
    "action_date",
    "habit_id",
    "habit_title",
)


def _format_habit_action_summary(action: HabitActionView) -> str:
    status = "deleted" if action.deleted_at is not None else action.status
    action_id = "-" if action.id is None else str(action.id)
    return f"{action_id}\t{status}\t{action.action_date}\t{action.habit_id}\t{action.habit_title}"


def _format_habit_action_detail(action: HabitActionView) -> str:
    return "\n".join(
        (
            f"id: {action.id}",
            f"habit_id: {action.habit_id}",
            f"habit_title: {action.habit_title}",
            f"action_date: {action.action_date}",
            f"status: {action.status}",
            f"notes: {action.notes or '-'}",
            f"created_at: {format_timestamp(action.created_at)}",
            f"updated_at: {format_timestamp(action.updated_at)}",
            f"deleted_at: {format_timestamp(action.deleted_at)}",
            f"linked_notes_count: {action.linked_notes_count}",
        )
    )


async def handle_habit_action_list_async(args: argparse.Namespace) -> int:
    try:
        date_selection = resolve_date_selection_arguments(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        try:
            if args.count:
                actions, total_count = await habit_action_services.list_habit_actions_with_total(
                    session,
                    habit_id=args.habit_id,
                    status=args.status,
                    date_values=date_selection.date_values,
                    start_date=date_selection.start_date,
                    end_date=date_selection.end_date,
                    limit=args.limit,
                    offset=args.offset,
                )
            else:
                actions = await habit_action_services.list_habit_actions(
                    session,
                    habit_id=args.habit_id,
                    status=args.status,
                    date_values=date_selection.date_values,
                    start_date=date_selection.start_date,
                    end_date=date_selection.end_date,
                    limit=args.limit,
                    offset=args.offset,
                )
                total_count = None
        except (
            habit_action_services.HabitNotFoundError,
            habit_action_services.HabitValidationError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(actions, total_count=total_count)
        return 0
    trailer_lines = () if total_count is None else (f"Total habit actions: {total_count}",)
    print_summary_rows(
        items=actions,
        columns=HABIT_ACTION_SUMMARY_COLUMNS,
        row_formatter=_format_habit_action_summary,
        empty_message="No habit actions found.",
        trailer_lines=trailer_lines,
    )
    return 0


async def handle_habit_action_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        action = await habit_action_services.get_habit_action(
            session,
            action_id=args.action_id,
        )
    if action is None:
        return cli_handler_utils.print_missing_record_error("Habit action", args.action_id)
    if args.json:
        print_json_payload(action)
        return 0
    print(_format_habit_action_detail(action))
    return 0


async def handle_habit_action_update_async(args: argparse.Namespace) -> int:
    if args.clear_notes and args.notes is not None:
        return cli_handler_utils.print_mutually_exclusive_options("--notes", "--clear-notes")
    async with db_session.session_scope() as session:
        try:
            action = await habit_action_services.update_habit_action(
                session,
                action_id=args.action_id,
                status=args.status,
                notes=args.notes,
                clear_notes=args.clear_notes,
            )
        except (
            habit_action_services.HabitActionNotFoundError,
            habit_action_services.HabitValidationError,
            habit_action_services.InvalidHabitOperationError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated habit action {action.id}")
    return 0


async def handle_habit_action_log_async(args: argparse.Namespace) -> int:
    if args.clear_notes and args.notes is not None:
        return cli_handler_utils.print_mutually_exclusive_options("--notes", "--clear-notes")
    if args.status is None and args.notes is None and not args.clear_notes:
        print("At least one of --status, --notes, or --clear-notes is required.", file=sys.stderr)
        return 1
    async with db_session.session_scope() as session:
        try:
            action = await habit_action_services.update_habit_action_by_date(
                session,
                habit_id=args.habit_id,
                action_date=args.action_date,
                status=args.status,
                notes=args.notes,
                clear_notes=args.clear_notes,
            )
        except (
            habit_action_services.HabitActionNotFoundError,
            habit_action_services.HabitNotFoundError,
            habit_action_services.HabitValidationError,
            habit_action_services.InvalidHabitOperationError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated habit action {action.id}")
    return 0


async def handle_habit_action_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        if len(args.action_ids) > 1:
            result = await habit_action_services.batch_delete_habit_actions(
                session,
                action_ids=args.action_ids,
            )
            return print_batch_result(
                success_label="Deleted habit actions",
                success_count=result.deleted_count,
                failed_label="Failed habit action IDs",
                result=result,
            )
        try:
            await habit_action_services.delete_habit_action(
                session,
                action_id=args.action_ids[0],
            )
        except (
            habit_action_services.HabitActionNotFoundError,
            habit_action_services.InvalidHabitOperationError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted habit action {args.action_ids[0]}")
    return 0
