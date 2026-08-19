"""Menstrual cycle command handlers."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import DateArgumentError, resolve_date_selection_arguments
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.menstrual import MenstrualDay
from lifeos_cli.db.services import menstrual as menstrual_services

MENSTRUAL_SUMMARY_COLUMNS = (
    "day_id",
    "log_date",
    "in_period",
    "flow_amount",
    "symptoms",
    "factors",
    "notes",
)


def _menstrual_day_payload(day: MenstrualDay) -> dict[str, Any]:
    return {
        "id": str(day.id),
        "log_date": day.log_date.isoformat(),
        "in_period": day.in_period,
        "flow_amount": day.flow_amount,
        "symptoms": day.symptoms or [],
        "factors": [factor.name for factor in day.factors],
        "mood_changes": day.mood_changes,
        "protection_used": day.protection_used,
        "spotting": day.spotting,
        "notes": day.notes,
        "created_at": format_timestamp(day.created_at),
        "updated_at": format_timestamp(day.updated_at),
    }


def _format_menstrual_day_summary(day: MenstrualDay) -> str:
    symptoms = ",".join(day.symptoms or []) or "-"
    factors = ",".join(factor.name for factor in day.factors) or "-"
    return (
        f"{day.id}\t{day.log_date.isoformat()}\t{'yes' if day.in_period else 'no'}\t"
        f"{day.flow_amount or '-'}\t{symptoms}\t{factors}\t{day.notes or '-'}"
    )


def _resolve_tristate(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "yes"


async def handle_menstrual_add_async(args: argparse.Namespace) -> int:
    """Create one daily menstrual cycle record."""
    try:
        async with db_session.session_scope() as session:
            day = await menstrual_services.create_menstrual_day(
                session,
                log_date=args.date,
                in_period=args.in_period,
                flow_amount=args.flow,
                symptoms=args.symptoms,
                mood_changes=_resolve_tristate(args.mood_changes),
                protection_used=_resolve_tristate(args.protection_used),
                spotting=_resolve_tristate(args.spotting),
                factor_names=args.factor_names,
                notes=args.notes,
            )
    except (
        menstrual_services.MenstrualDayNotFoundError,
        menstrual_services.MenstrualFactorNotFoundError,
        menstrual_services.MenstrualValidationError,
    ) as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Created menstrual day {day.id}")
    return 0


async def handle_menstrual_list_async(args: argparse.Namespace) -> int:
    """List menstrual day records."""
    try:
        resolved = resolve_date_selection_arguments(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        days = await menstrual_services.list_menstrual_days(
            session,
            dates=resolved.date_values or None,
            start_date=resolved.start_date,
            end_date=resolved.end_date,
            limit=args.limit,
            offset=args.offset,
        )
    if args.json:
        print_json_items([_menstrual_day_payload(day) for day in days])
        return 0
    print_summary_rows(
        items=days,
        columns=MENSTRUAL_SUMMARY_COLUMNS,
        row_formatter=_format_menstrual_day_summary,
        empty_message="No menstrual day records found.",
    )
    return 0


async def handle_menstrual_show_async(args: argparse.Namespace) -> int:
    """Show one menstrual day record with full metadata."""
    async with db_session.session_scope() as session:
        day = await menstrual_services.get_menstrual_day(session, day_id=args.day_id)
        if day is None:
            return cli_handler_utils.print_missing_record_error(
                "Menstrual day",
                args.day_id,
            )
    if args.json:
        print_json_payload(_menstrual_day_payload(day))
        return 0
    print(f"menstrual_day_id: {day.id}")
    print(f"log_date: {day.log_date.isoformat()}")
    print(f"in_period: {'yes' if day.in_period else 'no'}")
    print(f"flow_amount: {day.flow_amount or '-'}")
    print(f"symptoms: {','.join(day.symptoms or []) or '-'}")
    print(f"factors: {','.join(factor.name for factor in day.factors) or '-'}")
    print(f"mood_changes: {day.mood_changes if day.mood_changes is not None else '-'}")
    print(f"protection_used: {day.protection_used if day.protection_used is not None else '-'}")
    print(f"spotting: {day.spotting if day.spotting is not None else '-'}")
    print(f"notes: {day.notes or '-'}")
    print(f"created_at: {format_timestamp(day.created_at)}")
    print(f"updated_at: {format_timestamp(day.updated_at)}")
    return 0


async def handle_menstrual_update_async(args: argparse.Namespace) -> int:
    """Update one menstrual day record."""
    try:
        async with db_session.session_scope() as session:
            day = await menstrual_services.update_menstrual_day(
                session,
                day_id=args.day_id,
                log_date=args.date,
                in_period=args.in_period,
                flow_amount=args.flow,
                symptoms=args.symptoms,
                mood_changes=_resolve_tristate(args.mood_changes),
                protection_used=_resolve_tristate(args.protection_used),
                spotting=_resolve_tristate(args.spotting),
                factor_names=args.factor_names,
                notes=args.notes,
                clear_flow=args.clear_flow,
                clear_symptoms=args.clear_symptoms,
                clear_notes=args.clear_notes,
                clear_factors=args.clear_factors,
            )
    except (
        menstrual_services.MenstrualDayNotFoundError,
        menstrual_services.MenstrualFactorNotFoundError,
        menstrual_services.MenstrualValidationError,
    ) as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Updated menstrual day {day.id}")
    return 0


async def handle_menstrual_delete_async(args: argparse.Namespace) -> int:
    """Soft-delete one or more menstrual day records."""
    failed_ids: list[object] = []
    errors: list[str] = []
    for day_id in args.day_ids:
        try:
            async with db_session.session_scope() as session:
                await menstrual_services.delete_menstrual_day(session, day_id=day_id)
        except menstrual_services.MenstrualDayNotFoundError as exc:
            failed_ids.append(day_id)
            errors.append(str(exc))
    for day_id in args.day_ids:
        if day_id not in failed_ids:
            print(f"Soft-deleted menstrual day {day_id}")
    for error in errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if failed_ids else 0
