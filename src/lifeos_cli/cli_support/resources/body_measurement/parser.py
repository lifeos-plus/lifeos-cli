"""Body measurement resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.body_measurement.parser_actions import (
    build_body_measurement_add_parser,
    build_body_measurement_delete_parser,
    build_body_measurement_list_parser,
    build_body_measurement_show_parser,
    build_body_measurement_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_body_measurement_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the body command tree."""
    body_parser = add_documented_help_parser(
        subparsers,
        "body-measurement",
        help_content=HelpContent(
            summary=_(
                "resources.body_measurement.parser.manage_body_weight_and_composition_measurements"
            ),
            description=(
                _(
                    "resources.body_measurement.parser.create_inspect_update_and_delete_body_measurements"
                )
                + "\n\n"
                + _(
                    "resources.body_measurement.parser.weights_are_stored_in_kg_and_displayed_in_the_preferred_unit"
                )
            ),
            examples=(
                "lifeos body-measurement add --help",
                "lifeos body-measurement list --help",
                "lifeos body-measurement show --help",
            ),
            notes=(
                _(
                    "resources.body_measurement.parser.use_body_fat_as_primary_composition_field_and_treat_other_values_as_optional"
                ),
                _(
                    "resources.body_measurement.parser.bmi_is_derived_from_weight_and_preferred_height"
                ),
                _(
                    "resources.body_measurement.parser.measured_at_is_user_owned_and_independent_of_record_created_at"
                ),
            ),
        ),
    )
    body_subparsers = body_parser.add_subparsers(
        dest="body_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_body_measurement_add_parser(body_subparsers)
    build_body_measurement_list_parser(body_subparsers)
    build_body_measurement_show_parser(body_subparsers)
    build_body_measurement_update_parser(body_subparsers)
    build_body_measurement_delete_parser(body_subparsers)
