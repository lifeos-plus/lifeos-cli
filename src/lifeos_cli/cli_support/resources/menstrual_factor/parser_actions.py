"""Builder helpers for menstrual factor actions."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.parser_common import add_limit_offset_arguments
from lifeos_cli.cli_support.resources.menstrual_factor.handlers import (
    handle_menstrual_factor_add_async,
    handle_menstrual_factor_delete_async,
    handle_menstrual_factor_list_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_menstrual_factor_add_parser(
    factor_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual-factor add command."""
    add_parser = add_documented_parser(
        factor_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.menstrual_factor.parser_actions.add_menstrual_factor"),
            description=_(
                "resources.menstrual_factor.parser_actions.create_one_custom_menstrual_factor"
            ),
            examples=("lifeos menstrual-factor add --name travel",),
        ),
    )
    add_parser.add_argument(
        "--name",
        required=True,
        help=_("resources.menstrual_factor.parser_actions.factor_name"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_menstrual_factor_add_async))


def build_menstrual_factor_list_parser(
    factor_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual-factor list command."""
    list_parser = add_documented_parser(
        factor_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.menstrual_factor.parser_actions.list_menstrual_factors"),
            description=_(
                "resources.menstrual_factor.parser_actions.list_custom_menstrual_factors"
            ),
            examples=("lifeos menstrual-factor list", "lifeos menstrual-factor list --json"),
        ),
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_menstrual_factor_list_async))


def build_menstrual_factor_delete_parser(
    factor_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual-factor delete command."""
    delete_parser = add_documented_parser(
        factor_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.menstrual_factor.parser_actions.delete_menstrual_factors"),
            description=_(
                "resources.menstrual_factor.parser_actions.soft_delete_one_or_more_custom_factors"
            ),
            examples=(
                "lifeos menstrual-factor delete <factor-id>",
                "lifeos menstrual-factor delete <id-1> <id-2>",
            ),
            notes=(_("common.messages.delete_accepts_one_or_more_identifiers"),),
        ),
    )
    delete_parser.add_argument(
        "factor_ids",
        type=UUID,
        nargs="+",
        metavar="factor-id",
        help=_("common.parser.noun_identifiers_to_delete").format(noun="Menstrual factor"),
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_menstrual_factor_delete_async))
