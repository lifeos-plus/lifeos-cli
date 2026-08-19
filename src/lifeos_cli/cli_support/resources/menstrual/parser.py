"""Menstrual cycle resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.menstrual.parser_actions import (
    build_menstrual_add_parser,
    build_menstrual_delete_parser,
    build_menstrual_list_parser,
    build_menstrual_show_parser,
    build_menstrual_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_menstrual_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual command tree."""
    menstrual_parser = add_documented_help_parser(
        subparsers,
        "menstrual",
        help_content=HelpContent(
            summary=_("resources.menstrual.parser.manage_menstrual_cycle_records"),
            description=(
                _(
                    "resources.menstrual.parser.create_inspect_update_and_delete_daily_menstrual_cycle_records"
                )
                + "\n\n"
                + _(
                    "resources.menstrual.parser.one_record_per_local_date_with_period_symptoms_factors_and_notes"
                )
            ),
            examples=(
                "lifeos menstrual add --help",
                "lifeos menstrual list --help",
                "lifeos menstrual-factor add --help",
            ),
            notes=(
                _(
                    "resources.menstrual.parser.use_list_as_primary_query_entrypoint_for_menstrual_days"
                ),
                _(
                    "resources.menstrual.parser.use_menstrual_factor_resource_to_manage_custom_factors"
                ),
            ),
        ),
    )
    menstrual_subparsers = menstrual_parser.add_subparsers(
        dest="menstrual_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_menstrual_add_parser(menstrual_subparsers)
    build_menstrual_list_parser(menstrual_subparsers)
    build_menstrual_show_parser(menstrual_subparsers)
    build_menstrual_update_parser(menstrual_subparsers)
    build_menstrual_delete_parser(menstrual_subparsers)
