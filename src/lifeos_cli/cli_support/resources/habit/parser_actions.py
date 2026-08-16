"""Builder helpers for core habit commands."""

from __future__ import annotations

import argparse
import re
from datetime import date
from uuid import UUID

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_batch_delete_namespace,
    add_limit_offset_arguments,
)
from lifeos_cli.cli_support.resources.habit.handlers import (
    HABIT_SUMMARY_COLUMNS,
    HABIT_SUMMARY_WITH_STATS_COLUMNS,
    HABIT_TASK_ASSOCIATION_COLUMNS,
    handle_habit_add_async,
    handle_habit_batch_delete_async,
    handle_habit_delete_async,
    handle_habit_list_async,
    handle_habit_show_async,
    handle_habit_stats_async,
    handle_habit_task_associations_async,
    handle_habit_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _

_WEEKDAY_SPLIT_PATTERN = re.compile(r"[\s,]+")


def _parse_habit_weekdays(value: str) -> list[str]:
    """Parse one CLI weekday list into canonical tokens."""
    weekdays = [part for part in _WEEKDAY_SPLIT_PATTERN.split(value.strip()) if part]
    if not weekdays:
        raise argparse.ArgumentTypeError(
            "Expected at least one weekday, for example `monday,wednesday,friday`."
        )
    return weekdays


def _parse_habit_monthdays(value: str) -> list[int]:
    """Parse one CLI monthday list into integer day numbers."""
    parts = [part for part in _WEEKDAY_SPLIT_PATTERN.split(value.strip()) if part]
    if not parts:
        raise argparse.ArgumentTypeError("Expected at least one month day, for example `1,15,28`.")
    monthdays: list[int] = []
    for part in parts:
        try:
            monthday = int(part)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("Month days must be integers.") from exc
        monthdays.append(monthday)
    return monthdays


def build_habit_add_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit add command."""
    add_parser = add_documented_parser(
        habit_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.create_habit"),
            description=_(
                "resources.habit.parser_actions.create_recurring_habit_with_cadence_aligned_on_demand_occurrences"
            ),
            examples=(
                'lifeos habit add "Daily Exercise" --start-date 2026-04-09 --duration-days 21',
                'lifeos habit add "Morning Review" --start-date 2026-04-09 --duration-days 100 '
                "--task-id 11111111-1111-1111-1111-111111111111",
                'lifeos habit add "Gym" --start-date 2026-04-09 --duration-days 100 '
                "--cadence-frequency weekly --weekdays monday,wednesday,friday "
                "--target-per-week 3",
                'lifeos habit add "Monthly cleanup" --start-date 2026-04-09 --duration-days 365 '
                "--cadence-frequency monthly --monthdays 1,15 --target-per-cycle 2",
                'lifeos habit add "Read annual plan" --start-date 2026-01-01 --duration-days 365 '
                "--cadence-frequency yearly --target-per-cycle 6",
            ),
            notes=(
                _(
                    "resources.habit.parser_actions.duration_must_be_one_of_supported_program_lengths"
                ),
                _(
                    "resources.habit.parser_actions.use_cadence_frequency_to_choose_daily_weekly_monthly_or_yearly_evaluation_cycles"
                ),
                _(
                    "resources.habit.parser_actions.weekdays_restricts_on_demand_habit_action_occurrences_to_selected_weekdays"
                ),
                _("resources.habit.parser_actions.if_task_id_is_provided_task_must_already_exist"),
            ),
        ),
    )
    add_parser.add_argument("title", help=_("resources.habit.parser_actions.habit_title"))
    add_parser.add_argument(
        "--description", help=_("resources.habit.parser_actions.optional_habit_description")
    )
    add_parser.add_argument(
        "--start-date",
        required=True,
        type=date.fromisoformat,
        help=_("resources.habit.parser_actions.habit_start_date_in_yyyy_mm_dd_format"),
    )
    add_parser.add_argument(
        "--duration-days",
        required=True,
        type=int,
        help=_("resources.habit.parser_actions.habit_duration_in_days"),
    )
    add_parser.add_argument(
        "--cadence-frequency",
        default="daily",
        help=_(
            "resources.habit.parser_actions.habit_cadence_frequency_daily_weekly_monthly_or_yearly"
        ),
    )
    add_parser.add_argument(
        "--weekdays",
        type=_parse_habit_weekdays,
        help=_(
            "resources.habit.parser_actions.allowed_weekdays_for_example_monday_wednesday_friday"
        ),
    )
    add_parser.add_argument(
        "--weekends-only",
        action="store_true",
        help=_("resources.habit.parser_actions.shortcut_for_weekdays_saturday_sunday"),
    )
    add_parser.add_argument(
        "--monthdays",
        type=_parse_habit_monthdays,
        help=_("resources.habit.parser_actions.allowed_monthdays_for_example_1_15_28"),
    )
    add_parser.add_argument(
        "--target-per-cycle",
        dest="target_per_cycle",
        type=int,
        help=_(
            "resources.habit.parser_actions.cadence_target_count_for_one_cycle_daily_habits_must_keep_1"
        ),
    )
    add_parser.add_argument(
        "--target-per-week",
        dest="target_per_cycle",
        type=int,
        help=_("resources.habit.parser_actions.weekly_alias_for_target_per_cycle"),
    )
    add_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.optional_linked_task_identifier")
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_habit_add_async))


def build_habit_list_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit list command."""
    list_parser = add_documented_parser(
        habit_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.list_habits"),
            description=(
                _(
                    "resources.habit.parser_actions.list_habits_with_optional_status_title_and_activity_window_filters"
                )
                + "\n\n"
                + _(
                    "resources.habit.parser_actions.use_this_command_as_primary_query_entrypoint_for_habits"
                )
            ),
            examples=(
                "lifeos habit list",
                "lifeos habit list --status active --with-stats",
                'lifeos habit list --title "Daily Exercise" --active-window-only',
                "lifeos habit list --status active --count",
            ),
            notes=(
                _(
                    "resources.habit.parser_actions.use_with_stats_when_summary_should_include_cycle_progress_and_streak_fields"
                ),
                _(
                    "resources.habit.parser_actions.use_active_window_only_to_show_habits_whose_duration_still_covers_today"
                ),
                _(
                    "resources.habit.parser_actions.default_list_output_prints_header_row_followed_by_tab_separated_columns_columns"
                ).format(columns=format_summary_column_list(HABIT_SUMMARY_COLUMNS)),
                _(
                    "resources.habit.parser_actions.with_with_stats_header_changes_to_columns"
                ).format(columns=format_summary_column_list(HABIT_SUMMARY_WITH_STATS_COLUMNS)),
            ),
        ),
    )
    list_parser.add_argument(
        "--status", help=_("resources.habit.parser_actions.filter_by_habit_status")
    )
    list_parser.add_argument(
        "--title", help=_("resources.habit.parser_actions.filter_by_exact_habit_title")
    )
    list_parser.add_argument(
        "--active-window-only",
        action="store_true",
        help=_(
            "resources.habit.parser_actions.restrict_results_to_habits_whose_duration_still_covers_today"
        ),
    )
    list_parser.add_argument(
        "--with-stats",
        action="store_true",
        help=_(
            "resources.habit.parser_actions.include_progress_and_streak_information_in_each_summary_row"
        ),
    )
    list_parser.add_argument(
        "--count", action="store_true", help=_("common.messages.print_total_matched_count")
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_habit_list_async))


