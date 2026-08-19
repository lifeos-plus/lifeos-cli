"""Builder helpers for body measurement actions."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
    help_message,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.parser_common import (
    add_date_range_arguments,
    add_limit_offset_arguments,
    add_start_end_date_arguments,
)
from lifeos_cli.cli_support.resources.body_measurement.handlers import (
    handle_body_measurement_add_async,
    handle_body_measurement_delete_async,
    handle_body_measurement_list_async,
    handle_body_measurement_show_async,
    handle_body_measurement_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_user_datetime_value
from lifeos_cli.i18n import cli_message as _


def _add_shared_body_metric_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--body-fat",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_body_fat_percentage"),
    )
    parser.add_argument(
        "--visceral-fat",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_visceral_fat"),
    )
    parser.add_argument(
        "--fat-mass",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_fat_mass_kg"),
    )
    parser.add_argument(
        "--muscle-percentage",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_muscle_percentage"),
    )
    parser.add_argument(
        "--muscle-mass",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_muscle_mass_kg"),
    )
    parser.add_argument(
        "--body-water",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_body_water_kg"),
    )
    parser.add_argument(
        "--protein",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_protein_kg"),
    )
    parser.add_argument(
        "--bone-mass",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_bone_mass_kg"),
    )
    parser.add_argument(
        "--skeletal-muscle",
        type=float,
        help=_("resources.body_measurement.parser_actions.optional_skeletal_muscle_kg"),
    )


def build_body_measurement_add_parser(
    body_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the body add command."""
    add_parser = add_documented_parser(
        body_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.body_measurement.parser_actions.add_body_measurement"),
            description=_(
                "resources.body_measurement.parser_actions.create_one_body_measurement_with_user_owned_measured_at"
            ),
            examples=(
                "lifeos body-measurement add --weight 63.5 --body-fat 22.1",
                (
                    "lifeos body-measurement add --weight 127 --unit jin "
                    "--measured-at 2026-08-19T08:00:00"
                ),
            ),
            notes=(
                _(
                    "resources.body_measurement.parser_actions.weights_are_stored_in_kg_regardless_of_input_unit"
                ),
                _(
                    "resources.body_measurement.parser_actions.default_unit_is_the_preferred_weight_unit"
                ),
                _("resources.body_measurement.parser_actions.measured_at_defaults_to_now"),
                help_message("notes.datetime.configuredTimezone"),
            ),
        ),
    )
    add_parser.add_argument(
        "--weight",
        type=float,
        required=True,
        help=_("resources.body_measurement.parser_actions.weight_value_in_input_unit"),
    )
    add_parser.add_argument(
        "--unit",
        choices=("kg", "jin", "lb"),
        help=_("resources.body_measurement.parser_actions.input_weight_unit_kg_jin_or_lb"),
    )
    add_parser.add_argument(
        "--measured-at",
        type=parse_user_datetime_value,
        help=_("resources.body_measurement.parser_actions.measured_at_defaults_to_now"),
    )
    _add_shared_body_metric_arguments(add_parser)
    add_parser.add_argument(
        "--notes",
        help=_("resources.body_measurement.parser_actions.optional_notes"),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_body_measurement_add_async))


def build_body_measurement_list_parser(
    body_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the body list command."""
    list_parser = add_documented_parser(
        body_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.body_measurement.parser_actions.list_body_measurements"),
            description=_(
                "resources.body_measurement.parser_actions.list_body_measurements_with_optional_date_range"
            ),
            examples=(
                "lifeos body-measurement list",
                "lifeos body-measurement list --start-date 2026-08-01 --end-date 2026-08-31 --json",
            ),
            notes=(help_message("notes.dateSelection.dateOrRange"),),
        ),
    )
    add_date_range_arguments(
        list_parser,
        date_help=_("common.messages.repeat_date_for_one_or_more_local_dates"),
    )
    add_start_end_date_arguments(
        list_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_body_measurement_list_async))


def build_body_measurement_show_parser(
    body_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the body show command."""
    show_parser = add_documented_parser(
        body_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.body_measurement.parser_actions.show_body_measurement"),
            description=_(
                "resources.body_measurement.parser_actions.show_one_body_measurement_with_derived_bmi"
            ),
            examples=("lifeos body-measurement show <body-measurement-id>",),
        ),
    )
    show_parser.add_argument(
        "measurement_id",
        type=UUID,
        help=_("resources.body_measurement.parser_actions.body_measurement_identifier"),
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_body_measurement_show_async))


