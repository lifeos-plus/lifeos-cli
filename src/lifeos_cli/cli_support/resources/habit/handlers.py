"""Habit resource handlers."""

from __future__ import annotations

import argparse
from typing import cast

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_summary_header,
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.services import habits as habit_services
from lifeos_cli.db.services.habit_support import WEEKEND_HABIT_WEEKDAYS

HABIT_SUMMARY_COLUMNS = (
    "habit_id",
    "status",
    "start_date",
    "duration_days",
    "cadence",
    "task_id",
    "title",
)
HABIT_SUMMARY_WITH_STATS_COLUMNS = (
    "habit_id",
    "status",
    "start_date",
    "duration_days",
    "cadence",
    "progress_percentage",
    "current_streak",
    "longest_streak",
    "title",
)
HABIT_TASK_ASSOCIATION_COLUMNS = (
    "task_id",
    "habit_id",
    "habit_status",
    "habit_start_date",
    "habit_title",
)


def _resolve_weekday_selection(args: argparse.Namespace) -> list[str] | None:
    weekdays = getattr(args, "weekdays", None)
    if getattr(args, "weekends_only", False):
        return list(WEEKEND_HABIT_WEEKDAYS)
    return weekdays


def _format_cadence_weekdays(habit: Habit) -> str:
    weekdays = getattr(habit, "cadence_weekdays", None)
    if not weekdays:
        return "-"
    return ",".join(str(weekday) for weekday in weekdays)


def _format_cadence_monthdays(habit: Habit) -> str:
    monthdays = getattr(habit, "cadence_monthdays", None)
    if not monthdays:
        return "-"
    return ",".join(str(monthday) for monthday in monthdays)


def _format_habit_cadence(habit: Habit) -> str:
    cadence_frequency = getattr(habit, "cadence_frequency", "daily")
    target_per_cycle = getattr(habit, "target_per_cycle", 1)
    cadence_weekdays = _format_cadence_weekdays(habit)
    cadence_monthdays = _format_cadence_monthdays(habit)
    cadence = f"{cadence_frequency}:{target_per_cycle}:{cadence_weekdays}"
    if cadence_monthdays == "-":
        return cadence
    return f"{cadence}:monthdays={cadence_monthdays}"


def _format_habit_summary(habit: Habit) -> str:
    status = "deleted" if habit.deleted_at is not None else habit.status
    return (
        f"{habit.id}\t{status}\t{habit.start_date}\t{habit.duration_days}\t{_format_habit_cadence(habit)}\t"
        f"{habit.task_id or '-'}\t{habit.title}"
    )


def _format_habit_summary_with_stats(overview: dict[str, object]) -> str:
    habit, stats = _extract_habit_overview(overview)
    status = "deleted" if habit.deleted_at is not None else habit.status
    return (
        f"{habit.id}\t{status}\t{habit.start_date}\t{habit.duration_days}\t{_format_habit_cadence(habit)}\t"
        f"{stats['progress_percentage']:.1f}\t{stats['current_streak']}\t"
        f"{stats['longest_streak']}\t{habit.title}"
    )


def _format_habit_detail(habit: Habit, stats: dict[str, object]) -> str:
    return "\n".join(
        (
            f"id: {habit.id}",
            f"title: {habit.title}",
            f"description: {habit.description or '-'}",
            f"status: {habit.status}",
            f"start_date: {habit.start_date}",
            f"end_date: {habit.end_date}",
            f"duration_days: {habit.duration_days}",
            f"cadence_frequency: {getattr(habit, 'cadence_frequency', 'daily')}",
            f"cadence_weekdays: {_format_cadence_weekdays(habit)}",
            f"cadence_monthdays: {_format_cadence_monthdays(habit)}",
            f"target_per_cycle: {getattr(habit, 'target_per_cycle', 1)}",
            f"task_id: {habit.task_id or '-'}",
            f"progress_percentage: {stats['progress_percentage']:.1f}",
            f"total_cycles: {stats['total_cycles']}",
            f"eligible_cycles: {stats['eligible_cycles']}",
            f"completed_cycles: {stats['completed_cycles']}",
            f"current_streak: {stats['current_streak']}",
            f"longest_streak: {stats['longest_streak']}",
            f"current_cycle_start: {stats['current_cycle_start']}",
            f"current_cycle_end: {stats['current_cycle_end']}",
            f"current_week_start: {stats['current_week_start']}",
            f"current_week_end: {stats['current_week_end']}",
            f"completed_actions: {stats['completed_actions']}",
            f"missed_actions: {stats['missed_actions']}",
            f"skipped_actions: {stats['skipped_actions']}",
            f"total_actions: {stats['total_actions']}",
            f"created_at: {format_timestamp(habit.created_at)}",
            f"updated_at: {format_timestamp(habit.updated_at)}",
            f"deleted_at: {format_timestamp(habit.deleted_at)}",
        )
    )


