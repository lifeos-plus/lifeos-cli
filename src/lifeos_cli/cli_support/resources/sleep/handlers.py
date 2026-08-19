"""Sleep command handlers."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import DateArgumentError, resolve_date_selection_arguments
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.sleep_segment import SleepSegment
from lifeos_cli.db.services import sleep as sleep_services

SLEEP_SEGMENT_SUMMARY_COLUMNS = (
    "segment_id",
    "sleep_date",
    "start_at",
    "end_at",
    "duration_minutes",
)

SLEEP_SUMMARY_COLUMNS = (
    "sleep_date",
    "total_minutes",
    "segment_count",
    "first_start_at",
    "last_end_at",
)


def _segment_payload(segment: SleepSegment) -> dict[str, Any]:
    return {
        "id": str(segment.id),
        "sleep_date": segment.sleep_date.isoformat(),
        "start_at": format_timestamp(segment.start_at),
        "end_at": format_timestamp(segment.end_at),
        "duration_minutes": segment.duration_minutes,
        "created_at": format_timestamp(segment.created_at),
        "updated_at": format_timestamp(segment.updated_at),
    }


def _format_segment_summary(segment: SleepSegment) -> str:
    return (
        f"{segment.id}\t{segment.sleep_date.isoformat()}\t"
        f"{format_timestamp(segment.start_at)}\t{format_timestamp(segment.end_at)}\t"
        f"{segment.duration_minutes}"
    )


def _summary_payload(summary: sleep_services.SleepDailySummary) -> dict[str, Any]:
    return {
        "sleep_date": summary.sleep_date.isoformat(),
        "total_minutes": summary.total_minutes,
        "segment_count": summary.segment_count,
        "first_start_at": (
            format_timestamp(summary.first_start_at) if summary.first_start_at else None
        ),
        "last_end_at": (format_timestamp(summary.last_end_at) if summary.last_end_at else None),
    }


def _format_summary_row(summary: sleep_services.SleepDailySummary) -> str:
    return (
        f"{summary.sleep_date.isoformat()}\t{summary.total_minutes}\t"
        f"{summary.segment_count}\t"
        f"{format_timestamp(summary.first_start_at) if summary.first_start_at else '-'}\t"
        f"{format_timestamp(summary.last_end_at) if summary.last_end_at else '-'}"
    )


def _resolve_date_selection(
    args: argparse.Namespace,
) -> tuple[date | None, date | None, date | None]:
    try:
        resolved = resolve_date_selection_arguments(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        raise DateArgumentError(str(exc)) from exc
    sleep_date = resolved.date_values[0] if len(resolved.date_values) == 1 else None
    return sleep_date, resolved.start_date, resolved.end_date


async def handle_sleep_add_async(args: argparse.Namespace) -> int:
    """Create one sleep segment."""
    try:
        async with db_session.session_scope() as session:
            segment = await sleep_services.create_sleep_segment(
                session,
                start_at=to_storage_timezone(args.start_time),
                end_at=to_storage_timezone(args.end_time),
            )
    except sleep_services.SleepValidationError as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Created sleep segment {segment.id} (sleep_date={segment.sleep_date.isoformat()})")
    return 0


async def handle_sleep_list_async(args: argparse.Namespace) -> int:
    """List sleep segments."""
    try:
        sleep_date, start_date, end_date = _resolve_date_selection(args)
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        segments = await sleep_services.list_sleep_segments(
            session,
            sleep_date=sleep_date,
            start_date=start_date,
            end_date=end_date,
            limit=args.limit,
            offset=args.offset,
        )
    if args.json:
        print_json_items([_segment_payload(segment) for segment in segments])
        return 0
    print_summary_rows(
        items=segments,
        columns=SLEEP_SEGMENT_SUMMARY_COLUMNS,
        row_formatter=_format_segment_summary,
        empty_message="No sleep segments found.",
    )
    return 0


async def handle_sleep_show_async(args: argparse.Namespace) -> int:
    """Show one sleep segment."""
    async with db_session.session_scope() as session:
        segment = await sleep_services.get_sleep_segment(
            session,
            segment_id=args.segment_id,
        )
        if segment is None:
            return cli_handler_utils.print_missing_record_error(
                "Sleep segment",
                args.segment_id,
            )
    if args.json:
        print_json_payload(_segment_payload(segment))
        return 0
    print(f"sleep_segment_id: {segment.id}")
    print(f"sleep_date: {segment.sleep_date.isoformat()}")
    print(f"start_at: {format_timestamp(segment.start_at)}")
    print(f"end_at: {format_timestamp(segment.end_at)}")
    print(f"duration_minutes: {segment.duration_minutes}")
    print(f"created_at: {format_timestamp(segment.created_at)}")
    print(f"updated_at: {format_timestamp(segment.updated_at)}")
    return 0


async def handle_sleep_update_async(args: argparse.Namespace) -> int:
    """Update one sleep segment."""
    try:
        async with db_session.session_scope() as session:
            segment = await sleep_services.update_sleep_segment(
                session,
                segment_id=args.segment_id,
                start_at=(to_storage_timezone(args.start_time) if args.start_time else None),
                end_at=to_storage_timezone(args.end_time) if args.end_time else None,
            )
    except (
        sleep_services.SleepSegmentNotFoundError,
        sleep_services.SleepValidationError,
    ) as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Updated sleep segment {segment.id}")
    return 0


async def handle_sleep_delete_async(args: argparse.Namespace) -> int:
    """Soft-delete one or more sleep segments."""
    failed_ids: list[object] = []
    errors: list[str] = []
    for segment_id in args.segment_ids:
        try:
            async with db_session.session_scope() as session:
                await sleep_services.delete_sleep_segment(
                    session,
                    segment_id=segment_id,
                )
        except sleep_services.SleepSegmentNotFoundError as exc:
            failed_ids.append(segment_id)
            errors.append(str(exc))
    for segment_id in args.segment_ids:
        if segment_id not in failed_ids:
            print(f"Soft-deleted sleep segment {segment_id}")
    for error in errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if failed_ids else 0


async def handle_sleep_summary_async(args: argparse.Namespace) -> int:
    """Show daily sleep summaries."""
    try:
        _, start_date, end_date = _resolve_date_selection(args)
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        summaries = await sleep_services.get_sleep_daily_summaries(
            session,
            start_date=start_date,
            end_date=end_date,
        )
    if args.json:
        print_json_items([_summary_payload(summary) for summary in summaries])
        return 0
    print_summary_rows(
        items=summaries,
        columns=SLEEP_SUMMARY_COLUMNS,
        row_formatter=_format_summary_row,
        empty_message="No sleep summaries found.",
    )
    return 0
