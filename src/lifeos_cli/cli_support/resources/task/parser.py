"""Task resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
)
from lifeos_cli.cli_support.resources.task.parser_read_models import (
    build_task_hierarchy_parser,
    build_task_list_parser,
    build_task_show_parser,
    build_task_stats_parser,
    build_task_with_subtasks_parser,
)
from lifeos_cli.cli_support.resources.task.parser_structure import (
    build_task_move_parser,
    build_task_reorder_parser,
)
from lifeos_cli.cli_support.resources.task.parser_write import (
    build_task_add_parser,
    build_task_delete_parser,
    build_task_update_parser,
)
from lifeos_cli.i18n import cli_message as _


def build_task_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the task command tree."""
    task_parser = add_documented_help_parser(
        subparsers,
        "task",
        help_content=HelpContent(
            summary=_("resources.task.parser.manage_hierarchical_tasks"),
            description=(
                _("resources.task.parser.create_and_maintain_task_trees_that_belong_to_vision")
                + "\n\n"
                + _(
                    "resources.task.parser.tasks_are_main_execution_unit_in_lifeos_and_can_be_nested_under"
                )
                + " "
                + _(
                    "resources.task.parser.use_planning_cycle_fields_for_broader_timebox_use_event_when_task_also"
                )
            ),
            examples=(
                "lifeos task add --help",
                "lifeos task list --help",
                "lifeos task batch --help",
            ),
            notes=(
                _("common.messages.use_list_as_primary_query_entrypoint_for_this_resource"),
                _("resources.task.parser.tasks_can_form_trees_through_parent_task_id"),
                _(
                    "resources.task.parser.use_lifeos_event_add_task_id_task_id_when_task_also_needs"
                ),
            ),
        ),
    )
    task_subparsers = task_parser.add_subparsers(
        dest="task_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    build_task_add_parser(task_subparsers)
    build_task_list_parser(task_subparsers)
    build_task_show_parser(task_subparsers)
    build_task_with_subtasks_parser(task_subparsers)
    build_task_hierarchy_parser(task_subparsers)
    build_task_stats_parser(task_subparsers)
    build_task_move_parser(task_subparsers)
    build_task_reorder_parser(task_subparsers)
    build_task_update_parser(task_subparsers)
    build_task_delete_parser(task_subparsers)
