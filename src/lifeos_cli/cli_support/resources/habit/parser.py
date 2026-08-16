"""Habit resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.habit.parser_actions import (
    build_habit_add_parser,
    build_habit_delete_parser,
    build_habit_list_parser,
    build_habit_show_parser,
    build_habit_stats_parser,
    build_habit_task_associations_parser,
    build_habit_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_habit_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the habit command tree."""
    habit_parser = add_documented_help_parser(
        subparsers,
        "habit",
        help_content=HelpContent(
            summary=_("resources.habit.parser.manage_recurring_habits"),
            description=(
                _(
                    "resources.habit.parser.create_and_maintain_recurring_habits_with_explicit_cadence_rules"
                )
                + "\n\n"
                + _(
                    "resources.habit.parser.habits_define_recurring_work_query_windows_materialize_habit_action_occurrences_on_demand"
                )
            ),
            examples=(
                "lifeos habit add --help",
                "lifeos habit list --help",
                "lifeos habit batch --help",
            ),
            notes=(
                _("resources.habit.parser.use_list_as_primary_query_entrypoint_for_habits"),
                _(
                    "resources.habit.parser.habit_creation_and_timing_updates_no_longer_pre_generate_full_habit_action"
                ),
                _(
                    "resources.habit.parser.cadence_cycles_can_be_daily_weekly_monthly_or_yearly_while_habit_action"
                ),
            ),
        ),
    )
    habit_subparsers = habit_parser.add_subparsers(
        dest="habit_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_habit_add_parser(habit_subparsers)
    build_habit_list_parser(habit_subparsers)
    build_habit_show_parser(habit_subparsers)
    build_habit_update_parser(habit_subparsers)
    build_habit_delete_parser(habit_subparsers)
    build_habit_stats_parser(habit_subparsers)
    build_habit_task_associations_parser(habit_subparsers)
