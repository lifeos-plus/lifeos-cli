"""Opt-in JSON output for CLI read commands.

The default CLI output stays human-friendly (tab-separated summary rows and
labeled detail lines). ``--json`` is an explicit opt-in for agents and other
automation callers that need stable, self-describing structured output.

Serialization follows the same conventions as the Web API where they overlap:
UUIDs become strings, datetimes become explicit UTC ISO strings, and enum
values become their scalar values. Decimal amounts are rendered as strings so
precision is never lost to floating-point coercion.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from lifeos_cli.application.datetime_utils import format_utc_iso
from lifeos_cli.i18n import cli_message as _


def to_jsonable(value: Any) -> Any:
    """Convert LifeOS records and scalar values into JSON-compatible values."""
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: to_jsonable(item) for key, item in vars(value).items() if not key.startswith("_")
        }
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return format_utc_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def print_json_items(items: Sequence[Any], *, total_count: int | None = None) -> None:
    """Print one JSON array with one object per record.

    When ``total_count`` is provided the payload becomes
    ``{"items": [...], "total_count": N}`` so list commands that support
    ``--count`` keep a machine-readable total.
    """
    payload: Any = [to_jsonable(item) for item in items]
    if total_count is not None:
        payload = {"items": payload, "total_count": total_count}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_json_payload(value: Any) -> None:
    """Print one JSON object for a single record or detail view."""
    print(json.dumps(to_jsonable(value), ensure_ascii=False, indent=2))


def add_json_output_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared opt-in ``--json`` flag to a read command parser."""
    parser.add_argument(
        "--json",
        action="store_true",
        help=_("common.parser.output_as_json"),
    )
