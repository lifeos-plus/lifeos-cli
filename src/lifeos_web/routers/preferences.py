"""Preference endpoints for the local Web UI."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lifeos_cli.application.configuration import set_runtime_config_value
from lifeos_cli.config import (
    SUPPORTED_THEMES,
    SUPPORTED_WEIGHT_UNITS,
    ConfigurationError,
    PreferencesSettings,
    clear_config_cache,
    get_preferences_settings,
)
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import visions as vision_services
from lifeos_web.response_schemas.preferences import PreferenceResponse

router = APIRouter(prefix="/preferences", tags=["preferences"])

_VISIBLE_MODULES = [
    "visions",
    "habits",
    "planning",
    "timelog",
    "finance",
    "health",
    "insights",
    "calendar",
    "notes",
    "person",
    "settings",
]

_CONFIG_KEY_MAP = {
    "appearance.theme": "preferences.theme",
    "calendar.first_day_of_week": "preferences.calendar_first_day_of_week",
    "calendar.system": "preferences.calendar_system",
    "calendar.seven_year_anchor_date": "preferences.calendar_seven_year_anchor_date",
    "navigation.visible_modules": "preferences.navigation_visible_modules",
    "notes.card_min_collapsed_lines": "preferences.notes_card_min_collapsed_lines",
    "notes.export_planning.include_cycle_notes": (
        "preferences.notes_export_planning_include_cycle_notes"
    ),
    "notes.export_planning.include_task_notes": (
        "preferences.notes_export_planning_include_task_notes"
    ),
    "health.weight_unit": "preferences.weight_unit",
    "health.body_height_cm": "preferences.body_height_cm",
    "planning.show_habit_actions": "preferences.planning_show_habit_actions",
    "system.timezone": "preferences.timezone",
    "system.language": "preferences.language",
    "tasks.default_planning_preset": "preferences.tasks_default_planning_preset",
    "timeLog.auto_set_task_planning": "preferences.timelog_auto_set_task_planning",
    "todos.default_inbox_vision": "preferences.todos_default_inbox_vision",
    "visions.experience_rate_per_hour": "preferences.vision_experience_rate_per_hour",
}

_CONFIG_ENV_KEY_MAP = {
    "system.language": "LIFEOS_LANGUAGE",
    "system.timezone": "LIFEOS_TIMEZONE",
    "visions.experience_rate_per_hour": "LIFEOS_VISION_EXPERIENCE_RATE_PER_HOUR",
}

_STATIC_DEFAULTS: dict[str, Any] = {
    "dashboard.area_order": [],
}

_META: dict[str, dict[str, Any]] = {
    "appearance.theme": {
        "allowed_values": list(SUPPORTED_THEMES),
        "description": "LifeOS Web UI theme.",
        "module": "appearance",
    },
    "calendar.system": {
        "allowed_values": ["gregorian", "mayan_13_moon"],
        "description": "Calendar system used by schedule and task planning views.",
        "module": "calendar",
    },
    "calendar.first_day_of_week": {
        "allowed_values": [1, 2, 3, 4, 5, 6, 7],
        "description": "First weekday used in calendar views.",
        "module": "calendar",
    },
    "calendar.seven_year_anchor_date": {
        "description": "Anchor date used to derive seven-year calendar periods.",
        "module": "calendar",
    },
    "navigation.visible_modules": {
        "allowed_values": _VISIBLE_MODULES,
        "description": "Visible LifeOS modules in the navigation rail.",
        "module": "navigation",
    },
    "health.weight_unit": {
        "allowed_values": list(SUPPORTED_WEIGHT_UNITS),
        "description": "Preferred unit for displaying body weight.",
        "module": "health",
    },
    "health.body_height_cm": {
        "description": "Body height in centimeters used to derive BMI.",
        "module": "health",
    },
}

_VALUES: dict[str, Any] = dict(_STATIC_DEFAULTS)


class PreferenceUpdate(BaseModel):
    """Preference update payload."""

    value: Any
    module: str | None = None


def _extract_config_preference_value(preferences: PreferencesSettings, key: str) -> Any:
    if key == "appearance.theme":
        return preferences.theme
    if key == "calendar.first_day_of_week":
        return preferences.calendar_first_day_of_week
    if key == "calendar.system":
        return preferences.calendar_system
    if key == "calendar.seven_year_anchor_date":
        return preferences.calendar_seven_year_anchor_date
    if key == "navigation.visible_modules":
        return list(preferences.navigation_visible_modules)
    if key == "notes.card_min_collapsed_lines":
        return preferences.notes_card_min_collapsed_lines
    if key == "notes.export_planning.include_cycle_notes":
        return preferences.notes_export_planning_include_cycle_notes
    if key == "notes.export_planning.include_task_notes":
        return preferences.notes_export_planning_include_task_notes
    if key == "health.weight_unit":
        return preferences.weight_unit
    if key == "health.body_height_cm":
        return preferences.body_height_cm
    if key == "planning.show_habit_actions":
        return preferences.planning_show_habit_actions
    if key == "system.timezone":
        return preferences.timezone
    if key == "system.language":
        return preferences.language
    if key == "tasks.default_planning_preset":
        return preferences.tasks_default_planning_preset
    if key == "timeLog.auto_set_task_planning":
        return preferences.timelog_auto_set_task_planning
    if key == "todos.default_inbox_vision":
        return preferences.todos_default_inbox_vision
    if key == "visions.experience_rate_per_hour":
        return preferences.vision_experience_rate_per_hour
    return None


def _sync_effective_config_preference_to_file(key: str) -> Any:
    """Keep config-backed Web preferences aligned with CLI's effective runtime value."""
    config_key = _CONFIG_KEY_MAP[key]
    effective_value = _extract_config_preference_value(get_preferences_settings(), key)
    file_value = _extract_config_preference_value(
        PreferencesSettings.from_env(include_overrides=False),
        key,
    )
    if effective_value != file_value:
        set_runtime_config_value(
            key=config_key,
            value=_config_payload_to_string(effective_value),
            refresh_runtime=False,
        )
        effective_value = _extract_config_preference_value(get_preferences_settings(), key)
    return effective_value


