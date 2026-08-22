"""Runtime helpers for synchronous CLI entrypoints."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Coroutine
from functools import partial

from sqlalchemy.exc import OperationalError

from lifeos_cli.config import (
    ConfigurationError,
    DatabaseSettings,
    PreferencesSettings,
    clear_config_cache,
    get_database_settings,
)


def make_sync_handler(
    async_handler: Callable[[argparse.Namespace], Coroutine[object, object, int]],
) -> Callable[[argparse.Namespace], int]:
    """Adapt one async CLI handler to the synchronous argparse entrypoint."""

    metadata_target = async_handler
    while isinstance(metadata_target, partial):
        metadata_target = metadata_target.func

    def handler(args: argparse.Namespace) -> int:
        return int(asyncio.run(async_handler(args)))

    handler.__doc__ = getattr(metadata_target, "__doc__", None)
    handler.__module__ = getattr(metadata_target, "__module__", __name__)
    handler.__name__ = getattr(metadata_target, "__name__", "handler").removesuffix("_async")
    handler.__qualname__ = getattr(
        metadata_target,
        "__qualname__",
        handler.__name__,
    ).removesuffix("_async")
    return handler


def refresh_runtime_configuration() -> None:
    """Clear cached configuration and session state in the current process."""
    clear_config_cache()
    from lifeos_cli.db.session import clear_session_cache

    clear_session_cache()


def format_config_summary(
    database_settings: DatabaseSettings,
    preferences_settings: PreferencesSettings,
    *,
    show_secrets: bool = False,
) -> str:
    """Render effective config values for display."""
    lines = [
        f"Config file: {database_settings.config_file}",
        f"Database URL: {database_settings.render_database_url(show_secrets=show_secrets)}",
        f"Database echo: {'true' if database_settings.database_echo else 'false'}",
        f"Preference timezone: {preferences_settings.timezone}",
        f"Preference language: {preferences_settings.language}",
        f"Payload language for agent-authored records: {preferences_settings.language}",
        f"Preference day starts at: {preferences_settings.day_starts_at}",
        f"Preference week starts on: {preferences_settings.week_starts_on}",
        "Preference vision experience rate per hour: "
        f"{preferences_settings.vision_experience_rate_per_hour}",
        f"Preference theme: {preferences_settings.theme}",
        "Agent payload rule: use the preference language for human-authored titles, "
        "descriptions, and note content unless the human explicitly asks for another language.",
    ]
    if database_settings.database_schema is not None:
        lines.insert(2, f"Database schema: {database_settings.database_schema}")
    return "\n".join(lines)


def print_database_runtime_error(exc: BaseException) -> int:
    """Render actionable database configuration or connectivity failures."""
    if isinstance(exc, ConfigurationError):
        print(str(exc), file=sys.stderr)
        return 1

    settings = get_database_settings()
    print("Database operation failed.", file=sys.stderr)
    print(
        f"Configured database URL: {settings.render_database_url(show_secrets=False)}",
        file=sys.stderr,
    )
    if settings.database_schema is not None:
        print(f"Configured schema: {settings.database_schema}", file=sys.stderr)
    guidance = None
    if isinstance(exc, OperationalError):
        details = str(exc).lower()
        policy = settings.backend_policy
        if policy is not None:
            guidance = policy.runtime_error_guidance(details)
    if guidance is not None:
        print(guidance, file=sys.stderr)
    print("Run `lifeos init` to create or update local configuration.", file=sys.stderr)
    print(
        "Then run `lifeos db ping` to verify connectivity and `lifeos db upgrade` to apply "
        "migrations.",
        file=sys.stderr,
    )
    print(f"Error type: {type(exc).__name__}", file=sys.stderr)
    print(
        "Original error details are suppressed to avoid leaking connection details.",
        file=sys.stderr,
    )
    return 1
