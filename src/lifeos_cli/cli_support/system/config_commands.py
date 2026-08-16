"""Configuration CLI command definitions."""

from __future__ import annotations

import argparse

from lifeos_cli.application.configuration import SUPPORTED_CONFIG_KEYS
from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.json_output import add_json_output_argument
from lifeos_cli.cli_support.system.config_handlers import (
    handle_config_show,
    handle_config_update,
)
from lifeos_cli.i18n import cli_message as _


def build_config_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the config command tree."""
    config_parser = add_documented_help_parser(
        subparsers,
        "config",
        help_content=HelpContent(
            summary=_("system.config_commands.inspect_runtime_configuration"),
            description=(
                _(
                    "system.config_commands.inspect_effective_configuration_resolved_from_config_file_and_environment_variables"
                )
            ),
            examples=(
                "lifeos config show",
                "lifeos config show --show-secrets",
                "lifeos config update preferences.timezone America/Toronto",
                "lifeos config update preferences.theme night",
            ),
            notes=(
                _(
                    "system.config_commands.use_show_to_inspect_effective_values_after_config_file_and_env_resolution"
                ),
                _(
                    "system.config_commands.use_update_to_persist_supported_keys_without_re_running_full_init_flow"
                ),
                _(
                    "system.config_commands.use_update_to_persist_supported_keys_into_local_config_file"
                ),
                _(
                    "system.config_commands.environment_variables_still_override_config_file_values_at_runtime"
                ),
                _(
                    "system.config_commands.agents_should_inspect_preference_language_before_writing_human_authored_titles_descriptions_or"
                ),
            ),
        ),
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    show_parser = add_documented_parser(
        config_subparsers,
        "show",
        help_content=HelpContent(
            summary=_("system.config_commands.show_effective_configuration"),
            description=_(
                "system.config_commands.print_effective_config_values_used_by_current_process"
            ),
            examples=(
                "lifeos config show",
                "lifeos config show --show-secrets",
            ),
            notes=(
                _(
                    "system.config_commands.database_urls_hide_passwords_by_default_use_show_secrets_when_needed"
                ),
                _(
                    "system.config_commands.preferences_are_resolved_from_preferences_toml_table_and_optional_lifeos_overrides"
                ),
                _(
                    "system.config_commands.use_config_update_to_persist_one_supported_key_after_reviewing_current_values"
                ),
                _(
                    "system.config_commands.agents_should_use_effective_language_for_human_authored_payload_data_unless_human"
                ),
            ),
        ),
    )
    show_parser.add_argument(
        "--show-secrets",
        action="store_true",
        help=_("system.config_commands.print_sensitive_values_such_as_database_passwords_in_full"),
    )
    add_json_output_argument(show_parser)
    show_parser.set_defaults(handler=handle_config_show)

    update_parser = add_documented_parser(
        config_subparsers,
        "update",
        help_content=HelpContent(
            summary=_("system.config_commands.persist_one_config_value"),
            description=_(
                "system.config_commands.write_one_supported_config_key_to_local_config_file"
            ),
            examples=(
                "lifeos config update preferences.timezone America/Toronto",
                "lifeos config update database.echo true",
                "lifeos config update database.url "
                "sqlite+aiosqlite:///$HOME/.lifeos/work.db "
                "--show-secrets",
                "lifeos config update preferences.vision_experience_rate_per_hour 120",
                "lifeos config update preferences.theme night",
            ),
            notes=(
                _(
                    "system.config_commands.this_command_writes_config_file_not_environment_variables"
                ),
                _("system.config_commands.supported_keys_keys").format(
                    keys=", ".join(SUPPORTED_CONFIG_KEYS)
                ),
                _(
                    "system.config_commands.use_lifeos_init_for_first_time_bootstrap_or_when_changing_schema_binding"
                ),
                _(
                    "system.config_commands.use_lifeos_init_schema_name_to_change_database_schema_binding"
                ),
                _(
                    "system.config_commands.use_config_show_to_inspect_effective_values_after_environment_overrides"
                ),
            ),
        ),
    )
    update_parser.add_argument(
        "key", help=_("system.config_commands.supported_config_key_to_update")
    )
    update_parser.add_argument(
        "value", help=_("system.config_commands.new_value_to_persist_for_selected_key")
    )
    update_parser.add_argument(
        "--show-secrets",
        action="store_true",
        help=_(
            "system.config_commands.print_sensitive_values_such_as_database_passwords_in_full_after_writing"
        ),
    )
    update_parser.set_defaults(handler=handle_config_update)
