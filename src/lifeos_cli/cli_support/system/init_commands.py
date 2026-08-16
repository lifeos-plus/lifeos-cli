"""Initialization CLI command definitions."""

from __future__ import annotations

import argparse

from lifeos_cli.cli_support.help_utils import HelpContent, add_documented_parser
from lifeos_cli.cli_support.system.config_handlers import handle_init
from lifeos_cli.i18n import cli_message as _


def build_init_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the init command."""
    init_parser = add_documented_parser(
        subparsers,
        "init",
        help_content=HelpContent(
            summary=_("system.init_commands.initialize_local_configuration"),
            description=(
                _(
                    "system.init_commands.create_or_update_local_lifeos_config_file_and_verify_that_database_is"
                )
                + "\n\n"
                + _(
                    "system.init_commands.this_command_is_recommended_first_step_after_installing_lifeos_cli"
                )
            ),
            examples=(
                "lifeos init",
                "lifeos init --database-url sqlite+aiosqlite:///$HOME/.lifeos/lifeos.db",
                "lifeos init --non-interactive --database-url "
                "postgresql+psycopg://<db-user>:<db-password>@localhost:5432/lifeos "
                "--schema lifeos --timezone America/Toronto --language zh-Hans --skip-migrate",
            ),
            notes=(
                _(
                    "system.init_commands.configuration_is_written_to_config_lifeos_config_toml_by_default"
                ),
                _("system.init_commands.database_url_defaults_to_local_sqlite_file_when_omitted"),
                _(
                    "system.init_commands.environment_variables_still_override_config_file_values_at_runtime"
                ),
                _(
                    "system.init_commands.database_credentials_may_be_stored_in_plain_text_in_config_file"
                ),
                _(
                    "system.init_commands.preference_values_are_also_stored_in_config_file_under_preferences"
                ),
                _(
                    "system.init_commands.use_config_update_for_supported_follow_up_edits_when_you_do_not"
                ),
                _(
                    "system.init_commands.interactive_init_confirms_language_preference_because_agents_should_use_it_for_human"
                ),
                _(
                    "system.init_commands.re_run_lifeos_init_at_any_time_to_update_stored_preferences"
                ),
            ),
        ),
    )
    init_parser.add_argument(
        "--database-url",
        help=_("system.init_commands.database_connection_url_to_persist_in_config_file"),
    )
    init_parser.add_argument(
        "--schema",
        default=None,
        help=_("system.init_commands.optional_schema_name_for_schema_capable_backends"),
    )
    init_parser.add_argument(
        "--echo",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=_("system.init_commands.enable_sqlalchemy_sql_echo_logging_in_config_file"),
    )
    init_parser.add_argument(
        "--timezone",
        default=None,
        help=_(
            "system.init_commands.default_iana_timezone_for_local_day_boundaries_and_time_based_summaries"
        ),
    )
    init_parser.add_argument(
        "--language",
        default=None,
        help=_("system.init_commands.preferred_language_tag_for_example_en_en_ca_or_zh_hans"),
    )
    init_parser.add_argument(
        "--day-starts-at",
        default=None,
        help=_(
            "system.init_commands.local_day_boundary_in_hh_mm_used_for_future_time_based_grouping"
        ),
    )
    init_parser.add_argument(
        "--week-starts-on",
        default=None,
        help=_("system.init_commands.preferred_first_day_of_week_monday_or_sunday"),
    )
    init_parser.add_argument(
        "--vision-experience-rate-per-hour",
        type=int,
        default=None,
        help=_(
            "system.init_commands.default_vision_experience_points_gained_per_hour_of_actual_effort"
        ),
    )
    init_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=_(
            "system.init_commands.do_not_prompt_for_missing_values_require_flags_or_existing_config_values"
        ),
    )
    init_parser.add_argument(
        "--skip-ping",
        action="store_true",
        help=_("system.init_commands.do_not_check_database_connectivity_after_writing_config_file"),
    )
    init_parser.add_argument(
        "--skip-migrate",
        action="store_true",
        help=_("system.init_commands.do_not_run_database_migrations_after_writing_config_file"),
    )
    init_parser.set_defaults(handler=handle_init)
