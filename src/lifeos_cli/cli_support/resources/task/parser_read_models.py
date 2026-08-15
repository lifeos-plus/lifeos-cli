"""Builder helpers for task read-model commands."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import HelpContent, add_documented_parser
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.output_utils import format_summary_column_list
from lifeos_cli.cli_support.parser_common import (
    add_limit_offset_arguments,
)
from lifeos_cli.cli_support.resources.task.handlers import (
    TASK_SUMMARY_COLUMNS,
    handle_task_hierarchy_async,
    handle_task_list_async,
    handle_task_show_async,
    handle_task_stats_async,
    handle_task_with_subtasks_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_task_list_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task list command."""
    list_parser = add_documented_parser(
        task_subparsers,
        "list",
        help_content=HelpContent(
            summary=_("resources.task.parser_read_models.list_tasks"),
            description=(
                _(
                    "resources.task.parser_read_models.list_tasks_with_optional_vision_parent_or_status_filters"
                )
                + "\n\n"
                + _(
                    "resources.task.parser_read_models.use_this_command_as_primary_query_entrypoint_for_structured_task_views"
                )
            ),
            examples=(
                "lifeos task list",
                "lifeos task list --vision-id 11111111-1111-1111-1111-111111111111",
                "lifeos task list --person-id 11111111-1111-1111-1111-111111111111",
                "lifeos task list --parent-task-id "
                "22222222-2222-2222-2222-222222222222 --status todo",
            ),
            notes=(
                _(
                    "resources.task.parser_read_models.when_vision_id_is_provided_without_parent_task_id_only_root_tasks"
                ),
                _(
                    "common.messages.when_results_exist_list_command_prints_header_row_followed_by_tab_separated"
                ).format(columns=format_summary_column_list(TASK_SUMMARY_COLUMNS)),
                _("resources.task.parser_read_models.use_limit_and_offset_for_pagination"),
            ),
        ),
    )
    list_parser.add_argument(
        "--vision-id",
        type=UUID,
        help=_("resources.task.parser_read_models.filter_by_vision_identifier"),
    )
    list_parser.add_argument(
        "--vision-in",
        help=_("resources.task.parser_read_models.comma_separated_vision_identifiers"),
    )
    list_parser.add_argument(
        "--parent-task-id",
        type=UUID,
        help=_("resources.task.parser_read_models.filter_by_parent_task_identifier"),
    )
    list_parser.add_argument(
        "--person-id", type=UUID, help=_("common.messages.filter_by_linked_person_identifier")
    )
    list_parser.add_argument(
        "--status", help=_("resources.task.parser_read_models.filter_by_task_status")
    )
    list_parser.add_argument(
        "--status-in",
        help=_("resources.task.parser_read_models.comma_separated_statuses_to_include"),
    )
    list_parser.add_argument(
        "--exclude-status",
        help=_("resources.task.parser_read_models.comma_separated_statuses_to_exclude"),
    )
    list_parser.add_argument(
        "--planning-cycle-type",
        help=_("resources.task.parser_read_models.filter_by_planning_cycle_type"),
    )
    list_parser.add_argument(
        "--planning-cycle-start-date",
        help=_("resources.task.parser_read_models.filter_by_planning_cycle_start_date_yyyy_mm_dd"),
    )
    list_parser.add_argument(
        "--content", help=_("resources.task.parser_read_models.filter_by_exact_task_content")
    )
    add_limit_offset_arguments(list_parser)
    add_json_output_argument(list_parser)
    list_parser.set_defaults(handler=make_sync_handler(handle_task_list_async))


def build_task_show_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task show command."""
    show_parser = add_documented_parser(
        task_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("resources.task.parser_read_models.show_task"),
            description=_("resources.task.parser_read_models.show_one_task_with_full_metadata"),
            examples=(
                "lifeos task show 11111111-1111-1111-1111-111111111111",
                "lifeos task show 11111111-1111-1111-1111-111111111111",
            ),
        ),
    )
    show_parser.add_argument("task_id", type=UUID, help=_("common.messages.task_identifier"))
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=make_sync_handler(handle_task_show_async))


def build_task_with_subtasks_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task with-subtasks command."""
    with_subtasks_parser = add_documented_parser(
        task_subparsers,
        "with-subtasks",
        help_content=HelpContent(
            summary=_("resources.task.parser_read_models.show_task_subtree"),
            description=_(
                "resources.task.parser_read_models.show_one_task_with_its_active_nested_subtasks"
            ),
            examples=("lifeos task with-subtasks 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.task.parser_read_models.the_root_task_prints_first_followed_by_active_descendants_indented_by_depth"
                ),
                _(
                    "resources.task.parser_read_models.use_hierarchy_when_you_need_full_active_tree_for_entire_vision"
                ),
            ),
        ),
    )
    with_subtasks_parser.add_argument(
        "task_id", type=UUID, help=_("common.messages.task_identifier")
    )
    with_subtasks_parser.set_defaults(handler=make_sync_handler(handle_task_with_subtasks_async))


def build_task_hierarchy_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task hierarchy command."""
    hierarchy_parser = add_documented_parser(
        task_subparsers,
        "hierarchy",
        help_content=HelpContent(
            summary=_("resources.task.parser_read_models.show_vision_task_hierarchy"),
            description=_(
                "resources.task.parser_read_models.show_all_active_tasks_for_vision_as_hierarchy"
            ),
            examples=("lifeos task hierarchy 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.task.parser_read_models.the_output_starts_with_vision_identifier_then_prints_each_root_task_and"
                ),
                _(
                    "resources.task.parser_read_models.use_with_subtasks_when_you_want_to_inspect_only_one_branch_of"
                ),
            ),
        ),
    )
    hierarchy_parser.add_argument(
        "vision_id", type=UUID, help=_("common.messages.vision_identifier")
    )
    hierarchy_parser.set_defaults(handler=make_sync_handler(handle_task_hierarchy_async))


def build_task_stats_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task stats command."""
    stats_parser = add_documented_parser(
        task_subparsers,
        "stats",
        help_content=HelpContent(
            summary=_("resources.task.parser_read_models.show_task_statistics"),
            description=_(
                "resources.task.parser_read_models.show_subtree_completion_and_effort_statistics_for_one_task"
            ),
            examples=("lifeos task stats 11111111-1111-1111-1111-111111111111",),
            notes=(
                _(
                    "resources.task.parser_read_models.totals_aggregate_selected_task_together_with_all_active_descendants"
                ),
                _(
                    "resources.task.parser_read_models.when_task_has_direct_children_completion_percentage_measures_how_many_of_those"
                ),
            ),
        ),
    )
    stats_parser.add_argument("task_id", type=UUID, help=_("common.messages.task_identifier"))
    stats_parser.set_defaults(handler=make_sync_handler(handle_task_stats_async))
