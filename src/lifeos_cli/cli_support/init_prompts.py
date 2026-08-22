"""Interactive prompts for initialization commands."""

from __future__ import annotations

import getpass
from collections.abc import Callable

from lifeos_cli.cli_support.handler_utils import write_cli_error
from lifeos_cli.config import (
    ConfigurationError,
)


def prompt_text(label: str, *, default: str | None = None) -> str:
    """Prompt for a text value."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ConfigurationError(f"{label} is required")


def prompt_validated_text(
    label: str,
    default: str | None = None,
    *,
    validator: Callable[[str], str],
) -> str:
    """Prompt until one validator accepts the entered text."""
    while True:
        candidate = prompt_text(label, default=default)
        try:
            return validator(candidate)
        except ConfigurationError as exc:
            write_cli_error(exc)
            default = None


def prompt_secret_text(label: str, *, default: str | None = None) -> str:
    """Prompt for a secret value without echoing it to the terminal."""
    suffix = f" [default: {default}]" if default else ""
    value = getpass.getpass(f"{label} (hidden input){suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ConfigurationError(f"{label} is required")


def prompt_validated_secret_text(
    label: str,
    default: str | None = None,
    *,
    validator: Callable[[str], str],
) -> str:
    """Prompt until one validator accepts hidden secret input."""
    while True:
        candidate = prompt_secret_text(label, default=default)
        try:
            return validator(candidate)
        except ConfigurationError as exc:
            write_cli_error(exc)
            default = None


def prompt_bool(label: str, default: bool) -> bool:
    """Prompt for a yes/no value."""
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} [{suffix}]: ").strip().lower()
    if not value:
        return default
    if value in {"y", "yes"}:
        return True
    if value in {"n", "no"}:
        return False
    raise ConfigurationError(f"{label} must be answered with yes or no")