def _set_process_config_override(key: str, value: Any) -> None:
    env_key = _CONFIG_ENV_KEY_MAP.get(key)
    if env_key is None:
        return
    if env_key in os.environ:
        os.environ[env_key] = _config_payload_to_string(value)
    clear_config_cache()


def _default_value(key: str) -> Any:
    if key in _CONFIG_KEY_MAP:
        return _sync_effective_config_preference_to_file(key)
    return _STATIC_DEFAULTS.get(key)


def _config_payload_to_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return ",".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _preference_response(key: str) -> dict[str, Any]:
    if key in _CONFIG_KEY_MAP:
        value = _sync_effective_config_preference_to_file(key)
    else:
        value = _VALUES.get(key, _STATIC_DEFAULTS.get(key))
    meta = {
        "default_value": _default_value(key),
        "module": key.split(".", 1)[0],
    }
    meta.update(_META.get(key, {}))
    return {"key": key, "value": value, "meta": meta}


async def _sync_config_preference_dependents(key: str) -> None:
    if key != "visions.experience_rate_per_hour":
        return
    async with db_session.session_scope() as session:
        await vision_services.sync_default_rate_vision_experience(session)


@router.get("/{key}", response_model=PreferenceResponse, response_model_exclude_unset=True)
async def get_preference(key: str) -> dict[str, Any]:
    """Return local Web preference values."""
    return _preference_response(key)


@router.put("/{key}", response_model=PreferenceResponse, response_model_exclude_unset=True)
async def set_preference(key: str, payload: PreferenceUpdate) -> dict[str, Any]:
    """Persist local Web preference values."""
    config_key = _CONFIG_KEY_MAP.get(key)
    if config_key is not None:
        try:
            set_runtime_config_value(
                key=config_key,
                value=_config_payload_to_string(payload.value),
                refresh_runtime=False,
            )
        except ConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _set_process_config_override(key, payload.value)
        await _sync_config_preference_dependents(key)
        response = _preference_response(key)
        if payload.module:
            response["meta"]["module"] = payload.module
        return response

    _VALUES[key] = payload.value
    response = _preference_response(key)
    if payload.module:
        response["meta"]["module"] = payload.module
    return response