def build_body_measurement_update_parser(
    body_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the body update command."""
    update_parser = add_documented_parser(
        body_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.body_measurement.parser_actions.update_body_measurement"),
            description=_(
                "resources.body_measurement.parser_actions.update_mutable_body_measurement_fields"
            ),
            examples=("lifeos body-measurement update <id> --weight 64.2",),
            notes=(
                _(
                    "common.messages.only_explicitly_provided_flags_are_changed_omitted_values_are_preserved"
                ),
                help_message("notes.clearFlags.explicitOptionalValues"),
            ),
        ),
    )
    update_parser.add_argument(
        "measurement_id",
        type=UUID,
        help=_("resources.body_measurement.parser_actions.body_measurement_identifier"),
    )
    update_parser.add_argument(
        "--weight",
        type=float,
        help=_("resources.body_measurement.parser_actions.weight_value_in_input_unit"),
    )
    update_parser.add_argument(
        "--unit",
        choices=("kg", "jin", "lb"),
        help=_("resources.body_measurement.parser_actions.input_weight_unit_kg_jin_or_lb"),
    )
    update_parser.add_argument(
        "--measured-at",
        type=parse_user_datetime_value,
        help=_("resources.body_measurement.parser_actions.measured_at_defaults_to_now"),
    )
    _add_shared_body_metric_arguments(update_parser)
    update_parser.add_argument(
        "--notes",
        help=_("resources.body_measurement.parser_actions.optional_notes"),
    )
    update_parser.add_argument(
        "--clear-body-fat",
        dest="clear_body_fat",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_body_fat"),
    )
    update_parser.add_argument(
        "--clear-visceral-fat",
        dest="clear_visceral_fat",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_visceral_fat"),
    )
    update_parser.add_argument(
        "--clear-fat-mass",
        dest="clear_fat_mass",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_fat_mass"),
    )
    update_parser.add_argument(
        "--clear-muscle-percentage",
        dest="clear_muscle_percentage",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_muscle_percentage"),
    )
    update_parser.add_argument(
        "--clear-muscle-mass",
        dest="clear_muscle_mass",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_muscle_mass"),
    )
    update_parser.add_argument(
        "--clear-body-water",
        dest="clear_body_water",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_body_water"),
    )
    update_parser.add_argument(
        "--clear-protein",
        dest="clear_protein",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_protein"),
    )
    update_parser.add_argument(
        "--clear-bone-mass",
        dest="clear_bone_mass",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_bone_mass"),
    )
    update_parser.add_argument(
        "--clear-skeletal-muscle",
        dest="clear_skeletal_muscle",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_skeletal_muscle"),
    )
    update_parser.add_argument(
        "--clear-notes",
        dest="clear_notes",
        action="store_true",
        help=_("resources.body_measurement.parser_actions.clear_notes"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_body_measurement_update_async))


def build_body_measurement_delete_parser(
    body_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the body delete command."""
    delete_parser = add_documented_parser(
        body_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.body_measurement.parser_actions.delete_body_measurements"),
            description=_(
                "resources.body_measurement.parser_actions.soft_delete_one_or_more_body_measurements"
            ),
            examples=(
                "lifeos body-measurement delete <body-measurement-id>",
                "lifeos body-measurement delete <id-1> <id-2>",
            ),
            notes=(_("common.messages.delete_accepts_one_or_more_identifiers"),),
        ),
    )
    delete_parser.add_argument(
        "measurement_ids",
        type=UUID,
        nargs="+",
        metavar="body-measurement-id",
        help=_("common.parser.noun_identifiers_to_delete").format(noun="Body measurement"),
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_body_measurement_delete_async))
