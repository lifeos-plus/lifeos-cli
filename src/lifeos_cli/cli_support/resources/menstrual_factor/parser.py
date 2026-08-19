"""Menstrual factor resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.menstrual_factor.parser_actions import (
    build_menstrual_factor_add_parser,
    build_menstrual_factor_delete_parser,
    build_menstrual_factor_list_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_menstrual_factor_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual-factor command tree."""
    factor_parser = add_documented_help_parser(
        subparsers,
        "menstrual-factor",
        help_content=HelpContent(
            summary=_("resources.menstrual_factor.parser.manage_custom_menstrual_factors"),
            description=(
                _("resources.menstrual_factor.parser.create_list_and_delete_user_defined_factors")
                + "\n\n"
                + _(
                    "resources.menstrual_factor.parser.factors_are_lightweight_dictionary_entries_attached_to_menstrual_days"
                )
            ),
            examples=(
                "lifeos menstrual-factor add --help",
                "lifeos menstrual-factor list --help",
            ),
            notes=(
                _(
                    "resources.menstrual_factor.parser.use_menstrual_add_factor_flag_to_attach_factors_to_daily_records"
                ),
            ),
        ),
    )
    factor_subparsers = factor_parser.add_subparsers(
        dest="menstrual_factor_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_menstrual_factor_add_parser(factor_subparsers)
    build_menstrual_factor_list_parser(factor_subparsers)
    build_menstrual_factor_delete_parser(factor_subparsers)