def build_habit_show_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit show command."""
    show_parser = add_documented_parser(
        habit_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.show_habit"),
            description=_(
                "resources.habit.parser_actions.show_one_habit_with_full_metadata_and_derived_statistics"
            ),
            examples=(
                "lifeos habit show 11111111-1111-1111-1111-111111111111",
                "lifeos habit show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument("habit_id", type=UUID, help=_("common.messages.habit_identifier"))
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_habit_show_async))


def build_habit_update_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit update command."""
    update_parser = add_documented_parser(
        habit_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.update_habit"),
            description=(
                _("resources.habit.parser_actions.update_mutable_habit_fields")
                + "\n\n"
                + _(
                    "resources.habit.parser_actions.cadence_and_timing_changes_reconcile_materialized_habit_action_records_without_regenerating_full"
                )
            ),
            examples=(
                "lifeos habit update 11111111-1111-1111-1111-111111111111 --status paused",
                "lifeos habit update 11111111-1111-1111-1111-111111111111 "
                "--duration-days 100 --start-date 2026-04-10",
                "lifeos habit update 11111111-1111-1111-1111-111111111111 "
                "--cadence-frequency weekly --weekends-only --target-per-week 1",
                "lifeos habit update 11111111-1111-1111-1111-111111111111 "
                "--cadence-frequency monthly --monthdays 1,15 --target-per-cycle 2",
                "lifeos habit update 11111111-1111-1111-1111-111111111111 --clear-weekdays",
                "lifeos habit update 11111111-1111-1111-1111-111111111111 --clear-monthdays",
                "lifeos habit update 11111111-1111-1111-1111-111111111111 --clear-task",
            ),
            notes=(
                _(
                    "resources.habit.parser_actions.use_clear_description_or_clear_task_to_remove_optional_values"
                ),
                _(
                    "resources.habit.parser_actions.use_clear_weekdays_to_remove_weekday_restrictions_without_resetting_cadence"
                ),
                _(
                    "resources.habit.parser_actions.reactivating_habit_still_respects_active_habit_limit"
                ),
            ),
        ),
    )
    update_parser.add_argument("habit_id", type=UUID, help=_("common.messages.habit_identifier"))
    update_parser.add_argument(
        "--title", help=_("resources.habit.parser_actions.updated_habit_title")
    )
    update_parser.add_argument(
        "--description", help=_("resources.habit.parser_actions.updated_habit_description")
    )
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.habit.parser_actions.clear_optional_habit_description"),
    )
    update_parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        help=_("resources.habit.parser_actions.updated_habit_start_date_in_yyyy_mm_dd_format"),
    )
    update_parser.add_argument(
        "--duration-days",
        type=int,
        help=_("resources.habit.parser_actions.updated_duration_in_days"),
    )
    update_parser.add_argument(
        "--cadence-frequency",
        help=_(
            "resources.habit.parser_actions.updated_cadence_frequency_daily_weekly_monthly_or_yearly"
        ),
    )
    update_parser.add_argument(
        "--weekdays",
        type=_parse_habit_weekdays,
        help=_(
            "resources.habit.parser_actions.updated_allowed_weekdays_for_example_monday_wednesday_friday"
        ),
    )
    update_parser.add_argument(
        "--weekends-only",
        action="store_true",
        help=_("resources.habit.parser_actions.shortcut_for_weekdays_saturday_sunday"),
    )
    update_parser.add_argument(
        "--clear-weekdays",
        action="store_true",
        help=_("resources.habit.parser_actions.remove_weekday_restrictions_from_habit_cadence"),
    )
    update_parser.add_argument(
        "--monthdays",
        type=_parse_habit_monthdays,
        help=_("resources.habit.parser_actions.updated_allowed_monthdays_for_example_1_15_28"),
    )
    update_parser.add_argument(
        "--clear-monthdays",
        action="store_true",
        help=_("resources.habit.parser_actions.remove_monthday_restrictions_from_habit_cadence"),
    )
    update_parser.add_argument(
        "--target-per-cycle",
        dest="target_per_cycle",
        type=int,
        help=_("resources.habit.parser_actions.updated_cadence_target_count_for_one_cycle"),
    )
    update_parser.add_argument(
        "--target-per-week",
        dest="target_per_cycle",
        type=int,
        help=_("resources.habit.parser_actions.weekly_alias_for_target_per_cycle"),
    )
    update_parser.add_argument(
        "--status", help=_("resources.habit.parser_actions.updated_habit_status")
    )
    update_parser.add_argument(
        "--task-id", type=UUID, help=_("common.messages.updated_linked_task_identifier")
    )
    update_parser.add_argument(
        "--clear-task",
        action="store_true",
        help=_("resources.habit.parser_actions.remove_linked_task_reference"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_habit_update_async))


