"""Builder helpers for task structure commands."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import HelpContent, add_documented_parser
from lifeos_cli.cli_support.resources.task.handlers import (
    handle_task_move_async,
    handle_task_reorder_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_task_move_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    move_parser = add_documented_parser(
        task_subparsers,
        "move",
        help_content=HelpContent(
            summary=_("resources.task.parser_structure.move_task"),
            description=_(
                "resources.task.parser_structure.move_task_to_new_parent_and_optionally_new_vision"
            ),
            examples=(
                "lifeos task move 11111111-1111-1111-1111-111111111111 "
                "--new-parent-task-id 22222222-2222-2222-2222-222222222222",
                "lifeos task move 11111111-1111-1111-1111-111111111111 "
                "--old-parent-task-id 00000000-0000-0000-0000-000000000000 "
                "--new-parent-task-id 22222222-2222-2222-2222-222222222222 "
                "--new-display-order 10",
                "lifeos task move 11111111-1111-1111-1111-111111111111 "
                "--new-vision-id 33333333-3333-3333-3333-333333333333 --clear-parent",
            ),
            notes=(
                _(
                    "resources.task.parser_structure.use_reorder_when_only_sibling_display_order_changes_and_parentage_stays_same"
                ),
                _(
                    "resources.task.parser_structure.use_old_parent_task_id_as_optimistic_guard_when_another_writer_may"
                ),
            ),
        ),
    )
    move_parser.add_argument("task_id", type=UUID, help=_("common.messages.task_identifier"))
    move_parser.add_argument(
        "--old-parent-task-id",
        type=UUID,
        help=_("resources.task.parser_structure.expected_current_parent_task_identifier"),
    )
    move_parser.add_argument(
        "--new-parent-task-id",
        type=UUID,
        help=_("resources.task.parser_structure.target_parent_task_identifier"),
    )
    move_parser.add_argument(
        "--clear-parent",
        action="store_true",
        help=_("resources.task.parser_structure.move_task_to_root_level"),
    )
    move_parser.add_argument(
        "--new-vision-id",
        type=UUID,
        help=_("resources.task.parser_structure.target_vision_identifier"),
    )
    move_parser.add_argument(
        "--new-display-order",
        type=int,
        help=_("resources.task.parser_structure.target_display_order"),
    )
    move_parser.set_defaults(handler=make_sync_handler(handle_task_move_async))


def build_task_reorder_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    reorder_parser = add_documented_parser(
        task_subparsers,
        "reorder",
        help_content=HelpContent(
            summary=_("resources.task.parser_structure.reorder_tasks"),
            description=_(
                "resources.task.parser_structure.update_display_order_values_for_one_or_more_tasks"
            ),
            examples=(
                "lifeos task reorder --order 11111111-1111-1111-1111-111111111111:0 "
                "--order 22222222-2222-2222-2222-222222222222:1",
            ),
            notes=(
                _(
                    "resources.task.parser_structure.this_command_changes_only_display_order_it_does_not_move_tasks_between"
                ),
                _(
                    "resources.task.parser_structure.use_move_when_parentage_or_vision_membership_also_needs_to_change"
                ),
            ),
        ),
    )
    reorder_parser.add_argument(
        "--order",
        action="append",
        required=True,
        help=_(
            "resources.task.parser_structure.task_order_in_task_id_display_order_format_repeat_for_multiple_tasks"
        ),
    )
    reorder_parser.set_defaults(handler=make_sync_handler(handle_task_reorder_async))
