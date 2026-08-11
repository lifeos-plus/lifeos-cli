"""Facade exports for habit-action service functions."""

from __future__ import annotations

from lifeos_cli.db.services.habit_mutations import (
    update_habit_action,
    update_habit_action_by_date,
)
from lifeos_cli.db.services.habit_queries import (
    count_habit_actions,
    get_habit_action,
    get_habit_action_model,
    list_habit_actions,
    list_habit_actions_in_range,
    list_habit_actions_with_total,
)
from lifeos_cli.db.services.habit_support import (
    DEFAULT_HABIT_ACTION_WINDOW_DAYS,
    HABIT_EDITABLE_DAYS,
    MAX_HABIT_ACTION_WINDOW_DAYS,
    VALID_HABIT_ACTION_STATUSES,
    HabitActionNotFoundError,
    HabitNotFoundError,
    HabitValidationError,
    InvalidHabitOperationError,
    validate_habit_action_status,
)

__all__ = [
    "DEFAULT_HABIT_ACTION_WINDOW_DAYS",
    "HABIT_EDITABLE_DAYS",
    "MAX_HABIT_ACTION_WINDOW_DAYS",
    "HabitActionNotFoundError",
    "HabitNotFoundError",
    "HabitValidationError",
    "InvalidHabitOperationError",
    "VALID_HABIT_ACTION_STATUSES",
    "count_habit_actions",
    "get_habit_action",
    "get_habit_action_model",
    "list_habit_actions",
    "list_habit_actions_in_range",
    "list_habit_actions_with_total",
    "update_habit_action",
    "update_habit_action_by_date",
    "validate_habit_action_status",
]
