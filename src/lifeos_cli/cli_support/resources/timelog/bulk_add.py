"""Quick batch-add parsing helpers for timelog CLI workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from lifeos_cli.application.time_preferences import (
    to_preferred_timezone,
    to_storage_timezone,
)
from lifeos_cli.config import ConfigurationError

_RANGE_SEPARATOR_REGEX = re.compile(r"[~～\-–—﹣－˗‒﹘﹣⎯]")
_FULL_WIDTH_SPACE = re.compile(r"[\u3000]")
_FULL_WIDTH_COLON = re.compile(r"[：﹕︰﹕﹕]")
_FULL_WIDTH_HYPHEN = re.compile(r"[－﹣－﹘–—~～]")
_TIME_TOKEN_PATTERN = r"(?:\d{3,4}|\d{1,2}(?::\d{1,2})?)"
_MAX_BULK_TIMELOG_LINES = 500


@dataclass(frozen=True)
class BulkTimelogDraft:
    """One normalized timelog draft derived from quick-entry text."""

    line_number: int
    raw_text: str
    title: str
    start_time: datetime
    end_time: datetime
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _ParsedLine:
    type: str
    end_token: str
    description: str
    start_token: str | None = None


def _normalize_for_matching(line: str) -> str:
    return (
        _FULL_WIDTH_HYPHEN.sub(
            "-",
            _FULL_WIDTH_COLON.sub(
                ":",
                _FULL_WIDTH_SPACE.sub(" ", line).replace("\u00a0", " ").replace("\t", " ").strip(),
            ),
        )
        .replace("  ", " ")
        .strip()
    )


def _parse_time_token(token: str | None, *, field_name: str, line_number: int) -> int:
    if token is None:
        raise ConfigurationError(f"Line {line_number}: missing {field_name} time.")
    normalized = "".join(
        character for character in token if character.isdigit() or character == ":"
    )
    if not normalized:
        raise ConfigurationError(f"Line {line_number}: invalid {field_name} time {token!r}.")
    if ":" in normalized:
        hour_text, minute_text = normalized.split(":", 1)
        minute_text = minute_text or "0"
    elif len(normalized) <= 2:
        hour_text, minute_text = normalized, "0"
    elif len(normalized) == 3:
        hour_text, minute_text = normalized[:1], normalized[1:]
    elif len(normalized) == 4:
        hour_text, minute_text = normalized[:2], normalized[2:]
    else:
        raise ConfigurationError(f"Line {line_number}: invalid {field_name} time {token!r}.")
    try:
        hours = int(hour_text)
        minutes = int(minute_text)
    except ValueError as exc:
        raise ConfigurationError(
            f"Line {line_number}: invalid {field_name} time {token!r}."
        ) from exc
    if hours < 0 or minutes < 0 or minutes >= 60 or hours >= 24:
        raise ConfigurationError(f"Line {line_number}: invalid {field_name} time {token!r}.")
    return hours * 60 + minutes


def _extract_range_line(line: str) -> _ParsedLine | None:
    normalized = _RANGE_SEPARATOR_REGEX.sub("-", line)
    match = re.match(
        rf"^({_TIME_TOKEN_PATTERN})\s*-\s*({_TIME_TOKEN_PATTERN})\s+(.+)$",
        normalized,
    )
    if match is None:
        return None
    start_token, end_token, description = match.groups()
    return _ParsedLine(
        type="range",
        start_token=start_token,
        end_token=end_token,
        description=description.strip(),
    )


def _extract_end_only_line(line: str) -> _ParsedLine | None:
    match = re.match(rf"^({_TIME_TOKEN_PATTERN})(.*)$", line)
    if match is None:
        return None
    end_token, description = match.groups()
    normalized_description = description.strip()
    if not normalized_description:
        return None
    return _ParsedLine(
        type="end_only",
        end_token=end_token,
        description=normalized_description,
    )


def _resolve_time_on_or_after(reference: datetime, minutes_after_midnight: int) -> datetime:
    candidate = reference.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        minutes=minutes_after_midnight
    )
    while candidate < reference:
        candidate += timedelta(days=1)
    return candidate


def parse_bulk_timelog_text(
    raw_text: str,
    *,
    first_start_time: datetime,
) -> list[BulkTimelogDraft]:
    """Parse quick-entry text into normalized timelog drafts."""
    normalized_first_start_time = to_storage_timezone(first_start_time)
    initial_cursor = to_preferred_timezone(normalized_first_start_time)
    lines = [
        (line_number, line.replace("\r", "").replace("\t", " ").replace("\u00a0", " ").strip())
        for line_number, line in enumerate(raw_text.splitlines(), start=1)
    ]
    active_lines = [(line_number, line) for line_number, line in lines if line]
    if not active_lines:
        raise ConfigurationError("Bulk timelog input must contain at least one non-empty line.")
    if len(active_lines) > _MAX_BULK_TIMELOG_LINES:
        raise ConfigurationError(
            f"Bulk timelog input supports at most {_MAX_BULK_TIMELOG_LINES} non-empty lines."
        )

    cursor = initial_cursor
    drafts: list[BulkTimelogDraft] = []
    for line_number, raw_line in active_lines:
        normalized = _normalize_for_matching(raw_line)
        parsed = _extract_range_line(normalized) or _extract_end_only_line(normalized)
        if parsed is None:
            raise ConfigurationError(
                "Line "
                f"{line_number}: could not parse quick timelog entry {raw_line!r}. "
                "Use `HHMM Title` or `HH:MM-HH:MM Title`."
            )
        title = parsed.description.strip()
        if not title:
            raise ConfigurationError(f"Line {line_number}: timelog title must not be empty.")

        warnings: list[str] = []
        if parsed.type == "range":
            start_minutes = _parse_time_token(
                parsed.start_token,
                field_name="start",
                line_number=line_number,
            )
            start_time = _resolve_time_on_or_after(cursor, start_minutes)
            if start_time.date() != cursor.date():
                warnings.append("start rolled into a later day to stay after the previous entry")
        else:
            start_time = cursor

        end_minutes = _parse_time_token(parsed.end_token, field_name="end", line_number=line_number)
        # Align the end to the start cursor itself so a zero-length entry stays a
        # zero-minute record instead of rolling a full day into a 24h span.
        end_time = _resolve_time_on_or_after(start_time, end_minutes)
        if end_time.date() != start_time.date():
            warnings.append("end crossed midnight into the next day")

        drafts.append(
            BulkTimelogDraft(
                line_number=line_number,
                raw_text=raw_line,
                title=title,
                start_time=start_time,
                end_time=end_time,
                warnings=tuple(warnings),
            )
        )
        cursor = end_time
    return drafts
