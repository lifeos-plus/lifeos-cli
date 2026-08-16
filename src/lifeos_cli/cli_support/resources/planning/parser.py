"""Planning resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.parser_common import add_limit_offset_arguments
from lifeos_cli.cli_support.resources.planning.handlers import handle_planning_show_async
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_date_value
from lifeos_cli.db.services.task_support import VALID_PLANNING_CYCLE_TYPES
from lifeos_cli.i18n import cli_message as _


def build_planning_show_parser(
    planning_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the planning show command."""
    show_parser = add_documented_parser(
        planning_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.planning.show.show_planning_view"),
            description=_("resources.planning.show.description"),
            examples=(
                "lifeos planning show --cycle-type 7years",
                "lifeos planning show --cycle-type 7years --at 2026-08-11",
                "lifeos planning show --cycle-type year --start 2026-07-26",
            ),
            notes=(
                _("resources.planning.show.window_semantics_note"),
                _("resources.planning.show.tree_columns_note"),
                _("resources.planning.show.context_note"),
                _("resources.planning.show.filters_note"),
            ),
        ),
    )
    show_parser.add_argument(
        "--cycle-type",
        required=True,
        choices=VALID_PLANNING_CYCLE_TYPES,
        help=_("resources.planning.show.cycle_type_help"),
    )
    show_parser.add_argument(
        "--at",
        type=parse_date_value,
        default=None,
        help=_("resources.planning.show.at_help"),
    )
    show_parser.add_argument(
        "--start",
        type=parse_date_value,
        default=None,
        help=_("resources.planning.show.start_help"),
    )
    show_parser.add_argument(
        "--depth",
        type=int,
        default=None,
        help=_("resources.planning.show.depth_help"),
    )
    show_parser.add_argument(
        "--status",
        help=_("resources.planning.show.status_help"),
    )
    show_parser.add_argument(
        "--vision",
        help=_("resources.planning.show.vision_help"),
    )
    add_limit_offset_arguments(show_parser)
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_planning_show_async))


def build_planning_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the planning command tree."""
    planning_parser = add_documented_help_parser(
        subparsers,
        "planning",
        help_content=HelpContent(
            summary=_("resources.planning.parser.manage_planning_views"),
            description=(
                _("resources.planning.parser.description")
                + "\n\n"
                + _("resources.planning.parser.primary_reference_note")
            ),
            examples=("lifeos planning show --help",),
        ),
    )
    planning_subparsers = planning_parser.add_subparsers(
        dest="planning_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    build_planning_show_parser(planning_subparsers)
