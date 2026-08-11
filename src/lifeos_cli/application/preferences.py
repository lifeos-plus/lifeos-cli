"""Typed accessors for persisted user preferences shared by backend logic.

Backend services read user preferences through these accessors instead of
requiring each consumption point to resolve ``get_preferences_settings()``
and pass individual preference values into service calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lifeos_cli.config import get_preferences_settings


@dataclass(frozen=True)
class CalendarPreferences:
    """Calendar-related user preferences persisted in the local config."""

    system: str
    first_day_of_week: int
    seven_year_anchor_date: date


def get_calendar_preferences() -> CalendarPreferences:
    """Return the persisted calendar preferences for the current user."""
    preferences = get_preferences_settings()
    return CalendarPreferences(
        system=preferences.calendar_system,
        first_day_of_week=preferences.calendar_first_day_of_week,
        seven_year_anchor_date=date.fromisoformat(preferences.calendar_seven_year_anchor_date),
    )
