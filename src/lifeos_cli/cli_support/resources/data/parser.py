"""Data resource parser construction."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.resources.data.handlers import (
    handle_data_batch_delete_async,
    handle_data_batch_update_async,
    handle_data_export_async,
    handle_data_import_async,
)
from lifeos_cli.cli_support.runtime_utils import make_sync_handler
from lifeos_cli.db.services.data_ops import SUPPORTED_DATA_RESOURCES
from lifeos_cli.i18n import cli_message as _

DATA_RESOURCE_CHOICES = tuple(SUPPORTED_DATA_RESOURCES)
EXPORT_TARGET_CHOICES = (*DATA_RESOURCE_CHOICES, "all")
IMPORT_TARGET_CHOICES = (*DATA_RESOURCE_CHOICES, "bundle")


def build_data_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the data command tree."""
    data_parser = add_documented_help_parser(
        subparsers,
        "data",
        help_content=HelpContent(
            summary=_("resources.data.parser.run_unified_data_import_export_and_batch_commands"),
            description=(
                _("resources.data.parser.run_canonical_data_operations_across_lifeos_resources")
                + "\n\n"
                + _(
                    "resources.data.parser.use_this_namespace_for_machine_oriented_bulk_workflows_such_as_export_import"
                )
            ),
            examples=(
                "lifeos data export --help",
                "lifeos data import --help",
                "lifeos data batch-update --help",
            ),
            notes=(
                _(
                    "resources.data.parser.this_namespace_uses_canonical_json_jsonl_snapshot_rows_instead_of_ad_hoc"
                ),
                _(
                    "resources.data.parser.use_export_output_as_round_trip_contract_for_later_import_or_batch"
                ),
                _(
                    "resources.data.parser.bundle_import_export_preserves_record_identifiers_and_relationships_across_resources"
                ),
                _(
                    "resources.data.parser.use_resource_specific_commands_for_higher_level_behaviors_such_as_recurring_event"
                ),
                _(
                    "resources.data.parser.use_dry_run_before_applying_large_imports_or_batch_changes"
                ),
                _("resources.data.parser.finance_not_yet_covered_by_data_namespace"),
            ),
        ),
    )
    data_subparsers = data_parser.add_subparsers(
        dest="data_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    export_parser = add_documented_parser(
        data_subparsers,
        "export",
        help_content=HelpContent(
            summary=_("resources.data.parser.export_one_resource_or_full_bundle"),
            description=(
                _(
                    "resources.data.parser.export_canonical_snapshot_rows_for_one_resource_or_create_full_bundle_zip"
                )
                + " "
                + _("resources.data.parser.bundle_export_is_implied_when_target_is_all")
            ),
            examples=(
                "lifeos data export task --format jsonl",
                "lifeos data export person --format json --output person.json",
                "lifeos data export all --output lifeos-bundle.zip",
            ),
        ),
    )
    export_parser.add_argument("target", choices=EXPORT_TARGET_CHOICES)
    export_parser.add_argument(
        "--format",
        choices=("jsonl", "json", "bundle"),
        default="jsonl",
        help=_("resources.data.parser.export_format_for_one_resource_bundle_is_implied_for_all"),
    )
    export_parser.add_argument(
        "--output", help=_("resources.data.parser.write_exported_data_to_file_instead_of_stdout")
    )
    export_parser.set_defaults(handler=make_sync_handler(handle_data_export_async))

    import_parser = add_documented_parser(
        data_subparsers,
        "import",
        help_content=HelpContent(
            summary=_("resources.data.parser.import_one_resource_or_full_bundle"),
            description=(
                _(
                    "resources.data.parser.import_canonical_snapshot_rows_for_one_resource_or_restore_full_bundle_zip"
                )
                + " "
                + _("resources.data.parser.bundle_import_is_implied_when_target_is_bundle")
            ),
            examples=(
                "lifeos data import timelog --file timelog.jsonl --format jsonl",
                "lifeos data import note --stdin --format json",
                "lifeos data import bundle --file lifeos-bundle.zip --replace-existing",
                "lifeos data import area --file areas.json --mode upsert --key name",
            ),
            notes=(
                _(
                    "resources.data.parser.use_import_bundle_for_full_backup_restore_bundle_restore_is_atomic_and"
                ),
                _(
                    "resources.data.parser.single_resource_imports_expect_referenced_foreign_rows_to_already_exist"
                ),
                _(
                    "resources.data.parser.use_dry_run_before_applying_large_file_or_full_bundle_restore"
                ),
                _(
                    "resources.data.parser.natural_key_upsert_supported_keys_are_area_name_vision_name_person_name_and_habit_title"
                ),
            ),
        ),
    )
    import_parser.add_argument("target", choices=IMPORT_TARGET_CHOICES)
    import_parser.add_argument("--file", help=_("resources.data.parser.read_input_data_from_file"))
    import_parser.add_argument(
        "--stdin", action="store_true", help=_("resources.data.parser.read_input_data_from_stdin")
    )
    import_parser.add_argument(
        "--format",
        choices=("jsonl", "json", "bundle"),
        default="jsonl",
        help=_(
            "resources.data.parser.input_format_for_one_resource_bundle_is_implied_for_import_bundle"
        ),
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=_("resources.data.parser.validate_input_without_committing"),
    )
    import_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=_("resources.data.parser.continue_processing_later_rows_after_failure"),
    )
    import_parser.add_argument(
        "--replace-existing",
        action="store_true",
        help=_(
            "resources.data.parser.for_bundle_imports_truncate_supported_data_before_restoring_bundle"
        ),
    )
    import_parser.add_argument(
        "--mode",
        choices=("create", "upsert"),
        default="create",
        help=_("resources.data.parser.import_mode_create_or_upsert"),
    )
    import_parser.add_argument(
        "--key",
        metavar="FIELD",
        help=_("resources.data.parser.upsert_natural_key_field"),
    )
    import_parser.add_argument(
        "--error-file", help=_("resources.data.parser.write_row_level_failures_to_jsonl_file")
    )
    import_parser.set_defaults(handler=make_sync_handler(handle_data_import_async))

    batch_update_parser = add_documented_parser(
        data_subparsers,
        "batch-update",
        help_content=HelpContent(
            summary=_("resources.data.parser.batch_update_one_resource_from_canonical_patch_rows"),
            description=(
                _(
                    "resources.data.parser.apply_patch_rows_to_one_resource_using_same_canonical_record_shape_used"
                )
                + " "
                + _(
                    "resources.data.parser.omitted_fields_stay_unchanged_explicit_null_clears_clearable_fields"
                )
            ),
            examples=(
                "lifeos data batch-update timelog --file timelog-patch.jsonl --format jsonl",
                "lifeos data batch-update person --stdin --format json",
                "lifeos data batch-update event --file event-patch.jsonl --format jsonl "
                "--dry-run --error-file event-errors.jsonl",
            ),
            notes=(
                _(
                    "resources.data.parser.batch_update_operates_on_stored_records_use_public_resource_commands_when_you"
                ),
                _(
                    "resources.data.parser.start_from_data_export_output_when_preparing_machine_generated_patch_rows"
                ),
            ),
        ),
    )
    batch_update_parser.add_argument("target", choices=DATA_RESOURCE_CHOICES)
    batch_update_parser.add_argument(
        "--file", help=_("resources.data.parser.read_patch_rows_from_file")
    )
    batch_update_parser.add_argument(
        "--stdin",
        action="store_true",
        help=_("resources.data.parser.read_patch_rows_from_stdin"),
    )
    batch_update_parser.add_argument("--format", choices=("jsonl", "json"), default="jsonl")
    batch_update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=_("resources.data.parser.validate_without_committing"),
    )
    batch_update_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=_("resources.data.parser.continue_processing_later_rows_after_failure"),
    )
    batch_update_parser.add_argument(
        "--error-file",
        help=_("resources.data.parser.write_row_level_failures_to_jsonl_file"),
    )
    batch_update_parser.set_defaults(handler=make_sync_handler(handle_data_batch_update_async))

    batch_delete_parser = add_documented_parser(
        data_subparsers,
        "batch-delete",
        help_content=HelpContent(
            summary=_("resources.data.parser.batch_delete_one_resource_by_identifiers"),
            description=(
                _(
                    "resources.data.parser.delete_multiple_rows_for_one_resource_using_repeated_ids_ids_file_or"
                )
            ),
            examples=(
                "lifeos data batch-delete task --id <task-id-1> --id <task-id-2>",
                "lifeos data batch-delete event --ids-file event-ids.txt",
                "lifeos data batch-delete timelog --file timelog-export.jsonl --format jsonl",
            ),
            notes=(
                _(
                    "resources.data.parser.use_this_command_for_file_driven_or_machine_generated_cleanup_across_many"
                ),
                _(
                    "resources.data.parser.use_resource_specific_delete_commands_when_you_want_narrower_human_guided_changes"
                ),
                _("common.messages.use_resource_batch_delete_for_inline_id_bulk_workflows"),
            ),
        ),
    )
    batch_delete_parser.add_argument("target", choices=DATA_RESOURCE_CHOICES)
    batch_delete_parser.add_argument(
        "--id",
        dest="record_ids",
        action="append",
        help=_("resources.data.parser.repeat_to_delete_one_or_more_record_identifiers"),
    )
    batch_delete_parser.add_argument(
        "--ids-file", help=_("resources.data.parser.read_one_uuid_per_line_from_file")
    )
    batch_delete_parser.add_argument(
        "--file", help=_("resources.data.parser.read_identifiers_or_resource_rows_from_file")
    )
    batch_delete_parser.add_argument(
        "--stdin",
        action="store_true",
        help=_("resources.data.parser.read_identifiers_from_stdin"),
    )
    batch_delete_parser.add_argument(
        "--format",
        choices=("plain", "jsonl", "json"),
        default="plain",
    )
    batch_delete_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=_("resources.data.parser.validate_without_committing"),
    )
    batch_delete_parser.add_argument(
        "--error-file",
        help=_("resources.data.parser.write_row_level_failures_to_jsonl_file"),
    )
    batch_delete_parser.set_defaults(handler=make_sync_handler(handle_data_batch_delete_async))
