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
from decimal import Decimal
from typing import Any

from lifeos_cli.application.serialization import to_jsonable
from lifeos_cli.i18n import cli_message as _


def _json_default(value: Any) -> Any:
    """Render values the shared serializer intentionally leaves untouched."""
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def print_json_items(items: Sequence[Any], *, total_count: int | None = None) -> None:
    """Print one JSON array with one object per record.

    When ``total_count`` is provided the payload becomes
    ``{"items": [...], "total_count": N}`` so list commands that support
    ``--count`` keep a machine-readable total.
    """
    payload: Any = [to_jsonable(item) for item in items]
    if total_count is not None:
        payload = {"items": payload, "total_count": total_count}
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


def print_json_payload(value: Any) -> None:
    """Print one JSON object for a single record or detail view."""
    print(json.dumps(to_jsonable(value), ensure_ascii=False, indent=2, default=_json_default))


def add_json_output_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared opt-in ``--json`` flag to a read command parser."""
    parser.add_argument(
        "--json",
        action="store_true",
        help=_("common.parser.output_as_json"),
    )
