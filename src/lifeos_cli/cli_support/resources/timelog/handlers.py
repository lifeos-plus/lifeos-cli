"""CLI handlers for the timelog resource."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_id_lines,
    format_summary_header,
    format_timestamp,
    print_batch_result,
    print_summary_rows,
)
from lifeos_cli.cli_support.resources.timelog.bulk_add import (
    BulkTimelogDraft,
    parse_bulk_timelog_text,
)
from lifeos_cli.cli_support.time_args import (
    DateArgumentError,
    resolve_date_selection_arguments,
    resolve_exclusive_date_or_datetime_query,
    resolve_required_date_interval_arguments,
)
from lifeos_cli.config import ConfigurationError
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import timelog_stats
from lifeos_cli.db.services import timelogs as timelog_services
from lifeos_cli.db.services.read_models import TimelogView

TIMELOG_SUMMARY_COLUMNS = (
    "timelog_id",
    "status",
    "start_time",
    "end_time",
    "task_id",
    "title",
)

TIMELOG_SUMMARY_COLUMNS_WITH_COUNTS = (
    "timelog_id",
    "status",
    "start_time",
    "end_time",
    "task_id",
    "linked_notes_count",
    "title",
)

TIMELOG_BULK_PREVIEW_COLUMNS = (
    "line",
    "start_time",
    "end_time",
    "minutes",
    "title",
    "warnings",
)


def _format_timelog_summary(timelog: TimelogView, *, include_counts: bool = False) -> str:
    status = "deleted" if timelog.deleted_at is not None else timelog.tracking_method
    if not include_counts:
        return (
            f"{timelog.id}\t{status}\t{format_timestamp(timelog.start_time)}\t"
            f"{format_timestamp(timelog.end_time)}\t{timelog.task_id or '-'}\t{timelog.title}"
        )
    return (
        f"{timelog.id}\t{status}\t{format_timestamp(timelog.start_time)}\t"
        f"{format_timestamp(timelog.end_time)}\t{timelog.task_id or '-'}\t"
        f"{timelog.linked_notes_count}\t{timelog.title}"
    )


def _format_timelog_detail(timelog: TimelogView) -> str:
    tag_names = ", ".join(tag.name for tag in timelog.tags) if timelog.tags else "-"
    person_names = ", ".join(person.name for person in timelog.person) if timelog.person else "-"
    return "\n".join(
        (
            f"id: {timelog.id}",
            f"title: {timelog.title}",
            f"tracking_method: {timelog.tracking_method}",
            f"start_time: {format_timestamp(timelog.start_time)}",
            f"end_time: {format_timestamp(timelog.end_time)}",
            f"location: {timelog.location or '-'}",
            f"energy_level: {timelog.energy_level if timelog.energy_level is not None else '-'}",
            f"notes: {timelog.notes or '-'}",
            f"area_id: {timelog.area_id or '-'}",
            f"task_id: {timelog.task_id or '-'}",
            f"linked_notes_count: {timelog.linked_notes_count}",
            f"tags: {tag_names}",
            f"person: {person_names}",
            f"created_at: {format_timestamp(timelog.created_at)}",
            f"updated_at: {format_timestamp(timelog.updated_at)}",
            f"deleted_at: {format_timestamp(timelog.deleted_at)}",
        )
    )


def _resolve_bulk_timelog_input_text(args: argparse.Namespace) -> str:
    provided_sources = sum(
        1
        for candidate in (args.entry_lines is not None, args.stdin, args.file is not None)
        if candidate
    )
    if provided_sources != 1:
        raise ConfigurationError(
            "Provide quick batch timelog input with exactly one source: `--entry`, `--stdin`, "
            "or `--file`."
        )
    if args.entry_lines is not None:
        content = "\n".join(args.entry_lines)
    elif args.stdin:
        content = sys.stdin.read()
    else:
        try:
            content = Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Could not read quick batch timelog input from {args.file}: {exc}"
            ) from exc
    normalized = content.rstrip("\n")
    if not normalized.strip():
        raise ConfigurationError("Quick batch timelog input must not be empty.")
    return normalized


def _validate_single_timelog_add_args(args: argparse.Namespace) -> None:
    if args.title is None:
        raise ConfigurationError("Single-record mode requires `title`.")
    if args.start_time is None or args.end_time is None:
        raise ConfigurationError(
            "Single-record mode requires both `--start-time` and `--end-time`."
        )
    if args.first_start_time is not None:
        raise ConfigurationError("Use `--first-start-time` only with quick batch mode.")
    if args.yes:
        raise ConfigurationError("Use `--yes` only with quick batch mode.")


def _validate_bulk_timelog_add_args(args: argparse.Namespace) -> None:
    if args.title is not None:
        raise ConfigurationError("Quick batch mode cannot be combined with single-record `title`.")
    if args.start_time is not None:
        raise ConfigurationError("Quick batch mode uses `--first-start-time`, not `--start-time`.")
    if args.end_time is not None:
        raise ConfigurationError("Quick batch mode cannot be combined with `--end-time`.")


def _format_bulk_timelog_preview_row(draft: BulkTimelogDraft) -> str:
    minutes = int((draft.end_time - draft.start_time).total_seconds() // 60)
    warning_text = "; ".join(draft.warnings) if draft.warnings else "-"
    return (
        f"{draft.line_number}\t{format_timestamp(draft.start_time)}\t"
        f"{format_timestamp(draft.end_time)}\t{minutes}\t{draft.title}\t{warning_text}"
    )


def _print_bulk_timelog_preview(drafts: list[BulkTimelogDraft]) -> None:
    total_minutes = sum(
        int((draft.end_time - draft.start_time).total_seconds() // 60) for draft in drafts
    )
    print("Quick batch timelog preview:")
    print(format_summary_header(TIMELOG_BULK_PREVIEW_COLUMNS))
    for draft in drafts:
        print(_format_bulk_timelog_preview_row(draft))
    print(f"Total timelogs: {len(drafts)}")
    print(f"Total minutes: {total_minutes}")


def _read_bulk_timelog_confirmation() -> str:
    print("Type `yes` to create these timelogs: ", end="", flush=True)
    response = sys.stdin.readline()
    if response == "":
        raise ConfigurationError(
            "Quick batch timelog confirmation aborted before any changes were written."
        )
    return response.strip().lower()


def _format_timelog_stats_report(report: timelog_stats.TimelogStatsReport) -> str:
    lines = [
        f"granularity: {report.granularity}",
        f"start_date: {report.start_date.isoformat()}",
        f"end_date: {report.end_date.isoformat()}",
        f"timezone: {report.timezone}",
    ]
    if not report.rows:
        lines.append("No timelog stats found.")
        return "\n".join(lines)
    lines.extend(
        (
            "area_stats:",
            "area_id\tarea_name\tminutes\ttimelog_count",
        )
    )
    lines.extend(
        f"{row.area_id}\t{row.area_name or '-'}\t{row.minutes}\t{row.timelog_count}"
        for row in report.rows
    )
    return "\n".join(lines)


async def handle_timelog_add_async(args: argparse.Namespace) -> int:
    if args.entry_lines is not None or args.stdin or args.file is not None:
        _validate_bulk_timelog_add_args(args)
        raw_text = _resolve_bulk_timelog_input_text(args)
        async with db_session.session_scope() as session:
            first_start_time = args.first_start_time
            if first_start_time is None:
                first_start_time = await timelog_services.get_latest_timelog_end_time(session)
            if first_start_time is None:
                raise ConfigurationError(
                    "Quick batch mode requires `--first-start-time` when no active timelog "
                    "exists to provide the initial cursor."
                )
            drafts = parse_bulk_timelog_text(raw_text, first_start_time=first_start_time)
            _print_bulk_timelog_preview(drafts)
            if not args.stdin and not args.yes and _read_bulk_timelog_confirmation() != "yes":
                print("Quick batch timelog creation cancelled. No changes were written.")
                return 1
            created_ids = []
            try:
                for draft in drafts:
                    timelog = await timelog_services.create_timelog(
                        session,
                        payload=timelog_services.TimelogCreateInput(
                            title=draft.title,
                            start_time=draft.start_time,
                            end_time=draft.end_time,
                            tracking_method=args.tracking_method,
                            location=args.location,
                            energy_level=args.energy_level,
                            notes=args.notes,
                            area_id=args.area_id,
                            task_id=args.task_id,
                            tag_ids=args.tag_ids,
                            person_ids=args.person_ids,
                        ),
                    )
                    created_ids.append(timelog.id)
            except (
                timelog_services.TimelogAreaReferenceNotFoundError,
                timelog_services.TimelogTaskReferenceNotFoundError,
                timelog_services.TimelogValidationError,
                LookupError,
            ) as exc:
                return cli_handler_utils.print_cli_error(exc)
        print(f"Created timelogs: {len(created_ids)}")
        print(format_id_lines("timelog_ids", created_ids))
        return 0

    _validate_single_timelog_add_args(args)
    async with db_session.session_scope() as session:
        try:
            timelog = await timelog_services.create_timelog(
                session,
                payload=timelog_services.TimelogCreateInput(
                    title=args.title,
                    start_time=args.start_time,
                    end_time=args.end_time,
                    tracking_method=args.tracking_method,
                    location=args.location,
                    energy_level=args.energy_level,
                    notes=args.notes,
                    area_id=args.area_id,
                    task_id=args.task_id,
                    tag_ids=args.tag_ids,
                    person_ids=args.person_ids,
                ),
            )
        except (
            timelog_services.TimelogAreaReferenceNotFoundError,
            timelog_services.TimelogTaskReferenceNotFoundError,
            timelog_services.TimelogValidationError,
            LookupError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Created timelog {timelog.id}")
    return 0


async def handle_timelog_list_async(args: argparse.Namespace) -> int:
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
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(
        (
            (
                args.without_area and (args.area_id is not None or args.area_name is not None),
                "an area filter",
                "--without-area",
            ),
            (args.without_task and args.task_id is not None, "--task-id", "--without-task"),
        )
    )
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            list_input = timelog_services.TimelogListInput(
                filters=timelog_services.TimelogQueryFilters(
                    title_contains=args.title_contains,
                    notes_contains=args.notes_contains,
                    query=args.query,
                    tracking_method=args.tracking_method,
                    area_id=args.area_id,
                    area_name=args.area_name,
                    without_area=args.without_area,
                    task_id=args.task_id,
                    without_task=args.without_task,
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
            )
            timelogs = await timelog_services.list_timelogs(
                session,
                query=list_input,
            )
            total_count = (
                await timelog_services.count_timelogs(
                    session,
                    filters=list_input.filters,
                )
                if args.count
                else None
            )
        except timelog_services.TimelogValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if args.json:
        print_json_items(timelogs, total_count=total_count)
        return 0
    trailer_lines = () if total_count is None else (f"Total timelogs: {total_count}",)
    print_summary_rows(
        items=timelogs,
        columns=(
            TIMELOG_SUMMARY_COLUMNS_WITH_COUNTS if args.with_counts else TIMELOG_SUMMARY_COLUMNS
        ),
        row_formatter=lambda timelog: _format_timelog_summary(
            timelog, include_counts=args.with_counts
        ),
        empty_message="No timelogs found.",
        trailer_lines=trailer_lines,
    )
    return 0


async def handle_timelog_show_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        timelog = await timelog_services.get_timelog(
            session,
            timelog_id=args.timelog_id,
        )
    if timelog is None:
        return cli_handler_utils.print_missing_record_error("Timelog", args.timelog_id)
    if args.json:
        print_json_payload(timelog)
        return 0
    print(_format_timelog_detail(timelog))
    return 0


async def handle_timelog_update_async(args: argparse.Namespace) -> int:
    conflicts = (
        (args.clear_location and args.location is not None, "--location", "--clear-location"),
        (
            args.clear_energy_level and args.energy_level is not None,
            "--energy-level",
            "--clear-energy-level",
        ),
        (args.clear_notes and args.notes is not None, "--notes", "--clear-notes"),
        (args.clear_area and args.area_id is not None, "--area-id", "--clear-area"),
        (args.clear_task and args.task_id is not None, "--task-id", "--clear-task"),
        (args.clear_tags and args.tag_ids is not None, "--tag-id", "--clear-tags"),
        (args.clear_person and args.person_ids is not None, "--person-id", "--clear-person"),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicts)
    if conflict_error is not None:
        return conflict_error
    async with db_session.session_scope() as session:
        try:
            timelog = await timelog_services.update_timelog(
                session,
                timelog_id=args.timelog_id,
                changes=timelog_services.TimelogUpdateInput(
                    title=args.title,
                    start_time=args.start_time,
                    end_time=args.end_time,
                    tracking_method=args.tracking_method,
                    location=args.location,
                    clear_location=args.clear_location,
                    energy_level=args.energy_level,
                    clear_energy_level=args.clear_energy_level,
                    notes=args.notes,
                    clear_notes=args.clear_notes,
                    area_id=args.area_id,
                    clear_area=args.clear_area,
                    task_id=args.task_id,
                    clear_task=args.clear_task,
                    tag_ids=args.tag_ids,
                    clear_tags=args.clear_tags,
                    person_ids=args.person_ids,
                    clear_person=args.clear_person,
                ),
            )
        except (
            timelog_services.TimelogNotFoundError,
            timelog_services.TimelogAreaReferenceNotFoundError,
            timelog_services.TimelogTaskReferenceNotFoundError,
            timelog_services.TimelogValidationError,
            LookupError,
        ) as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated timelog {timelog.id}")
    return 0


async def handle_timelog_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        try:
            await timelog_services.delete_timelog(session, timelog_id=args.timelog_id)
        except timelog_services.TimelogNotFoundError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Soft-deleted timelog {args.timelog_id}")
    return 0


async def handle_timelog_batch_update_async(args: argparse.Namespace) -> int:
    conflicts = (
        (
            args.title is not None
            and (args.find_title_text is not None or args.replace_title_text is not None),
            "--title",
            "--find-title-text/--replace-title-text",
        ),
        (args.clear_area and args.area_id is not None, "--area-id", "--clear-area"),
        (args.clear_task and args.task_id is not None, "--task-id", "--clear-task"),
        (args.clear_tags and args.tag_ids is not None, "--tag-id", "--clear-tags"),
        (args.clear_person and args.person_ids is not None, "--person-id", "--clear-person"),
    )
    conflict_error = cli_handler_utils.validate_mutually_exclusive_pairs(conflicts)
    if conflict_error is not None:
        return conflict_error
    if args.replace_title_text is not None and args.find_title_text is None:
        print("Use --replace-title-text only with --find-title-text.", file=sys.stderr)
        return 1
    if not any(
        (
            args.title is not None,
            args.find_title_text is not None,
            args.area_id is not None,
            args.clear_area,
            args.task_id is not None,
            args.clear_task,
            args.tag_ids is not None,
            args.clear_tags,
            args.person_ids is not None,
            args.clear_person,
        )
    ):
        print("At least one batch update option is required.", file=sys.stderr)
        return 1

    async with db_session.session_scope() as session:
        try:
            result = await timelog_services.batch_update_timelogs(
                session,
                timelog_ids=list(args.timelog_ids),
                changes=timelog_services.TimelogBatchUpdateInput(
                    title=args.title,
                    find_title_text=args.find_title_text,
                    replace_title_text=args.replace_title_text or "",
                    changes=timelog_services.TimelogUpdateInput(
                        area_id=args.area_id,
                        clear_area=args.clear_area,
                        task_id=args.task_id,
                        clear_task=args.clear_task,
                        tag_ids=args.tag_ids,
                        clear_tags=args.clear_tags,
                        person_ids=args.person_ids,
                        clear_person=args.clear_person,
                    ),
                ),
            )
        except timelog_services.TimelogValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(f"Updated timelogs: {result.updated_count}")
    if result.unchanged_ids:
        print(format_id_lines("Unchanged timelog IDs", result.unchanged_ids))
    if result.failed_ids:
        print(format_id_lines("Failed timelog IDs", result.failed_ids), file=sys.stderr)
    for error in result.errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if result.failed_ids else 0


async def handle_timelog_batch_delete_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        result = await timelog_services.batch_delete_timelogs(
            session,
            timelog_ids=list(args.timelog_ids),
        )
    return print_batch_result(
        success_label="Deleted timelogs",
        success_count=result.deleted_count,
        failed_label="Failed timelog IDs",
        result=result,
    )


async def handle_timelog_stats_day_async(args: argparse.Namespace) -> int:
    async with db_session.session_scope() as session:
        report = await timelog_stats.get_timelog_stats_groupby_area_for_day(
            session,
            target_date=args.target_date,
        )
    print(_format_timelog_stats_report(report))
    return 0


async def handle_timelog_stats_range_async(args: argparse.Namespace) -> int:
    try:
        start_date, end_date = resolve_required_date_interval_arguments(
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        report = await timelog_stats.get_timelog_stats_groupby_area_for_range(
            session,
            start_date=start_date,
            end_date=end_date,
        )
    print(_format_timelog_stats_report(report))
    return 0


async def handle_timelog_stats_period_async(
    args: argparse.Namespace,
    *,
    granularity: str,
) -> int:
    target_date = args.target_date if granularity == "week" else None
    month = args.month if granularity == "month" else None
    year = args.year if granularity == "year" else None
    async with db_session.session_scope() as session:
        try:
            report = await timelog_stats.get_timelog_stats_groupby_area_for_period(
                session,
                granularity=granularity,
                target_date=target_date,
                month=month,
                year=year,
            )
        except timelog_stats.TimelogStatsValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    print(_format_timelog_stats_report(report))
    return 0


async def handle_timelog_stats_rebuild_async(args: argparse.Namespace) -> int:
    try:
        date_selection = resolve_date_selection_arguments(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    has_date_selection = bool(date_selection.date_values) or (
        date_selection.start_date is not None or date_selection.end_date is not None
    )
    if args.rebuild_all and has_date_selection:
        print("Use --all by itself, without date filters.", file=sys.stderr)
        return 1
    async with db_session.session_scope() as session:
        try:
            rebuilt_dates = await timelog_stats.rebuild_timelog_stats_groupby_area(
                session,
                date_values=date_selection.date_values,
                start_date=date_selection.start_date,
                end_date=date_selection.end_date,
                rebuild_all=args.rebuild_all,
            )
        except timelog_stats.TimelogStatsValidationError as exc:
            return cli_handler_utils.print_cli_error(exc)
    if not rebuilt_dates:
        print("No linked-area timelogs found for the selected rebuild scope.")
        return 0
    print(f"Rebuilt timelog stats grouped by area for {len(rebuilt_dates)} dates.")
    if date_selection.date_values:
        label = "date" if len(date_selection.date_values) == 1 else "dates"
        selected_dates = ", ".join(
            target_date.isoformat() for target_date in date_selection.date_values
        )
        print(f"{label}: {selected_dates}")
    else:
        rebuilt_start_date = min(rebuilt_dates)
        rebuilt_end_date = max(rebuilt_dates)
        print(f"start_date: {rebuilt_start_date.isoformat()}")
        print(f"end_date: {rebuilt_end_date.isoformat()}")
    return 0
