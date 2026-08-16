"""CLI handlers for the event resource."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import (
    DateArgumentError,
    resolve_exclusive_date_or_datetime_query,
)
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import events as event_services

EVENT_SUMMARY_COLUMNS = (
    "event_id",
    "status",
    "event_type",
    "start_time",
    "end_time",
    "task_id",
    "title",
)


def _build_recurrence_rule_from_args(args: argparse.Namespace) -> dict[str, object] | None:
    """Build structured recurrence rule details from CLI arguments."""
    recurrence_rule: dict[str, object] = {}
    if getattr(args, "recurrence_weekdays", None) is not None:
        recurrence_rule["byweekday"] = args.recurrence_weekdays
    if getattr(args, "recurrence_month_days", None) is not None:
        recurrence_rule["bymonthday"] = args.recurrence_month_days
    if getattr(args, "recurrence_months", None) is not None:
        recurrence_rule["bymonth"] = args.recurrence_months
    if getattr(args, "recurrence_weekday_ordinals", None) is not None:
        recurrence_rule["byweekday_ordinals"] = args.recurrence_weekday_ordinals
    return recurrence_rule or None


def _format_event_summary(event: event_services.EventOccurrence | event_services.EventView) -> str:
    status = "deleted" if event.deleted_at is not None else event.status
    return (
        f"{event.id}\t{status}\t{event.event_type}\t{format_timestamp(event.start_time)}\t"
        f"{format_timestamp(event.end_time)}\t{event.task_id or '-'}\t{event.title}"
    )


def _format_event_detail(event: event_services.EventView) -> str:
    tag_names = ", ".join(tag.name for tag in event.tags) if event.tags else "-"
    person_names = ", ".join(person.name for person in event.person) if event.person else "-"
    return "\n".join(
        (
            f"id: {event.id}",
            f"title: {event.title}",
            f"description: {event.description or '-'}",
            f"status: {event.status}",
            f"event_type: {event.event_type}",
            f"priority: {event.priority}",
            f"is_all_day: {event.is_all_day}",
            f"start_time: {format_timestamp(event.start_time)}",
            f"end_time: {format_timestamp(event.end_time)}",
            f"recurrence_frequency: {event.recurrence_frequency or '-'}",
            f"recurrence_interval: {event.recurrence_interval or '-'}",
            f"recurrence_count: {event.recurrence_count or '-'}",
            f"recurrence_until: {format_timestamp(event.recurrence_until)}",
            f"recurrence_rule: {event.recurrence_rule or '-'}",
            f"recurrence_parent_event_id: {event.recurrence_parent_event_id or '-'}",
            f"recurrence_instance_start: {format_timestamp(event.recurrence_instance_start)}",
            f"area_id: {event.area_id or '-'}",
            f"task_id: {event.task_id or '-'}",
            f"tags: {tag_names}",
            f"person: {person_names}",
            f"created_at: {format_timestamp(event.created_at)}",
            f"updated_at: {format_timestamp(event.updated_at)}",
            f"deleted_at: {format_timestamp(event.deleted_at)}",
        )
    )


async def handle_event_add_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            event = await event_services.create_event(
                session,
                payload=event_services.EventCreateInput(
                    title=args.title,
                    description=args.description,
                    start_time=args.start_time,
                    end_time=args.end_time,
                    priority=args.priority,
                    status=args.status,
                    event_type=args.event_type,
                    is_all_day=args.all_day,
                    area_id=args.area_id,
                    task_id=args.task_id,
                    tag_ids=args.tag_ids,
                    person_ids=args.person_ids,
                    recurrence_frequency=args.recurrence_frequency,
                    recurrence_interval=args.recurrence_interval,
                    recurrence_count=args.recurrence_count,
                    recurrence_until=args.recurrence_until,
                    recurrence_rule=_build_recurrence_rule_from_args(args),
                ),
            )
        except (
            event_services.EventAreaReferenceNotFoundError,
            event_services.EventTaskReferenceNotFoundError,
            event_services.EventValidationError,
            LookupError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created event {event.id}")
    return 0


async def handle_event_list_async(args: argparse.Namespace) -> int:
    try:
        query = resolve_exclusive_date_or_datetime_query(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
            window_start=args.window_start,
            window_end=args.window_end,
        )
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        try:
            events = await event_services.list_events(
                session,
                query=event_services.EventListInput(
                    filters=event_services.EventQueryFilters(
                        title_contains=args.title_contains,
                        status=args.status,
                        event_type=args.event_type,
                        area_id=args.area_id,
                        task_id=args.task_id,
                        person_id=args.person_id,
                        tag_id=args.tag_id,
                        date_values=query.date_values,
                        start_date=query.start_date,
                        end_date=query.end_date,
                        window_start=query.window_start,
                        window_end=query.window_end,
                    ),
                    limit=args.limit,
                    offset=args.offset,
                ),
            )
        except event_services.EventValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(events)
        return 0
    print_summary_rows(
        items=events,
        columns=EVENT_SUMMARY_COLUMNS,
        row_formatter=_format_event_summary,
        empty_message="No events found.",
    )
    return 0


async def handle_event_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        event = await event_services.get_event(
            session,
            event_id=args.event_id,
        )
    if event is None:
        return cli_handler_utils.print_missing_record_error("Event", args.event_id)
    if args.json:
        print_json_payload(event)
        return 0
    print(_format_event_detail(event))
    return 0


async def handle_event_update_async(args: argparse.Namespace) -> int:
    conflicts = (
        (
            args.clear_description and args.description is not None,
            "--description",
            "--clear-description",
        ),
        (args.clear_end_time and args.end_time is not None, "--end-time", "--clear-end-time"),
        (args.clear_area and args.area_id is not None, "--area-id", "--clear-area"),
        (args.clear_task and args.task_id is not None, "--task-id", "--clear-task"),
        (args.clear_tags and args.tag_ids is not None, "--tag-id", "--clear-tags"),
        (args.clear_person and args.person_ids is not None, "--person-id", "--clear-person"),
        (
            args.clear_recurrence
            and any(
                value is not None
                for value in (
                    args.recurrence_frequency,
                    args.recurrence_interval,
                    args.recurrence_count,
                    args.recurrence_until,
                    args.recurrence_weekdays,
                    args.recurrence_month_days,
                    args.recurrence_months,
                    args.recurrence_weekday_ordinals,
                )
            ),
            "--recurrence-*",
            "--clear-recurrence",
        ),
        (
            args.clear_recurrence_rule
            and any(
                value is not None
                for value in (
                    args.recurrence_weekdays,
                    args.recurrence_month_days,
                    args.recurrence_months,
                    args.recurrence_weekday_ordinals,
                )
            ),
            "--recurrence-*",
            "--clear-recurrence-rule",
        ),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicts)
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            event = await event_services.update_event(
                session,
                event_id=args.event_id,
                changes=event_services.EventUpdateInput(
                    title=args.title,
                    description=args.description,
                    clear_description=args.clear_description,
                    start_time=args.start_time,
                    end_time=args.end_time,
                    clear_end_time=args.clear_end_time,
                    priority=args.priority,
                    status=args.status,
                    event_type=args.event_type,
                    is_all_day=args.all_day,
                    area_id=args.area_id,
                    clear_area=args.clear_area,
                    task_id=args.task_id,
                    clear_task=args.clear_task,
                    tag_ids=args.tag_ids,
                    clear_tags=args.clear_tags,
                    person_ids=args.person_ids,
                    clear_person=args.clear_person,
                    recurrence_frequency=args.recurrence_frequency,
                    recurrence_interval=args.recurrence_interval,
                    recurrence_count=args.recurrence_count,
                    recurrence_until=args.recurrence_until,
                    recurrence_rule=_build_recurrence_rule_from_args(args),
                    clear_recurrence_rule=args.clear_recurrence_rule,
                    clear_recurrence=args.clear_recurrence,
                ),
                scope=args.scope,
                instance_start=args.instance_start,
            )
        except (
            event_services.EventNotFoundError,
            event_services.EventAreaReferenceNotFoundError,
            event_services.EventTaskReferenceNotFoundError,
            event_services.EventValidationError,
            LookupError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated event {event.id}")
    return 0


async def handle_event_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            await event_services.delete_event(
                session,
                event_id=args.event_id,
                scope=args.scope,
                instance_start=args.instance_start,
            )
        except event_services.EventNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
        except event_services.EventValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted event {args.event_id}")
    return 0


async def handle_event_batch_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        result = await event_services.batch_delete_events(
            session,
            event_ids=list(args.event_ids),
        )
    return print_batch_result(
        success_label="Deleted events",
        success_count=result.deleted_count,
        failed_label="Failed event IDs",
        result=result,
    )
