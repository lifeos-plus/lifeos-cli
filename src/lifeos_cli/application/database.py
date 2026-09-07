"""Database workflows shared by CLI entrypoints."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Literal

from lifeos_cli.config import ConfigurationError
from lifeos_cli.db.maintenance import (
    DatabaseCheckReport,
    check_database,
    ping_database,
    upgrade_database,
)


async def ping_configured_database() -> None:
    """Ping the configured database."""
    await ping_database()


async def check_configured_database(*, repair: bool = False) -> DatabaseCheckReport:
    """Run operational checks against the configured database."""
    return await check_database(repair=repair)


def upgrade_configured_database() -> None:
    """Apply database migrations to the configured database."""
    upgrade_database()


def run_configured_database_subcommand_in_subprocess(
    *,
    subcommand: Literal["ping", "upgrade"],
) -> None:
    """Run one database CLI command in a fresh process after config changes.

    This keeps post-init database actions aligned with the newly written
    schema binding without mutating already-imported ORM metadata in-process.
    """
    failure_messages = {
        "ping": "Database connectivity check failed.",
        "upgrade": "Database migrations failed.",
    }
    executable = shutil.which("lifeos")
    command = (
        [executable, "db", subcommand]
        if executable is not None
        else [sys.executable, "-m", "lifeos_cli.cli", "db", subcommand]
    )
    result = subprocess.run(
        command,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or failure_messages[subcommand]
        raise ConfigurationError(message)
