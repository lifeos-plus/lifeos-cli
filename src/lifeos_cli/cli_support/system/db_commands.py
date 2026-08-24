"""Database maintenance CLI commands."""

from __future__ import annotations

import argparse

from lifeos_cli.application.database import (
    ping_configured_database,
    upgrade_configured_database,
)
from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.cli_support.runtime_utils import (
    make_sync_handler,
)
from lifeos_cli.i18n import cli_message as _


async def run_db_ping(_: argparse.Namespace) -> int:
    """Ping the configured database and print a success message."""
    await ping_configured_database()
    print("Database connection succeeded.")
    return 0


def run_db_upgrade(_: argparse.Namespace) -> int:
    """Apply database migrations and print a success message."""
    upgrade_configured_database()
    print("Database migrations are up to date.")
    return 0


def build_db_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    db_parser = add_documented_help_parser(
        subparsers,
        "db",
        help_content=HelpContent(
            summary=_("system.db_commands.run_database_maintenance_commands"),
            description=(
                _("system.db_commands.inspect_database_connectivity_and_apply_migrations")
                + "\n\n"
                + _(
                    "system.db_commands.these_commands_operate_on_database_configured_through_lifeos_init_config_file_or"
                )
            ),
            examples=(
                "lifeos db ping",
                "lifeos db upgrade",
            ),
            notes=(
                _(
                    "system.db_commands.use_ping_to_validate_current_connection_settings_without_changing_schema"
                ),
                _(
                    "system.db_commands.use_upgrade_when_configured_database_schema_needs_to_catch_up_with_code"
                ),
            ),
        ),
    )
    db_subparsers = db_parser.add_subparsers(
        dest="db_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )

    ping_parser = add_documented_parser(
        db_subparsers,
        "ping",
        help_content=HelpContent(
            summary=_("system.db_commands.check_database_connectivity"),
            description=_(
                "system.db_commands.open_database_connection_and_run_minimal_health_check_query"
            ),
            examples=("lifeos db ping",),
            notes=(
                _(
                    "system.db_commands.use_this_before_db_upgrade_when_you_first_need_to_confirm_target"
                ),
            ),
        ),
    )
    ping_parser.set_defaults(handler=make_sync_handler(run_db_ping))

    upgrade_parser = add_documented_parser(
        db_subparsers,
        "upgrade",
        help_content=HelpContent(
            summary=_("system.db_commands.apply_migrations"),
            description=_("system.db_commands.apply_alembic_migrations_to_configured_database"),
            examples=("lifeos db upgrade",),
            notes=(
                _(
                    "system.db_commands.this_updates_schema_state_in_database_it_does_not_rewrite_local_config"
                ),
                _(
                    "system.db_commands.use_db_ping_first_if_you_are_unsure_current_connection_settings_are"
                ),
            ),
        ),
    )
    upgrade_parser.set_defaults(handler=run_db_upgrade)
