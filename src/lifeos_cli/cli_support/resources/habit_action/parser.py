"""Habit-action resource parser construction."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_date_range_arguments,
    add_limit_offset_arguments,
    add_start_end_date_arguments,
)
from lifeos_cli.cli_support.resources.habit_action.handlers import (
    HABIT_ACTION_SUMMARY_COLUMNS,
    handle_habit_action_list_async,
    handle_habit_action_log_async,
    handle_habit_action_show_async,
    handle_habit_action_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.cli_support.time_args import parse_date_value
from lifeos_cli.i18n import cli_message as _


def build_habit_action_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit-action command tree."""
    action_parser = add_documented_help_parser(
        subparsers,
        "habit-action",
        help_content=HelpContent(
            summary=_("resources.habit_action.parser.manage_dated_habit_actions"),
            description=(
                _(
                    "resources.habit_action.parser.inspect_and_update_dated_habit_action_occurrences_materialized_from_habits"
                )
                + "\n\n"
                + _(
                    "resources.habit_action.parser.habit_actions_are_materialized_on_demand_when_queried_or_logged"
                )
                + "\n\n"
                + _(
                    "resources.habit_action.parser.cadence_based_habits_still_log_dated_rows_but_progress_and_streaks_are"
                )
            ),
            examples=(
                "lifeos habit-action list --help",
                "lifeos habit-action show --help",
                "lifeos habit-action log --help",
            ),
            notes=(
                _("resources.habit_action.parser.use_list_for_both_per_habit_and_by_date_views"),
                _(
                    "resources.habit_action.parser.habit_cadence_decides_how_rows_are_grouped_into_completion_cycles"
                ),
                _(
                    "resources.habit_action.parser.use_log_to_materialize_and_update_occurrence_by_habit_and_date"
                ),
            ),
        ),
    )
    action_subparsers = action_parser.add_subparsers(
        dest="habit_action_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    list_parser = add_documented_parser(
        action_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.habit_action.parser.list_habit_actions"),
            description=(
                _(
                    "resources.habit_action.parser.list_habit_actions_for_one_habit_or_by_date_filters"
                )
                + "\n\n"
                + _(
                    "resources.habit_action.parser.use_this_command_to_inspect_daily_occurrence_views_and_materialized_records"
                )
            ),
            examples=(
                "lifeos habit-action list --habit-id 11111111-1111-1111-1111-111111111111",
                "lifeos habit-action list --date 2026-04-09",
                "lifeos habit-action list --date 2026-04-09 --date 2026-04-15",
                "lifeos habit-action list --start-date 2026-04-09 --end-date 2026-04-15",
                "lifeos habit-action list --date 2026-04-09 --count",
            ),
            notes=(
                _("resources.habit_action.parser.repeat_date_for_one_or_more_action_dates"),
                _("common.messages.use_start_date_end_date_for_inclusive_local_date_range"),
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(HABIT_ACTION_SUMMARY_COLUMNS)),
            ),
        ),
    )
    list_parser.add_argument(
        "--habit-id", type=UUID, help=_("resources.habit_action.parser.filter_by_habit_identifier")
    )
    list_parser.add_argument(
        "--status", help=_("resources.habit_action.parser.filter_by_habit_action_status")
    )
    add_date_range_arguments(
        list_parser,
        date_help=_("resources.habit_action.parser.repeat_for_one_or_more_action_dates"),
    )
    add_start_end_date_arguments(
        list_parser,
        start_date_help=_("common.messages.inclusive_local_date_range_start_date"),
        end_date_help=_("common.messages.inclusive_local_date_range_end_date"),
    )
    list_parser.add_argument(
        "--count", action="store_true", help=_("common.messages.print_total_matched_count")
    )
    add_limit_offset_arguments(list_parser, row_noun="habit actions")
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_habit_action_list_async))

    show_parser = add_documented_parser(
        action_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.habit_action.parser.show_habit_action"),
            description=_(
                "resources.habit_action.parser.show_one_habit_action_with_its_linked_habit_metadata"
            ),
            examples=(
                "lifeos habit-action show 11111111-1111-1111-1111-111111111111",
                "lifeos habit-action show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument(
        "action_id", type=UUID, help=_("resources.habit_action.parser.habit_action_identifier")
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_habit_action_show_async))

    update_parser = add_documented_parser(
        action_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.habit_action.parser.update_habit_action"),
            description=(
                _("resources.habit_action.parser.update_one_materialized_habit_action")
                + "\n\n"
                + _(
                    "resources.habit_action.parser.this_command_only_allows_status_and_notes_changes_within_editable_window"
                )
            ),
            examples=(
                "lifeos habit-action update 11111111-1111-1111-1111-111111111111 --status done",
                "lifeos habit-action update 11111111-1111-1111-1111-111111111111 "
                '--notes "Completed after lunch"',
                "lifeos habit-action update 11111111-1111-1111-1111-111111111111 --clear-notes",
            ),
            notes=(
                _(
                    "resources.habit_action.parser.use_log_when_you_know_habit_and_date_but_have_not_looked"
                ),
                _("resources.habit_action.parser.use_clear_notes_to_remove_optional_notes"),
            ),
        ),
    )
    update_parser.add_argument(
        "action_id", type=UUID, help=_("resources.habit_action.parser.habit_action_identifier")
    )
    update_parser.add_argument(
        "--status", help=_("resources.habit_action.parser.updated_habit_action_status")
    )
    update_parser.add_argument("--notes", help=_("common.messages.updated_notes"))
    update_parser.add_argument(
        "--clear-notes",
        action="store_true",
        help=_("resources.habit_action.parser.clear_optional_notes_field"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_habit_action_update_async))

    log_parser = add_documented_parser(
        action_subparsers,
        "log",
        help_content=HelpContent(
            summary=_("resources.habit_action.parser.update_habit_action_by_date"),
            description=(
                _(
                    "resources.habit_action.parser.materialize_or_update_habit_action_by_habit_identifier_and_action_date"
                )
                + "\n\n"
                + _(
                    "resources.habit_action.parser.use_this_command_when_checking_in_without_first_looking_up_action_id"
                )
            ),
            examples=(
                "lifeos habit-action log --habit-id 11111111-1111-1111-1111-111111111111 "
                "--date 2026-04-09 --status done",
                "lifeos habit-action log --habit-id 11111111-1111-1111-1111-111111111111 "
                '--date 2026-04-09 --status skip --notes "Travel day"',
            ),
            notes=(
                _(
                    "resources.habit_action.parser.use_update_when_you_already_have_materialized_action_identifier"
                ),
                _(
                    "resources.habit_action.parser.this_command_follows_same_editable_window_rules_as_update"
                ),
            ),
        ),
    )
    log_parser.add_argument(
        "--habit-id", required=True, type=UUID, help=_("common.messages.habit_identifier")
    )
    log_parser.add_argument(
        "--date",
        dest="action_date",
        required=True,
        type=parse_date_value,
        help=_("resources.habit_action.parser.action_date_in_yyyy_mm_dd_format"),
    )
    log_parser.add_argument(
        "--status", help=_("resources.habit_action.parser.updated_habit_action_status")
    )
    log_parser.add_argument("--notes", help=_("common.messages.updated_notes"))
    log_parser.add_argument(
        "--clear-notes",
        action="store_true",
        help=_("resources.habit_action.parser.clear_optional_notes_field"),
    )
    log_parser.set_defaults(handler=make_sync_handler(handle_habit_action_log_async))