def _extract_habit_overview(overview: dict[str, object]) -> tuple[Habit, dict[str, object]]:
    habit = overview.get("habit")
    stats = overview.get("stats")
    if not isinstance(habit, Habit) or not isinstance(stats, dict):
        raise RuntimeError("Habit overview payload is invalid.")
    return habit, stats


def _format_habit_stats(stats: dict[str, object]) -> str:
    cadence_weekdays = cast(tuple[str, ...] | None, stats["cadence_weekdays"])
    cadence_weekdays_text = "-" if not cadence_weekdays else ",".join(cadence_weekdays)
    cadence_monthdays = cast(tuple[int, ...] | None, stats["cadence_monthdays"])
    cadence_monthdays_text = (
        "-" if not cadence_monthdays else ",".join(str(day) for day in cadence_monthdays)
    )
    return "\n".join(
        (
            f"habit_id: {stats['habit_id']}",
            f"cadence_frequency: {stats['cadence_frequency']}",
            f"cadence_weekdays: {cadence_weekdays_text}",
            f"cadence_monthdays: {cadence_monthdays_text}",
            f"target_per_cycle: {stats['target_per_cycle']}",
            f"total_actions: {stats['total_actions']}",
            f"completed_actions: {stats['completed_actions']}",
            f"missed_actions: {stats['missed_actions']}",
            f"skipped_actions: {stats['skipped_actions']}",
            f"total_cycles: {stats['total_cycles']}",
            f"eligible_cycles: {stats['eligible_cycles']}",
            f"completed_cycles: {stats['completed_cycles']}",
            f"progress_percentage: {stats['progress_percentage']:.1f}",
            f"current_streak: {stats['current_streak']}",
            f"longest_streak: {stats['longest_streak']}",
            f"current_cycle_start: {stats['current_cycle_start']}",
            f"current_cycle_end: {stats['current_cycle_end']}",
            f"current_week_start: {stats['current_week_start']}",
            f"current_week_end: {stats['current_week_end']}",
        )
    )


