"""Reusable argument builders for resource parsers."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.time_args import parse_date_value
from lifeos_cli.i18n import cli_message as _

DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 500
DEFAULT_LIST_OFFSET = 0


def _parse_list_limit(value: str) -> int:
    """Validate one list page size against the shared pagination contract."""
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise argparse.ArgumentTypeError(
            f"limit must be between 1 and {MAX_LIST_LIMIT} (default {DEFAULT_LIST_LIMIT})"
        )
    return limit


def _parse_list_offset(value: str) -> int:
    """Validate one list page offset against the shared pagination contract."""
    try:
        offset = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("offset must be an integer") from exc
    if offset < 0:
        raise argparse.ArgumentTypeError("offset must be zero or greater")
    return offset


def add_limit_offset_arguments(
    parser: argparse.ArgumentParser,
    *,
    row_noun: str = "rows",
) -> None:
    """Add standard pagination flags.

    Keep the page size bounded so oversized requests fail at argument parsing
    instead of reaching a backend whose statement parameter limit produces an
    opaque database error.
    """
    del row_noun
    parser.add_argument(
        "--limit",
        type=_parse_list_limit,
        default=DEFAULT_LIST_LIMIT,
        help=_("common.parser.maximum_number_of_results_to_return"),
    )
    parser.add_argument(
        "--offset",
        type=_parse_list_offset,
        default=DEFAULT_LIST_OFFSET,
        help=_("common.parser.number_of_results_to_skip"),
    )


def add_identifier_list_argument(
    parser: argparse.ArgumentParser,
    *,
    dest: str,
    noun: str,
    action_verb: str = "delete",
) -> None:
    """Add a standard repeated UUID identifier argument."""
    parser.add_argument(
        "--ids",
        dest=dest,
        metavar=f"{noun}-id",
        type=UUID,
        nargs="+",
        required=True,
        help=_("common.parser.noun_identifiers_to_action_verb").format(
            noun=noun.capitalize(),
            action_verb=action_verb,
        ),
    )


def add_date_range_arguments(
    parser: argparse.ArgumentParser,
    *,
    date_help: str,
) -> None:
    """Add a shared repeated-date argument for discrete local-date filters."""
    parser.add_argument(
        "--date",
        dest="date_values",
        action="append",
        default=None,
        type=parse_date_value,
        help=date_help,
    )


def add_start_end_date_arguments(
    parser: argparse.ArgumentParser,
    *,
    start_date_help: str,
    end_date_help: str,
) -> None:
    """Add shared explicit inclusive local-date range arguments."""
    parser.add_argument(
        "--start-date",
        dest="start_date",
        type=parse_date_value,
        help=start_date_help,
    )
    parser.add_argument(
        "--end-date",
        dest="end_date",
        type=parse_date_value,
        help=end_date_help,
    )


def add_batch_namespace(
    resource_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    dest: str,
    batch_summary: str,
    batch_description: str,
    batch_examples: tuple[str, ...],
    batch_notes: tuple[str, ...] = (),
) -> argparse._SubParsersAction[argparse.ArgumentParser]:
    """Create the standard ``batch`` command group and return its subparsers."""
    batch_parser = add_documented_help_parser(
        resource_subparsers,
        "batch",
        help_content=HelpContent(
            summary=batch_summary,
            description=batch_description,
            examples=batch_examples,
            notes=batch_notes,
        ),
    )
    return batch_parser.add_subparsers(
        dest=dest,
        title=_("common.messages.batch_actions"),
        metavar=_("common.messages.action"),
    )
