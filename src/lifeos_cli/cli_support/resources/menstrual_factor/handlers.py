"""Menstrual factor command handlers."""

from __future__ import annotations

import argparse
import sys

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items
from lifeos_cli.cli_support.output_utils import print_summary_rows
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models.menstrual import MenstrualFactor
from lifeos_cli.db.services import menstrual as menstrual_services

FACTOR_SUMMARY_COLUMNS = ("factor_id", "name")


def _factor_payload(factor: MenstrualFactor) -> dict[str, object]:
    return {
        "id": str(factor.id),
        "name": factor.name,
    }


def _format_factor_summary(factor: MenstrualFactor) -> str:
    return f"{factor.id}\t{factor.name}"


async def handle_menstrual_factor_add_async(args: argparse.Namespace) -> int:
    """Create one custom menstrual factor."""
    try:
        async with db_session.session_scope() as session:
            factor = await menstrual_services.create_menstrual_factor(
                session,
                name=args.name,
            )
    except menstrual_services.MenstrualValidationError as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Created menstrual factor {factor.id}")
    return 0


async def handle_menstrual_factor_list_async(args: argparse.Namespace) -> int:
    """List custom menstrual factors."""
    async with db_session.session_scope() as session:
        factors = await menstrual_services.list_menstrual_factors(
            session,
            limit=args.limit,
            offset=args.offset,
        )
    if args.json:
        print_json_items([_factor_payload(factor) for factor in factors])
        return 0
    print_summary_rows(
        items=factors,
        columns=FACTOR_SUMMARY_COLUMNS,
        row_formatter=_format_factor_summary,
        empty_message="No menstrual factors found.",
    )
    return 0


async def handle_menstrual_factor_delete_async(args: argparse.Namespace) -> int:
    """Soft-delete one or more custom menstrual factors."""
    failed_ids: list[object] = []
    errors: list[str] = []
    for factor_id in args.factor_ids:
        try:
            async with db_session.session_scope() as session:
                await menstrual_services.delete_menstrual_factor(
                    session,
                    factor_id=factor_id,
                )
        except menstrual_services.MenstrualFactorNotFoundError as exc:
            failed_ids.append(factor_id)
            errors.append(str(exc))
    for factor_id in args.factor_ids:
        if factor_id not in failed_ids:
            print(f"Soft-deleted menstrual factor {factor_id}")
    for error in errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if failed_ids else 0
