"""Reusable argument builders for resource parsers."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.time_args import parse_date_value
from lifeos_cli.i18n import cli_message as _


def add_limit_offset_arguments(
    parser: argparse.ArgumentParser,
    *,
    row_noun: str = "rows",
) -> None:
    """Add standard pagination flags."""
    del row_noun
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help=_("common.parser.maximum_number_of_results_to_return"),
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
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


def add_batch_delete_action(
    batch_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    ids_dest: str,
    noun: str,
    delete_handler: Callable[[argparse.Namespace], int],
    delete_summary: str,
    delete_description: str,
    delete_examples: tuple[str, ...] = (),
    delete_notes: tuple[str, ...] = (),
    ids_help: str | None = None,
) -> None:
    """Register the standard ``batch delete`` action inside a batch namespace."""
    batch_delete_parser = add_documented_parser(
        batch_subparsers,
        "delete",
        help_content=HelpContent(
            summary=delete_summary,
            description=delete_description,
            examples=delete_examples,
            notes=delete_notes,
        ),
    )
    if ids_help is None:
        add_identifier_list_argument(batch_delete_parser, dest=ids_dest, noun=noun)
    else:
        batch_delete_parser.add_argument(
            "--ids",
            dest=ids_dest,
            metavar=f"{noun}-id",
            nargs="+",
            required=True,
            type=UUID,
            help=ids_help,
        )
    batch_delete_parser.set_defaults(handler=delete_handler)


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


def add_batch_delete_namespace(
    resource_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    dest: str,
    ids_dest: str,
    noun: str,
    delete_handler: Callable[[argparse.Namespace], int],
    batch_summary: str,
    batch_description: str,
    batch_examples: tuple[str, ...],
    delete_summary: str,
    delete_description: str,
    delete_examples: tuple[str, ...] = (),
    batch_notes: tuple[str, ...] = (),
) -> None:
    """Build the standard ``batch delete`` namespace used by CRUD resources."""
    batch_subparsers = add_batch_namespace(
        resource_subparsers,
        dest=dest,
        batch_summary=batch_summary,
        batch_description=batch_description,
        batch_examples=batch_examples,
        batch_notes=batch_notes,
    )
    add_batch_delete_action(
        batch_subparsers,
        ids_dest=ids_dest,
        noun=noun,
        delete_handler=delete_handler,
        delete_summary=delete_summary,
        delete_description=delete_description,
        delete_examples=delete_examples,
    )
