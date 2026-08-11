"""Helpers for applying user time preferences at runtime."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from lifeos_cli.config import get_preferences_settings


def apply_preferred_timezone(value: datetime) -> datetime:
    """Attach the configured timezone when a user datetime omits one."""
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value
    preferred_timezone = ZoneInfo(get_preferences_settings().timezone)
    localized = value.replace(tzinfo=preferred_timezone)
    round_trip = localized.astimezone(UTC).astimezone(preferred_timezone).replace(tzinfo=None)
    if round_trip != value:
        raise ValueError(
            f"Local datetime {value.isoformat()} does not exist in timezone "
            f"{preferred_timezone.key}"
        )
    return localized


def to_storage_timezone(value: datetime) -> datetime:
    """Interpret one user-facing datetime and convert it to UTC storage semantics."""
    return apply_preferred_timezone(value).astimezone(UTC)


def to_preferred_timezone(value: datetime) -> datetime:
    """Convert a stored timestamp to the preferred display timezone."""
    preferred_timezone = ZoneInfo(get_preferences_settings().timezone)
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(preferred_timezone)


def get_operational_date(value: datetime | None = None) -> date:
    """Return the configured local date after applying the day-start boundary."""
    if value is None:
        value = datetime.now(UTC)
    local_value = to_preferred_timezone(value)
    hour, minute = (int(part) for part in get_preferences_settings().day_starts_at.split(":"))
    day_start = time(hour=hour, minute=minute)
    local_clock = time(
        hour=local_value.hour,
        minute=local_value.minute,
        second=local_value.second,
        microsecond=local_value.microsecond,
    )
    if local_clock < day_start:
        return (local_value - timedelta(days=1)).date()
    return local_value.date()


def get_day_start_datetime(target_date: date) -> datetime:
    """Return the configured local day-start datetime for one local date."""
    preferences = get_preferences_settings()
    hour, minute = (int(part) for part in preferences.day_starts_at.split(":"))
    return datetime.combine(
        target_date,
        time(hour=hour, minute=minute),
        tzinfo=ZoneInfo(preferences.timezone),
    )


def get_utc_window_for_local_date(target_date: date) -> tuple[datetime, datetime]:
    """Return the UTC datetime window for one configured local operational day."""
    local_start = get_day_start_datetime(target_date)
    local_end = local_start + timedelta(days=1)
    return (
        local_start.astimezone(UTC),
        local_end.astimezone(UTC),
    )


def get_utc_window_for_local_date_range(
    start_date: date,
    end_date: date,
) -> tuple[datetime, datetime]:
    """Return the inclusive UTC datetime window for a local-date range."""
    range_start, _ = get_utc_window_for_local_date(start_date)
    _, range_end_exclusive = get_utc_window_for_local_date(end_date)
    return range_start, range_end_exclusive - timedelta(microseconds=1)


def get_utc_half_open_window_for_local_date_range(
    start_date: date,
    end_date: date,
) -> tuple[datetime, datetime]:
    """Return the half-open UTC datetime window for an inclusive local-date range."""
    range_start, _ = get_utc_window_for_local_date(start_date)
    _, range_end_exclusive = get_utc_window_for_local_date(end_date)
    return range_start, range_end_exclusive


def get_week_bounds(reference_date: date) -> tuple[date, date]:
    """Return the configured week start and end dates for one local date."""
    week_starts_on = get_preferences_settings().week_starts_on
    weekday = reference_date.weekday()
    if week_starts_on == "sunday":
        days_since_week_start = (weekday + 1) % 7
    else:
        days_since_week_start = weekday
    week_start = reference_date - timedelta(days=days_since_week_start)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end