async def handle_habit_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            habit = await habit_services.create_habit(
                session,
                title=args.title,
                description=args.description,
                start_date=args.start_date,
                duration_days=args.duration_days,
                cadence_frequency=args.cadence_frequency,
                cadence_weekdays=_resolve_weekday_selection(args),
                cadence_monthdays=args.monthdays,
                target_per_cycle=args.target_per_cycle,
                task_id=args.task_id,
            )
        except (
            habit_services.HabitValidationError,
            habit_services.HabitTaskReferenceNotFoundError,
            habit_services.InvalidHabitOperationError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created habit {habit.id}")
    return 0


async def handle_habit_list_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            if args.with_stats:
                overviews = await habit_services.list_habit_overviews(
                    session,
                    status=args.status,
                    title=args.title,
                    active_window_only=args.active_window_only,
                    limit=args.limit,
                    offset=args.offset,
                )
                total_count = (
                    await habit_services.count_habits(
                        session,
                        status=args.status,
                        title=args.title,
                        active_window_only=args.active_window_only,
                    )
                    if args.count
                    else None
                )
                trailer_lines = () if total_count is None else (f"Total habits: {total_count}",)
                if args.json:
                    print_json_items(overviews, total_count=total_count)
                    return 0
                print_summary_rows(
                    items=overviews,
                    columns=HABIT_SUMMARY_WITH_STATS_COLUMNS,
                    row_formatter=_format_habit_summary_with_stats,
                    empty_message="No habits found.",
                    trailer_lines=trailer_lines,
                )
                return 0
            habits = await habit_services.list_habits(
                session,
                status=args.status,
                title=args.title,
                active_window_only=args.active_window_only,
                limit=args.limit,
                offset=args.offset,
            )
            total_count = (
                await habit_services.count_habits(
                    session,
                    status=args.status,
                    title=args.title,
                    active_window_only=args.active_window_only,
                )
                if args.count
                else None
            )
        except habit_services.HabitValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(habits, total_count=total_count)
        return 0
    trailer_lines = () if total_count is None else (f"Total habits: {total_count}",)
    print_summary_rows(
        items=habits,
        columns=HABIT_SUMMARY_COLUMNS,
        row_formatter=_format_habit_summary,
        empty_message="No habits found.",
        trailer_lines=trailer_lines,
    )
    return 0


async def handle_habit_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            overview = await habit_services.get_habit_overview(
                session,
                habit_id=args.habit_id,
            )
        except habit_services.HabitNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    habit, stats = _extract_habit_overview(overview)
    if args.json:
        print_json_payload(overview)
        return 0
    print(_format_habit_detail(habit, stats))
    return 0


async def handle_habit_update_async(args: argparse.Namespace) -> int:
    conflicts = (
        (
            args.clear_description and args.description is not None,
            "--description",
            "--clear-description",
        ),
        (
            args.clear_task and args.task_id is not None,
            "--task-id",
            "--clear-task",
        ),
        (
            args.clear_weekdays and (args.weekdays is not None or args.weekends_only),
            "--weekdays / --weekends-only",
            "--clear-weekdays",
        ),
        (
            args.clear_monthdays and args.monthdays is not None,
            "--monthdays",
            "--clear-monthdays",
        ),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicts)
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            habit = await habit_services.update_habit(
                session,
                habit_id=args.habit_id,
                title=args.title,
                description=args.description,
                clear_description=args.clear_description,
                start_date=args.start_date,
                duration_days=args.duration_days,
                cadence_frequency=args.cadence_frequency,
                cadence_weekdays=_resolve_weekday_selection(args),
                clear_weekdays=args.clear_weekdays,
                cadence_monthdays=args.monthdays,
                clear_monthdays=args.clear_monthdays,
                target_per_cycle=args.target_per_cycle,
                status=args.status,
                task_id=args.task_id,
                clear_task=args.clear_task,
            )
        except (
            habit_services.HabitNotFoundError,
            habit_services.HabitValidationError,
            habit_services.HabitTaskReferenceNotFoundError,
            habit_services.InvalidHabitOperationError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated habit {habit.id}")
    return 0


async def handle_habit_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            await habit_services.delete_habit(session, habit_id=args.habit_id)
        except habit_services.HabitNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted habit {args.habit_id}")
    return 0


async def handle_habit_stats_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            stats = await habit_services.get_habit_stats(session, habit_id=args.habit_id)
        except habit_services.HabitNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_habit_stats(stats))
    return 0


async def handle_habit_task_associations_async(_: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        associations = await habit_services.get_habit_task_associations(session)
    if not associations:
        print("No task associations found.")
        return 0
    print(format_summary_header(HABIT_TASK_ASSOCIATION_COLUMNS))
    for task_id, habits in associations.items():
        for habit in habits:
            print(f"{task_id}\t{habit.id}\t{habit.status}\t{habit.start_date}\t{habit.title}")
    return 0


async def handle_habit_batch_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        result = await habit_services.batch_delete_habits(
            session,
            habit_ids=list(args.habit_ids),
        )
    return print_batch_result(
        success_label="Deleted habits",
        success_count=result.deleted_count,
        failed_label="Failed habit IDs",
        result=result,
    )