def build_habit_delete_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit delete command."""
    delete_parser = add_documented_parser(
        habit_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.delete_habit"),
            description=_("resources.habit.parser_actions.delete_one_habit"),
            examples=("lifeos habit delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument("habit_id", type=UUID, help=_("common.messages.habit_identifier"))
    delete_parser.set_defaults(handler=make_sync_handler(handle_habit_delete_async))


def build_habit_stats_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit stats command."""
    stats_parser = add_documented_parser(
        habit_subparsers,
        "stats",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.show_habit_statistics"),
            description=_(
                "resources.habit.parser_actions.show_derived_completion_and_streak_statistics_for_one_habit"
            ),
            examples=("lifeos habit stats 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.habit.parser_actions.these_metrics_are_derived_from_cadence_settings_together_with_materialized_habit_action"
                ),
                _(
                    "resources.habit.parser_actions.use_show_when_you_also_need_underlying_habit_fields_in_same_output"
                ),
            ),
        ),
    )
    stats_parser.add_argument("habit_id", type=UUID, help=_("common.messages.habit_identifier"))
    stats_parser.set_defaults(handler=make_sync_handler(handle_habit_stats_async))


def build_habit_task_associations_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit task-associations command."""
    associations_parser = add_documented_parser(
        habit_subparsers,
        "task-associations",
        help_content=HelpContent(
            summary=_("resources.habit.parser_actions.list_task_to_habit_associations"),
            description=_(
                "resources.habit.parser_actions.show_active_habits_currently_linked_to_tasks"
            ),
            examples=("lifeos habit task-associations",),
            notes=(
                _(
                    "resources.habit.parser_actions.use_this_command_to_audit_which_active_habits_are_still_attached_to"
                ),
                _(
                    "resources.habit.parser_actions.when_results_exist_command_prints_header_row_followed_by_tab_separated_columns"
                ).format(columns=format_summary_column_list(HABIT_TASK_ASSOCIATION_COLUMNS)),
            ),
        ),
    )
    associations_parser.set_defaults(
        handler=make_sync_handler(handle_habit_task_associations_async)
    )


def build_habit_batch_parser(
    habit_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the habit batch command tree."""
    add_batch_delete_namespace(
        habit_subparsers,
        dest="habit_batch_command",
        ids_dest="habit_ids",
        noun="habit",
        delete_handler=make_sync_handler(handle_habit_batch_delete_async),
        batch_summary=_("resources.habit.parser_actions.run_bulk_habit_operations"),
        batch_description=_("resources.habit.parser_actions.delete_multiple_habits_in_one_command"),
        batch_examples=(
            "lifeos habit batch delete --help",
            "lifeos habit batch delete --ids <habit-id-1> <habit-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.habit.parser_actions.delete_multiple_habits"),
        delete_description=_(
            "resources.habit.parser_actions.delete_multiple_habits_in_one_command"
        ),
        delete_examples=("lifeos habit batch delete --ids <habit-id-1> <habit-id-2>",),
    )
