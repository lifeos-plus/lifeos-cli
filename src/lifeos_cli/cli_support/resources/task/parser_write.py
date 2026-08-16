"""Builder helpers for task write commands."""

from __future__ import annotations

import argparse
from uuid import UUID

from lifeos_cli.cli_support.help_utils import HelpContent, add_documented_parser
from lifeos_cli.cli_support.resources.task.handlers import (
    handle_task_add_async,
    handle_task_delete_async,
    handle_task_update_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_task_add_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task add command."""
    add_parser = add_documented_parser(
        task_subparsers,
        "add",
        help_content=HelpContent(
            summary=_("resources.task.parser_write.create_task"),
            description=(
                _("resources.task.parser_write.create_new_task_for_vision")
                + "\n\n"
                + _(
                    "resources.task.parser_write.tasks_can_be_root_tasks_or_child_tasks_under_another_task_in"
                )
                + " "
                + _(
                    "resources.task.parser_write.planning_cycle_fields_describe_enclosing_timebox_for_task_not_clock_time_execution"
                )
            ),
            examples=(
                'lifeos task add "Draft the release checklist" '
                "--vision-id 11111111-1111-1111-1111-111111111111",
                'lifeos task add "Write changelog" '
                "--vision-id 11111111-1111-1111-1111-111111111111 "
                "--parent-task-id 22222222-2222-2222-2222-222222222222",
                'lifeos task add "Prepare family meeting" '
                "--vision-id 11111111-1111-1111-1111-111111111111 "
                "--person-id 33333333-3333-3333-3333-333333333333",
                'lifeos task add "Plan shared trip" '
                "--vision-id 11111111-1111-1111-1111-111111111111 "
                "--person-id 33333333-3333-3333-3333-333333333333 "
                "--person-id 44444444-4444-4444-4444-444444444444",
                'lifeos task add "Draft sprint backlog" '
                "--vision-id 11111111-1111-1111-1111-111111111111 "
                "--planning-cycle-type week --planning-cycle-days 7 "
                "--planning-cycle-start-date 2026-04-14",
            ),
            notes=(
                _(
                    "resources.task.parser_write.planning_cycle_flags_must_be_supplied_as_complete_set_when_used"
                ),
                _(
                    "resources.task.parser_write.use_planning_cycle_fields_for_broader_year_month_week_or_day_window"
                ),
                _(
                    "resources.task.parser_write.use_lifeos_event_add_task_id_task_id_if_task_also_needs"
                ),
                _(
                    "common.messages.repeat_same_person_id_flag_to_associate_multiple_person_in_one_command"
                ),
                _(
                    "resources.task.parser_write.when_agent_creates_tasks_on_behalf_of_human_use_person_id_to"
                ),
            ),
        ),
    )
    add_parser.add_argument("content", help=_("resources.task.parser_write.task_content"))
    add_parser.add_argument(
        "--vision-id",
        required=True,
        type=UUID,
        help=_("resources.task.parser_write.owning_vision_identifier"),
    )
    add_parser.add_argument(
        "--description", help=_("resources.task.parser_write.optional_task_description")
    )
    add_parser.add_argument(
        "--parent-task-id",
        type=UUID,
        help=_("resources.task.parser_write.optional_parent_task_identifier"),
    )
    add_parser.add_argument(
        "--status", default="todo", help=_("resources.task.parser_write.task_status")
    )
    add_parser.add_argument(
        "--priority", type=int, default=0, help=_("resources.task.parser_write.task_priority")
    )
    add_parser.add_argument(
        "--display-order", type=int, default=0, help=_("common.messages.display_order")
    )
    add_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_associate_one_or_more_person"),
    )
    add_parser.add_argument(
        "--estimated-effort",
        type=int,
        help=_("resources.task.parser_write.estimated_effort_in_minutes"),
    )
    add_parser.add_argument(
        "--planning-cycle-type",
        help=_("resources.task.parser_write.planning_cycle_type_year_month_week_or_day"),
    )
    add_parser.add_argument(
        "--planning-cycle-days",
        type=int,
        help=_("resources.task.parser_write.planning_cycle_duration_in_days_for_enclosing_timebox"),
    )
    add_parser.add_argument(
        "--planning-cycle-start-date",
        help=_(
            "resources.task.parser_write.start_date_of_enclosing_planning_cycle_window_in_yyyy_mm_dd_format"
        ),
    )
    add_parser.set_defaults(handler=make_sync_handler(handle_task_add_async))


def build_task_update_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task update command."""
    update_parser = add_documented_parser(
        task_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("resources.task.parser_write.update_task"),
            description=(
                _("resources.task.parser_write.update_mutable_task_fields")
                + "\n\n"
                + _(
                    "resources.task.parser_write.only_explicitly_provided_flags_are_changed_omitted_fields_stay_unchanged"
                )
            ),
            examples=(
                "lifeos task update 11111111-1111-1111-1111-111111111111 --status in_progress",
                "lifeos task update 11111111-1111-1111-1111-111111111111 "
                "--priority 3 --display-order 20",
                "lifeos task update 11111111-1111-1111-1111-111111111111 "
                "--person-id 33333333-3333-3333-3333-333333333333",
                "lifeos task update 11111111-1111-1111-1111-111111111111 "
                "--person-id 33333333-3333-3333-3333-333333333333 "
                "--person-id 44444444-4444-4444-4444-444444444444",
                "lifeos task update 11111111-1111-1111-1111-111111111111 "
                "--clear-description --clear-estimated-effort",
                "lifeos task update 11111111-1111-1111-1111-111111111111 "
                "--planning-cycle-type month --planning-cycle-days 30 "
                "--planning-cycle-start-date 2026-04-01",
                "lifeos task update 11111111-1111-1111-1111-111111111111 --clear-parent",
                "lifeos task update 11111111-1111-1111-1111-111111111111 --clear-planning-cycle",
            ),
            notes=(
                _(
                    "resources.task.parser_write.parent_task_references_must_stay_within_same_vision"
                ),
                _(
                    "resources.task.parser_write.use_clear_parent_to_move_child_task_back_to_root_level"
                ),
                _(
                    "resources.task.parser_write.updated_planning_cycle_fields_still_describe_enclosing_timebox_not_specific_scheduled_timestamp"
                ),
                _(
                    "resources.task.parser_write.use_clear_flags_to_remove_optional_values_such_as_descriptions_or_planning"
                ),
                _(
                    "resources.task.parser_write.use_repeated_person_id_to_keep_human_only_agent_only_and_shared"
                ),
            ),
        ),
    )
    update_parser.add_argument("task_id", type=UUID, help=_("common.messages.task_identifier"))
    update_parser.add_argument(
        "--content", help=_("resources.task.parser_write.updated_task_content")
    )
    update_parser.add_argument("--description", help=_("common.messages.updated_description"))
    update_parser.add_argument(
        "--clear-description",
        action="store_true",
        help=_("resources.task.parser_write.clear_optional_task_description"),
    )
    update_parser.add_argument(
        "--parent-task-id",
        type=UUID,
        help=_("resources.task.parser_write.updated_parent_task_identifier"),
    )
    update_parser.add_argument(
        "--clear-parent",
        action="store_true",
        help=_(
            "resources.task.parser_write.move_task_to_root_level_by_clearing_its_parent_task_reference"
        ),
    )
    update_parser.add_argument(
        "--status", help=_("resources.task.parser_write.updated_task_status")
    )
    update_parser.add_argument(
        "--priority", type=int, help=_("resources.task.parser_write.updated_priority")
    )
    update_parser.add_argument(
        "--display-order", type=int, help=_("common.messages.updated_display_order")
    )
    update_parser.add_argument(
        "--person-id",
        dest="person_ids",
        type=UUID,
        action="append",
        default=None,
        help=_("common.messages.repeat_to_replace_person_with_one_or_more_identifiers"),
    )
    update_parser.add_argument(
        "--clear-person", action="store_true", help=_("common.messages.remove_all_person")
    )
    update_parser.add_argument(
        "--estimated-effort",
        type=int,
        help=_("resources.task.parser_write.updated_estimated_effort"),
    )
    update_parser.add_argument(
        "--clear-estimated-effort",
        action="store_true",
        help=_("resources.task.parser_write.clear_optional_estimated_effort_value"),
    )
    update_parser.add_argument(
        "--planning-cycle-type",
        help=_("resources.task.parser_write.updated_planning_cycle_type_year_month_week_or_day"),
    )
    update_parser.add_argument(
        "--planning-cycle-days",
        type=int,
        help=_(
            "resources.task.parser_write.updated_planning_cycle_duration_in_days_for_enclosing_timebox"
        ),
    )
    update_parser.add_argument(
        "--planning-cycle-start-date",
        help=_(
            "resources.task.parser_write.updated_start_date_of_enclosing_planning_cycle_window_in_yyyy_mm_dd"
        ),
    )
    update_parser.add_argument(
        "--clear-planning-cycle",
        action="store_true",
        help=_("resources.task.parser_write.clear_all_planning_cycle_fields"),
    )
    update_parser.set_defaults(handler=make_sync_handler(handle_task_update_async))


def build_task_delete_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task delete command."""
    delete_parser = add_documented_parser(
        task_subparsers,
        "delete",
        help_content=HelpContent(
            summary=_("resources.task.parser_write.delete_task"),
            description=_("resources.task.parser_write.delete_task_description"),
            examples=("lifeos task delete 11111111-1111-1111-1111-111111111111",),
        ),
    )
    delete_parser.add_argument("task_id", type=UUID, help=_("common.messages.task_identifier"))
    delete_parser.set_defaults(handler=make_sync_handler(handle_task_delete_async))
