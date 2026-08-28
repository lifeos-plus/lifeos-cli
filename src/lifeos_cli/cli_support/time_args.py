"""Shared CLI helpers for date and time query arguments."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime, time

from lifeos_cli.application.datetime_utils import parse_iso_datetime_input
from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.db.services.validation_utils import DATE_RANGE_TOGETHER_MESSAGE

_DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class DateArgumentError(ValueError):
    """Raised when CLI date arguments do not form a valid interval."""


@dataclass(frozen=True)
class ResolvedDateSelection:
    """Normalized local-date selection from CLI flags."""

    date_values: tuple[date, ...]
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class ResolvedDateTimeQuery:
    """Normalized date-or-time query filters for list commands."""

    date_values: tuple[date, ...]
    start_date: date | None
    end_date: date | None
    window_start: datetime | None
    window_end: datetime | None


def parse_date_value(value: str) -> date:
    """Parse one ISO local date value."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_optional_date_value(value: str | None) -> date | None:
    """Parse one optional ISO local date value."""
    if value is None:
        return None
    return date.fromisoformat(value)


def parse_datetime_or_date_value(value: str) -> datetime | date:
    """Parse one ISO datetime or date value for query filters."""
    if _DATE_ONLY_PATTERN.fullmatch(value):
        return parse_date_value(value)
    return parse_user_datetime_value(value)


def parse_user_datetime_value(value: str) -> datetime:
    """Parse one ISO datetime value for user-facing write arguments."""
    try:
        return parse_iso_datetime_input(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def resolve_date_selection_arguments(
    *,
    date_values: list[date] | None,
    start_date: date | None = None,
    end_date: date | None = None,
    conflict_message: str = "Use either --date or --start-date/--end-date, not both.",
    incomplete_message: str = DATE_RANGE_TOGETHER_MESSAGE,
    explicit_inverted_message: str = "The --end-date value must be on or after --start-date.",
) -> ResolvedDateSelection:
    """Resolve repeated discrete dates or one explicit inclusive date range."""
    selected_dates = tuple(dict.fromkeys(date_values or ()))
    if selected_dates and (start_date is not None or end_date is not None):
        raise DateArgumentError(conflict_message)
    if start_date is not None or end_date is not None:
        if start_date is None or end_date is None:
            raise DateArgumentError(incomplete_message)
        if end_date < start_date:
            raise DateArgumentError(explicit_inverted_message)
        return ResolvedDateSelection(date_values=(), start_date=start_date, end_date=end_date)
    return ResolvedDateSelection(date_values=selected_dates, start_date=None, end_date=None)


def resolve_required_date_interval_arguments(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    empty_message: str = DATE_RANGE_TOGETHER_MESSAGE,
) -> tuple[date, date]:
    """Resolve one required explicit inclusive date interval from CLI flags."""
    selection = resolve_date_selection_arguments(
        date_values=None,
        start_date=start_date,
        end_date=end_date,
    )
    if selection.start_date is None or selection.end_date is None:
        raise DateArgumentError(empty_message)
    return selection.start_date, selection.end_date


def normalize_query_datetime_bound(
    value: datetime | date | None,
    *,
    is_end: bool,
) -> datetime | None:
    """Normalize one CLI query datetime bound into UTC."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        local_time = time.max if is_end else time.min
        value = datetime.combine(value, local_time)
    return to_storage_timezone(value)


def resolve_exclusive_date_or_datetime_query(
    *,
    date_values: list[date] | None,
    start_date: date | None = None,
    end_date: date | None = None,
    window_start: datetime | date | None,
    window_end: datetime | date | None,
    conflict_message: str = (
        "Use either --date, --start-date/--end-date, or --start-time/--end-time."
    ),
) -> ResolvedDateTimeQuery:
    """Resolve one query scope that may be either a date interval or a datetime window."""
    selection = resolve_date_selection_arguments(
        date_values=date_values,
        start_date=start_date,
        end_date=end_date,
    )
    normalized_window_start = normalize_query_datetime_bound(window_start, is_end=False)
    normalized_window_end = normalize_query_datetime_bound(window_end, is_end=True)
    has_date_selection = bool(selection.date_values) or (
        selection.start_date is not None or selection.end_date is not None
    )
    if has_date_selection and (
        normalized_window_start is not None or normalized_window_end is not None
    ):
        raise DateArgumentError(conflict_message)
    return ResolvedDateTimeQuery(
        date_values=selection.date_values,
        start_date=selection.start_date,
        end_date=selection.end_date,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
    )
