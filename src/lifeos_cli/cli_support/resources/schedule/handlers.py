"""CLI handlers for the schedule resource."""

from __future__ import annotations

import argparse
from datetime import date

from lifeos_cli.application.time_preferences import get_operational_date
from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_payload
from lifeos_cli.cli_support.output_utils import format_summary_header, format_timestamp
from lifeos_cli.cli_support.time_args import (
    DateArgumentError,
    resolve_date_selection_arguments,
)
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import planning_lifecycle as planning_lifecycle_services
from lifeos_cli.db.services import schedules as schedule_services

SCHEDULE_TASK_COLUMNS = (
    "task_id",
    "status",
    "planning_cycle_type",
    "planning_cycle_start_date",
    "planning_cycle_end_date",
    "content",
)
SCHEDULE_HABIT_ACTION_COLUMNS = (
    "habit_action_id",
    "status",
    "action_date",
    "habit_title",
)
SCHEDULE_EVENT_COLUMNS = (
    "event_id",
    "event_type",
    "start_time",
    "end_time",
    "title",
)


def _format_schedule_task(item: schedule_services.ScheduleTaskItem) -> str:
    return (
        f"  {item.id}\t{item.status}\t{item.planning_cycle_type}\t"
        f"{item.planning_cycle_start_date}\t{item.planning_cycle_end_date}\t{item.content}"
    )


def _format_schedule_habit_action(item: schedule_services.ScheduleHabitActionItem) -> str:
    return f"  {item.id}\t{item.status}\t{item.action_date}\t{item.habit_title}"


def _format_schedule_event_end_time(item: schedule_services.ScheduleEventItem) -> str:
    if item.end_time is None and item.event_type == "deadline":
        return format_timestamp(item.start_time)
    return format_timestamp(item.end_time)


def _format_schedule_event(item: schedule_services.ScheduleEventItem) -> str:
    return (
        f"  {item.id}\t{item.event_type}\t{format_timestamp(item.start_time)}\t"
        f"{_format_schedule_event_end_time(item)}\t{item.title}"
    )


def _format_schedule_day(day: schedule_services.ScheduleDay) -> str:
    lines = [f"date: {day.local_date}", "tasks:"]
    if day.tasks:
        lines.append(f"  {format_summary_header(SCHEDULE_TASK_COLUMNS)}")
        lines.extend(_format_schedule_task(item) for item in day.tasks)
    else:
        lines.append("  -")

    lines.append("habit_actions:")
    if day.habit_actions:
        lines.append(f"  {format_summary_header(SCHEDULE_HABIT_ACTION_COLUMNS)}")
        lines.extend(_format_schedule_habit_action(item) for item in day.habit_actions)
    else:
        lines.append("  -")

    lines.append("events:")
    if day.events:
        lines.append(f"  {format_summary_header(SCHEDULE_EVENT_COLUMNS)}")
        lines.extend(_format_schedule_event(item) for item in day.events)
    else:
        lines.append("  -")
    return "\n".join(lines)


async def handle_schedule_show_async(args: argparse.Namespace) -> int:
    target_date = args.target_date or get_operational_date()
    async with db_session.session_scope() as session:
        await planning_lifecycle_services.reconcile_planning_habit_action_lifecycle(
            session,
            reference_date=target_date,
            start_date=date.min,
            end_date=target_date,
        )
        day = await schedule_services.get_schedule_for_date(
            session,
            target_date=target_date,
            hide_overdue_unfinished=args.hide_overdue_unfinished,
        )
    if args.json:
        print_json_payload(day)
        return 0
    print(_format_schedule_day(day))
    return 0


async def handle_schedule_list_async(args: argparse.Namespace) -> int:
    try:
        date_selection = resolve_date_selection_arguments(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    if not date_selection.date_values and (
        date_selection.start_date is None or date_selection.end_date is None
    ):
        return cli_handler_utils.print_cli_error(
            DateArgumentError(
                "Provide --date one or more times, or provide both --start-date and --end-date."
            )
        )
    async with db_session.session_scope() as session:
        if date_selection.date_values:
            reference_date = max(date_selection.date_values)
            await planning_lifecycle_services.reconcile_planning_habit_action_lifecycle(
                session,
                reference_date=reference_date,
                start_date=date.min,
                end_date=reference_date,
            )
            days = [
                await schedule_services.get_schedule_for_date(
                    session,
                    target_date=target_date,
                    hide_overdue_unfinished=args.hide_overdue_unfinished,
                )
                for target_date in date_selection.date_values
            ]
        else:
            assert date_selection.start_date is not None
            assert date_selection.end_date is not None
            await planning_lifecycle_services.reconcile_planning_habit_action_lifecycle(
                session,
                reference_date=date_selection.end_date,
                start_date=date.min,
                end_date=date_selection.end_date,
            )
            days = await schedule_services.list_schedule_in_range(
                session,
                start_date=date_selection.start_date,
                end_date=date_selection.end_date,
                hide_overdue_unfinished=args.hide_overdue_unfinished,
            )
    if args.json:
        print_json_payload(days)
        return 0
    print("\n\n".join(_format_schedule_day(day) for day in days))
    return 0
