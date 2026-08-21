"""Builder helpers for menstrual cycle actions."""

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
from lifeos_cli.cli_support.resources.menstrual.handlers import (
    handle_menstrual_add_async,
    handle_menstrual_delete_async,
    handle_menstrual_list_async,
    handle_menstrual_show_async,
    handle_menstrual_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_date_value
from lifeos_cli.i18n import cli_message as _


def _add_shared_menstrual_field_arguments(parser: argparse.ArgumentParser) -> None:
    period_group = parser.add_mutually_exclusive_group()
    period_group.add_argument(
        "--in-period",
        dest="in_period",
        action="store_true",
        help=_("resources.menstrual.parser_actions.mark_day_as_in_period"),
    )
    period_group.add_argument(
        "--not-in-period",
        dest="in_period",
        action="store_false",
        help=_("resources.menstrual.parser_actions.mark_day_as_not_in_period"),
    )
    parser.add_argument(
        "--flow",
        choices=("low", "medium", "high"),
        help=_("resources.menstrual.parser_actions.optional_flow_amount_low_medium_or_high"),
    )
    parser.add_argument(
        "--symptom",
        dest="symptoms",
        action="append",
        default=None,
        help=_("resources.menstrual.parser_actions.repeat_to_add_one_daily_symptom"),
    )
    parser.add_argument(
        "--factor",
        dest="factor_names",
        action="append",
        default=None,
        metavar="factor-name",
        help=_("resources.menstrual.parser_actions.repeat_to_attach_one_custom_factor_by_name"),
    )
    parser.add_argument(
        "--mood-changes",
        choices=("yes", "no"),
        help=_("resources.menstrual.parser_actions.mood_changes_yes_or_no"),
    )
    parser.add_argument(
        "--protection-used",
        choices=("yes", "no"),
        help=_("resources.menstrual.parser_actions.protection_used_yes_or_no"),
    )
    parser.add_argument(
        "--spotting",
        choices=("yes", "no"),
        help=_("resources.menstrual.parser_actions.spotting_yes_or_no"),
    )
    parser.add_argument(
        "--notes",
        help=_("resources.menstrual.parser_actions.optional_notes"),
    )


def build_menstrual_add_parser(
    menstrual_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual add command."""
    add_parser = add_documented_parser(
        menstrual_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.menstrual.parser_actions.add_menstrual_day"),
            description=_(
                "resources.menstrual.parser_actions.create_one_daily_menstrual_cycle_record"
            ),
            examples=(
                "lifeos menstrual add --date 2026-08-19 --in-period --flow medium",
                "lifeos menstrual add --date 2026-08-20 --symptom headache --factor travel",
            ),
            notes=(
                _("resources.menstrual.parser_actions.flow_amount_requires_in_period"),
                _(
                    "resources.menstrual.parser_actions.known_symptom_codes_are_hot_flash_headache_bladder_incontinence_and_constipation"
                ),
                _("resources.menstrual.parser_actions.missing_factors_are_created_automatically"),
            ),
        ),
    )
    add_parser.add_argument(
        "--date",
        type=parse_date_value,
        required=True,
        help=_("resources.menstrual.parser_actions.log_date"),
    )
    _add_shared_menstrual_field_arguments(add_parser)
    add_parser.set_defaults(handler=make_sync_handler(handle_menstrual_add_async))


def build_menstrual_list_parser(
    menstrual_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual list command."""
    list_parser = add_documented_parser(
        menstrual_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.menstrual.parser_actions.list_menstrual_days"),
            description=_(
                "resources.menstrual.parser_actions.list_menstrual_days_with_optional_date_range"
            ),
            examples=(
                "lifeos menstrual list",
                "lifeos menstrual list --start-date 2026-08-01 --end-date 2026-08-31",
                "lifeos menstrual list --json",
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
    list_parser.set_defaults(handler=make_sync_handler(handle_menstrual_list_async))


def build_menstrual_show_parser(
    menstrual_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual show command."""
    show_parser = add_documented_parser(
        menstrual_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.menstrual.parser_actions.show_menstrual_day"),
            description=_(
                "resources.menstrual.parser_actions.show_one_menstrual_day_with_full_metadata"
            ),
            examples=("lifeos menstrual show <menstrual-day-id>",),
        ),
    )
    show_parser.add_argument(
        "day_id",
        type=UUID,
        help=_("resources.menstrual.parser_actions.menstrual_day_identifier"),
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_menstrual_show_async))


def build_menstrual_update_parser(
    menstrual_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual update command."""
    update_parser = add_documented_parser(
        menstrual_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.menstrual.parser_actions.update_menstrual_day"),
            description=_("resources.menstrual.parser_actions.update_mutable_menstrual_day_fields"),
            examples=("lifeos menstrual update <id> --flow low",),
            notes=(
                _(
                    "common.messages.only_explicitly_provided_flags_are_changed_omitted_values_are_preserved"
                ),
                help_message("notes.clearFlags.explicitOptionalValues"),
            ),
        ),
    )
    update_parser.add_argument(
        "day_id",
        type=UUID,
        help=_("resources.menstrual.parser_actions.menstrual_day_identifier"),
    )
    update_parser.add_argument(
        "--date",
        type=parse_date_value,
        help=_("resources.menstrual.parser_actions.log_date"),
    )
    _add_shared_menstrual_field_arguments(update_parser)
    update_parser.add_argument(
        "--clear-flow",
        action="store_true",
        help=_("resources.menstrual.parser_actions.clear_flow_amount"),
    )
    update_parser.add_argument(
        "--clear-symptoms",
        action="store_true",
        help=_("resources.menstrual.parser_actions.clear_symptoms"),
    )
    update_parser.add_argument(
        "--clear-notes",
        action="store_true",
        help=_("resources.menstrual.parser_actions.clear_notes"),
    )
    update_parser.add_argument(
        "--clear-factors",
        action="store_true",
        help=_("resources.menstrual.parser_actions.clear_factors"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_menstrual_update_async))


def build_menstrual_delete_parser(
    menstrual_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the menstrual delete command."""
    delete_parser = add_documented_parser(
        menstrual_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.menstrual.parser_actions.delete_menstrual_days"),
            description=_(
                "resources.menstrual.parser_actions.soft_delete_one_or_more_menstrual_day_records"
            ),
            examples=(
                "lifeos menstrual delete <menstrual-day-id>",
                "lifeos menstrual delete <id-1> <id-2>",
            ),
            notes=(_("common.messages.delete_accepts_one_or_more_identifiers"),),
        ),
    )
    delete_parser.add_argument(
        "day_ids",
        type=UUID,
        nargs="+",
        metavar="menstrual-day-id",
        help=_("common.parser.noun_identifiers_to_delete").format(noun="Menstrual day"),
    )
    delete_parser.set_defaults(handler=make_sync_handler(handle_menstrual_delete_async))
