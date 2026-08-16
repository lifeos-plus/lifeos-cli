"""Builder helpers for task batch commands."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.parser_common import add_batch_delete_namespace
from lifeos_cli.cli_support.resources.task.handlers import handle_task_batch_delete_async
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.i18n import cli_message as _


def build_task_batch_parser(
    task_subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Build the task batch command tree."""
    add_batch_delete_namespace(
        task_subparsers,
        dest="task_batch_command",
        ids_dest="task_ids",
        noun="task",
        delete_handler=make_sync_handler(handle_task_batch_delete_async),
        batch_summary=_("resources.task.parser_batch.run_batch_task_operations"),
        batch_description=_("resources.task.parser_batch.delete_multiple_tasks_in_one_command"),
        batch_examples=(
            "lifeos task batch delete --help",
            "lifeos task batch delete --ids <task-id-1> <task-id-2>",
        ),
        batch_notes=(
            _("common.messages.this_namespace_currently_exposes_only_delete_workflow"),
            _("common.messages.use_data_batch_delete_for_file_or_stream_bulk_workflows"),
        ),
        delete_summary=_("resources.task.parser_batch.delete_multiple_tasks"),
        delete_description=_("resources.task.parser_batch.delete_multiple_tasks_by_identifier"),
        delete_examples=("lifeos task batch delete --ids <task-id-1> <task-id-2>",),
    )
