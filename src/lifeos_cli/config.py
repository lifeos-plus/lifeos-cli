"""Runtime configuration for lifeos_cli."""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from lifeos_cli.db.backend_policy import (
    SUPPORTED_DATABASE_DRIVERS,
    DatabaseBackendPolicy,
    backend_policy_for_drivername,
    supported_database_driver_examples,
)

DEFAULT_DATABASE_SCHEMA = "lifeos"
DEFAULT_CONFIG_PATH = Path.home() / ".lifeos" / "config.toml"
DEFAULT_SQLITE_DATABASE_FILENAME = "lifeos.db"
DEFAULT_LANGUAGE = "en"
DEFAULT_DAY_STARTS_AT = "00:00"
DEFAULT_WEEK_STARTS_ON = "monday"
DEFAULT_VISION_EXPERIENCE_RATE_PER_HOUR = 60
DEFAULT_THEME = "system"
DEFAULT_CALENDAR_FIRST_DAY_OF_WEEK = 1
DEFAULT_CALENDAR_SYSTEM = "gregorian"
DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_DATE = "2025-07-26"
DEFAULT_NAVIGATION_VISIBLE_MODULES = (
    "visions",
    "habits",
    "planning",
    "timelog",
    "finance",
    "insights",
    "calendar",
    "notes",
    "person",
    "settings",
)
DEFAULT_WEIGHT_UNIT = "kg"
DEFAULT_NOTES_CARD_MIN_COLLAPSED_LINES = 5
DEFAULT_NOTES_EXPORT_PLANNING_INCLUDE_CYCLE_NOTES = False
DEFAULT_NOTES_EXPORT_PLANNING_INCLUDE_TASK_NOTES = True
DEFAULT_PLANNING_SHOW_HABIT_ACTIONS = True
DEFAULT_TASKS_DEFAULT_PLANNING_PRESET = "none"
DEFAULT_TIMELOG_AUTO_SET_TASK_PLANNING = False
DEFAULT_TODOS_DEFAULT_INBOX_VISION = None
DEFAULT_BODY_HEIGHT_CM: float | None = None
SUPPORTED_WEIGHT_UNITS = ("kg", "jin", "lb")
MAX_VISION_EXPERIENCE_RATE_PER_HOUR = 3600
SUPPORTED_THEMES = (
    "system",
    "fresh",
    "cupcake",
    "bumblebee",
    "emerald",
    "corporate",
    "synthwave",
    "retro",
    "cyberpunk",
    "valentine",
    "halloween",
    "garden",
    "forest",
    "aqua",
    "lofi",
    "pastel",
    "fantasy",
    "wireframe",
    "luxury",
    "dracula",
    "cmyk",
    "autumn",
    "business",
    "acid",
    "lemonade",
    "night",
    "coffee",
    "winter",
)
SUPPORTED_CALENDAR_SYSTEMS = ("gregorian", "mayan_13_moon")
SUPPORTED_NAVIGATION_MODULES = DEFAULT_NAVIGATION_VISIBLE_MODULES
SUPPORTED_NOTES_CARD_MIN_COLLAPSED_LINES = (3, 5, 7, 9, 11, 13, 15)
SUPPORTED_TASKS_DEFAULT_PLANNING_PRESETS = ("none", "today", "this_week", "this_month")
_SCHEMA_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LANGUAGE_TAG_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_DAY_STARTS_AT_PATTERN = re.compile(r"^(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d)$")
_WEEK_STARTS_ON_VALUES = {"monday", "sunday"}
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class ConfigurationError(RuntimeError):
    """Raised when runtime configuration is missing or invalid."""


def _parse_database_url(database_url: str) -> tuple[str, URL]:
    normalized = database_url.strip()
    if not normalized:
        raise ConfigurationError("Database URL is required.")
    try:
        parsed = make_url(normalized)
    except ArgumentError as exc:
        raise ConfigurationError(f"Database URL is invalid: {exc}") from exc
    return normalized, parsed


def database_policy(database_url: str) -> DatabaseBackendPolicy:
    """Return the backend policy for one validated database URL."""
    _, parsed = _parse_database_url(database_url)
    return backend_policy_for_drivername(parsed.drivername)


def ensure_database_driver_available(database_url: str) -> None:
    """Ensure the configured SQLAlchemy driver dependencies are installed."""
    policy = database_policy(database_url)
    if policy.required_driver_module is None:
        return
    try:
        import_module(policy.required_driver_module)
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            policy.missing_driver_message or "Database driver is missing."
        ) from exc


def _sqlite_database_file_path(parsed: URL) -> Path | None:
    """Return the on-disk SQLite database path when one file is configured."""
    if not backend_policy_for_drivername(parsed.drivername).supports_local_file_storage:
        return None
    database_name = parsed.database
    if database_name is None or database_name in {"", ":memory:"}:
        return None
    if database_name.startswith("file:") or parsed.query.get("uri") in {"1", "true"}:
        return None
    return Path(database_name).expanduser()


def _normalize_sqlite_database_url(parsed: URL) -> str:
    """Render one SQLite URL with a normalized filesystem path when applicable."""
    database_path = _sqlite_database_file_path(parsed)
    if database_path is None:
        return parsed.render_as_string(hide_password=False)
    return parsed.set(database=str(database_path)).render_as_string(hide_password=False)


def ensure_database_url_storage_ready(database_url: str) -> None:
    """Create local storage prerequisites for file-backed database URLs."""
    _, parsed = _parse_database_url(database_url)
    database_path = _sqlite_database_file_path(parsed)
    if database_path is None:
        return
    database_path.parent.mkdir(parents=True, exist_ok=True)


def normalize_database_schema(
    *,
    database_url: str | None,
    configured_schema: str | None,
    explicit: bool = False,
) -> str | None:
    """Normalize one schema value against the target database URL."""
    if database_url is None:
        return validate_database_schema_name(configured_schema or DEFAULT_DATABASE_SCHEMA)
    if database_policy(database_url).supports_schema:
        return validate_database_schema_name(configured_schema or DEFAULT_DATABASE_SCHEMA)
    if explicit and configured_schema is not None:
        raise ConfigurationError(
            "Database schema is only supported for `postgresql+psycopg://` URLs."
        )
    return None


def validate_database_url(database_url: str) -> str:
    """Validate one supported SQLAlchemy database URL and return the normalized value."""
    normalized, parsed = _parse_database_url(database_url)
    if parsed.drivername not in SUPPORTED_DATABASE_DRIVERS:
        raise ConfigurationError(
            "Database URL must use one of the supported SQLAlchemy drivers: "
            f"{supported_database_driver_examples()}."
        )
    policy = backend_policy_for_drivername(parsed.drivername)
    if policy.backend_name == "postgresql" and (
        parsed.database is None or not parsed.database.strip()
    ):
        raise ConfigurationError("Database URL must include a PostgreSQL database name.")
    if policy.supports_local_file_storage:
        return _normalize_sqlite_database_url(parsed)
    return normalized


def validate_database_schema_name(schema_name: str) -> str:
    """Validate a PostgreSQL schema identifier and return the normalized value."""
    normalized = schema_name.strip()
    if not _SCHEMA_NAME_PATTERN.match(normalized):
        raise ConfigurationError(
            "Database schema must start with a letter or underscore and contain only "
            "letters, numbers, and underscores. Use `lifeos_dev` instead of `lifeos-dev`."
        )
    return normalized


def detect_default_timezone(env: Mapping[str, str] | None = None) -> str:
    """Return a stable default timezone name for local preferences."""
    source = env or os.environ
    explicit_timezone = source.get("TZ")
    if explicit_timezone:
        try:
            return validate_timezone_name(explicit_timezone)
        except ConfigurationError:
            pass

    local_timezone = datetime.now().astimezone().tzinfo
    local_key = getattr(local_timezone, "key", None)
    if isinstance(local_key, str):
        try:
            return validate_timezone_name(local_key)
        except ConfigurationError:
            pass

    return "UTC"


def validate_timezone_name(timezone_name: str) -> str:
    """Validate an IANA timezone name and return the normalized value."""
    normalized = timezone_name.strip()
    if not normalized:
        raise ConfigurationError("Preference `timezone` is required.")
    try:
        ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(
            f"Preference `timezone` must be a valid IANA timezone name, got {normalized!r}."
        ) from exc
    return normalized


def _normalize_language_value(language: str) -> str:
    normalized = language.strip()
    if not normalized:
        raise ConfigurationError("Preference `language` is required.")
    normalized = normalized.split(".", maxsplit=1)[0].replace("_", "-")
    if normalized in {"C", "POSIX"}:
        return DEFAULT_LANGUAGE
    return normalized


def validate_language(language: str) -> str:
    """Validate a language tag used for user-facing preferences."""
    normalized = _normalize_language_value(language)
    if normalized.lower() == "auto":
        return "auto"
    if not _LANGUAGE_TAG_PATTERN.match(normalized):
        raise ConfigurationError(
            "Preference `language` must be `auto` or a valid language tag such as "
            "`en`, `en-CA`, or `zh-Hans`."
        )
    return normalized


def detect_default_language(env: Mapping[str, str] | None = None) -> str:
    """Return a stable default language value for preferences."""
    source = env or os.environ
    for key in ("LC_ALL", "LANG"):
        candidate = source.get(key)
        if candidate:
            try:
                return validate_language(candidate)
            except ConfigurationError:
                continue
    return DEFAULT_LANGUAGE


def validate_day_starts_at(value: str) -> str:
    """Validate the local day boundary used for grouping time-based records."""
    normalized = value.strip()
    if not _DAY_STARTS_AT_PATTERN.match(normalized):
        raise ConfigurationError(
            "Preference `day_starts_at` must use 24-hour `HH:MM` format, for example `04:00`."
        )
    return normalized


def validate_week_starts_on(value: str) -> str:
    """Validate the preferred first day of the week."""
    normalized = value.strip().lower()
    if normalized not in _WEEK_STARTS_ON_VALUES:
        supported = ", ".join(sorted(_WEEK_STARTS_ON_VALUES))
        raise ConfigurationError(f"Preference `week_starts_on` must be one of: {supported}.")
    return normalized


def _validate_int_preference(value: int | str, *, field_name: str) -> int:
    """Validate an integer preference value, rejecting booleans and non-integers."""
    if isinstance(value, bool):
        raise ConfigurationError(f"Preference `{field_name}` must be an integer.")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Preference `{field_name}` must be an integer.") from exc
    return normalized


def validate_vision_experience_rate_per_hour(value: int | str) -> int:
    """Validate the default vision experience rate preference."""
    normalized = _validate_int_preference(
        value,
        field_name="vision_experience_rate_per_hour",
    )
    if normalized < 1 or normalized > MAX_VISION_EXPERIENCE_RATE_PER_HOUR:
        raise ConfigurationError(
            "Preference `vision_experience_rate_per_hour` must be between "
            f"1 and {MAX_VISION_EXPERIENCE_RATE_PER_HOUR}."
        )
    return normalized


def validate_theme(value: str) -> str:
    """Validate the preferred Web UI theme."""
    normalized = value.strip()
    if normalized not in SUPPORTED_THEMES:
        supported = ", ".join(SUPPORTED_THEMES)
        raise ConfigurationError(f"Preference `theme` must be one of: {supported}.")
    return normalized


def _parse_string_list(value: object, *, field_name: str) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return []
        return [item.strip() for item in normalized.split(",") if item.strip()]
    if isinstance(value, list | tuple):
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ConfigurationError(f"Preference `{field_name}` must contain strings.")
            items.append(item.strip())
        return [item for item in items if item]
    raise ConfigurationError(f"Preference `{field_name}` must be a list of strings.")


def validate_calendar_first_day_of_week(value: int | str) -> int:
    """Validate the preferred first day used by Web calendar views."""
    normalized = _validate_int_preference(
        value,
        field_name="calendar_first_day_of_week",
    )
    if normalized < 1 or normalized > 7:
        raise ConfigurationError("Preference `calendar_first_day_of_week` must be between 1 and 7.")
    return normalized


def validate_calendar_system(value: str) -> str:
    """Validate the preferred Web calendar system."""
    normalized = value.strip()
    if normalized not in SUPPORTED_CALENDAR_SYSTEMS:
        supported = ", ".join(SUPPORTED_CALENDAR_SYSTEMS)
        raise ConfigurationError(f"Preference `calendar_system` must be one of: {supported}.")
    return normalized


def validate_calendar_seven_year_anchor_date(value: str) -> str:
    """Validate the date used to anchor seven-year calendar periods."""
    normalized = value.strip()
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise ConfigurationError(
            "Preference `calendar_seven_year_anchor_date` must be a YYYY-MM-DD date."
        ) from exc


def validate_navigation_visible_modules(value: object) -> tuple[str, ...]:
    """Validate the Web navigation module visibility preference."""
    modules = _parse_string_list(value, field_name="navigation_visible_modules")
    modules = ["person" if module == "persons" else module for module in modules]
    unsupported = [module for module in modules if module not in SUPPORTED_NAVIGATION_MODULES]
    if unsupported:
        supported = ", ".join(SUPPORTED_NAVIGATION_MODULES)
        raise ConfigurationError(
            "Preference `navigation_visible_modules` contains unsupported modules: "
            f"{', '.join(unsupported)}. Supported modules: {supported}."
        )
    return tuple(dict.fromkeys(modules))


def validate_notes_card_min_collapsed_lines(value: int | str) -> int:
    """Validate the Web note card collapsed preview size."""
    normalized = _validate_int_preference(
        value,
        field_name="notes_card_min_collapsed_lines",
    )
    if normalized not in SUPPORTED_NOTES_CARD_MIN_COLLAPSED_LINES:
        supported = ", ".join(str(item) for item in SUPPORTED_NOTES_CARD_MIN_COLLAPSED_LINES)
        raise ConfigurationError(
            f"Preference `notes_card_min_collapsed_lines` must be one of: {supported}."
        )
    return normalized


def validate_tasks_default_planning_preset(value: str) -> str:
    """Validate the default planning preset for new Web tasks."""
    normalized = value.strip()
    if normalized not in SUPPORTED_TASKS_DEFAULT_PLANNING_PRESETS:
        supported = ", ".join(SUPPORTED_TASKS_DEFAULT_PLANNING_PRESETS)
        raise ConfigurationError(
            f"Preference `tasks_default_planning_preset` must be one of: {supported}."
        )
    return normalized


def validate_todos_default_inbox_vision(value: str | None) -> str | None:
    """Validate the optional default inbox vision identifier used by Web planning."""
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not _UUID_PATTERN.match(normalized):
        raise ConfigurationError("Preference `todos_default_inbox_vision` must be a UUID when set.")
    return normalized.lower()


def validate_weight_unit(value: str) -> str:
    """Validate the preferred display unit for body weight."""
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_WEIGHT_UNITS:
        supported = ", ".join(SUPPORTED_WEIGHT_UNITS)
        raise ConfigurationError(f"Preference `weight_unit` must be one of: {supported}.")
    return normalized


def validate_body_height_cm(value: object) -> float | None:
    """Validate the optional body height used to derive BMI."""
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            height = float(normalized)
        except ValueError as exc:
            raise ConfigurationError(
                "Preference `body_height_cm` must be a number in centimeters when set."
            ) from exc
    elif isinstance(value, (int, float)):
        height = float(value)
    else:
        raise ConfigurationError(
            "Preference `body_height_cm` must be a number in centimeters when set."
        )
    if height < 50 or height > 300:
        raise ConfigurationError("Preference `body_height_cm` must be between 50 and 300.")
    return round(height, 1)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def parse_boolean_value(value: str, *, field_name: str) -> bool:
    """Parse a strict boolean string used by explicit CLI write commands."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{field_name} must be one of: true, false, yes, no, on, off, 1, 0.")


def _serialize_toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _serialize_toml_string_list(values: tuple[str, ...]) -> str:
    return f"[{', '.join(_serialize_toml_string(value) for value in values)}]"


def _render_database_table(settings: DatabaseSettings) -> str:
    """Render the `[database]` TOML table for persisted settings."""
    lines = ["[database]"]
    if settings.database_url is not None:
        lines.append(f"url = {_serialize_toml_string(settings.database_url)}")
    if settings.database_schema is not None:
        lines.append(f"schema = {_serialize_toml_string(settings.database_schema)}")
    lines.append(f"echo = {'true' if settings.database_echo else 'false'}")
    return "\n".join(lines)


def _render_preferences_table(settings: PreferencesSettings) -> str:
    """Render the `[preferences]` TOML table for persisted settings."""
    lines = [
        "[preferences]",
        f"timezone = {_serialize_toml_string(settings.timezone)}",
        f"language = {_serialize_toml_string(settings.language)}",
        f"day_starts_at = {_serialize_toml_string(settings.day_starts_at)}",
        f"week_starts_on = {_serialize_toml_string(settings.week_starts_on)}",
        f"vision_experience_rate_per_hour = {settings.vision_experience_rate_per_hour}",
        f"theme = {_serialize_toml_string(settings.theme)}",
        f"calendar_first_day_of_week = {settings.calendar_first_day_of_week}",
        f"calendar_system = {_serialize_toml_string(settings.calendar_system)}",
        "calendar_seven_year_anchor_date = "
        f"{_serialize_toml_string(settings.calendar_seven_year_anchor_date)}",
        "navigation_visible_modules = "
        f"{_serialize_toml_string_list(settings.navigation_visible_modules)}",
        f"notes_card_min_collapsed_lines = {settings.notes_card_min_collapsed_lines}",
        "notes_export_planning_include_cycle_notes = "
        f"{'true' if settings.notes_export_planning_include_cycle_notes else 'false'}",
        "notes_export_planning_include_task_notes = "
        f"{'true' if settings.notes_export_planning_include_task_notes else 'false'}",
        "planning_show_habit_actions = "
        f"{'true' if settings.planning_show_habit_actions else 'false'}",
        f"tasks_default_planning_preset = "
        f"{_serialize_toml_string(settings.tasks_default_planning_preset)}",
        f"timelog_auto_set_task_planning = "
        f"{'true' if settings.timelog_auto_set_task_planning else 'false'}",
    ]
    if settings.todos_default_inbox_vision is not None:
        lines.append(
            "todos_default_inbox_vision = "
            f"{_serialize_toml_string(settings.todos_default_inbox_vision)}"
        )
    return "\n".join(lines)


def _replace_top_level_table(existing_content: str, *, table_name: str, replacement: str) -> str:
    """Replace or append a top-level TOML table while preserving other file content."""
    section_header = f"[{table_name}]"
    header_pattern = re.compile(r"^\[[^\[\]].*\]$")
    lines = existing_content.splitlines()
    start_index: int | None = None
    end_index = len(lines)

    for index, line in enumerate(lines):
        if line.strip() == section_header:
            start_index = index
            break

    replacement_lines = replacement.splitlines()
    if start_index is None:
        if not lines:
            return f"{replacement}\n"
        if lines[-1].strip():
            lines.append("")
        lines.extend(replacement_lines)
        return "\n".join(lines) + "\n"

    for index in range(start_index + 1, len(lines)):
        if header_pattern.match(lines[index].strip()):
            end_index = index
            break

    updated_lines = lines[:start_index] + replacement_lines + lines[end_index:]
    return "\n".join(updated_lines) + "\n"


def resolve_config_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the configured config file path."""
    source = env or os.environ
    configured_path = source.get("LIFEOS_CONFIG_FILE")
    if configured_path:
        return Path(configured_path).expanduser()
    return DEFAULT_CONFIG_PATH


def default_sqlite_database_url(env: Mapping[str, str] | None = None) -> str:
    """Return the normalized default SQLite database URL."""
    database_path = resolve_config_path(env).parent / DEFAULT_SQLITE_DATABASE_FILENAME
    return validate_database_url(f"sqlite+aiosqlite:///{database_path}")


def load_config_file(config_path: Path) -> dict[str, Any]:
    """Load the config file when it exists."""
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        loaded = tomllib.load(handle)
    if not isinstance(loaded, dict):
        raise ConfigurationError(f"Config file {config_path} must contain a top-level TOML table")
    return loaded


def _get_config_table(
    file_values: Mapping[str, Any],
    *,
    config_path: Path,
    table_name: str,
) -> dict[str, Any]:
    table_values = file_values.get(table_name, {})
    if table_values and not isinstance(table_values, dict):
        raise ConfigurationError(
            f"Config file {config_path} must define [{table_name}] as a TOML table"
        )
    return table_values if isinstance(table_values, dict) else {}


@dataclass(frozen=True)
class DatabaseSettings:
    """Database settings loaded from config files and environment variables."""

    database_url: str | None
    database_schema: str | None
    database_echo: bool
    config_file: Path

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        include_overrides: bool = True,
    ) -> DatabaseSettings:
        """Build database settings from config files and environment variables."""
        source = os.environ if env is None else env
        config_path = resolve_config_path(source)
        file_values = load_config_file(config_path)
        database_values = _get_config_table(
            file_values,
            config_path=config_path,
            table_name="database",
        )

        file_url = database_values.get("url")
        file_schema = database_values.get("schema")
        file_echo = database_values.get("echo")

        database_url = source.get("LIFEOS_DATABASE_URL") if include_overrides else None
        if database_url is None and isinstance(file_url, str):
            database_url = file_url
        if database_url is not None:
            database_url = validate_database_url(database_url)

        database_schema = source.get("LIFEOS_DATABASE_SCHEMA") if include_overrides else None
        if database_schema is None and isinstance(file_schema, str):
            database_schema = file_schema
        database_schema = database_schema or DEFAULT_DATABASE_SCHEMA

        database_echo_value = source.get("LIFEOS_DATABASE_ECHO") if include_overrides else None
        if database_echo_value is not None:
            database_echo = _parse_bool(database_echo_value)
        elif isinstance(file_echo, bool):
            database_echo = file_echo
        elif isinstance(file_echo, str):
            database_echo = _parse_bool(file_echo)
        else:
            database_echo = False

        database_schema = normalize_database_schema(
            database_url=database_url,
            configured_schema=database_schema,
            explicit=False,
        )
        return cls(
            database_url=database_url,
            database_schema=database_schema,
            database_echo=database_echo,
            config_file=config_path,
        )

    def require_database_url(self) -> str:
        """Return the configured database URL or raise a helpful error."""
        if self.database_url is None:
            raise ConfigurationError(
                "Database configuration is missing. Run `lifeos init` to create a config file "
                "or set LIFEOS_DATABASE_URL."
            )
        return self.database_url

    def render_database_url(self, *, show_secrets: bool = False) -> str:
        """Render the database URL for display."""
        if self.database_url is None:
            return "<unset>"
        try:
            parsed = make_url(self.database_url)
        except ArgumentError:
            return self.database_url
        return parsed.render_as_string(hide_password=not show_secrets)

    @property
    def backend_policy(self) -> DatabaseBackendPolicy | None:
        """Return the backend policy for the configured database URL when available."""
        if self.database_url is None:
            return None
        return database_policy(self.database_url)

    @property
    def database_backend(self) -> str | None:
        """Return the configured database backend name when available."""
        policy = self.backend_policy
        if policy is None:
            return None
        return policy.backend_name


@dataclass(frozen=True)
class PreferencesSettings:
    """User preference values persisted in the local config file."""

    timezone: str
    language: str
    day_starts_at: str
    week_starts_on: str
    vision_experience_rate_per_hour: int
    config_file: Path
    theme: str = DEFAULT_THEME
    calendar_first_day_of_week: int = DEFAULT_CALENDAR_FIRST_DAY_OF_WEEK
    calendar_system: str = DEFAULT_CALENDAR_SYSTEM
    calendar_seven_year_anchor_date: str = DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_DATE
    navigation_visible_modules: tuple[str, ...] = DEFAULT_NAVIGATION_VISIBLE_MODULES
    notes_card_min_collapsed_lines: int = DEFAULT_NOTES_CARD_MIN_COLLAPSED_LINES
    notes_export_planning_include_cycle_notes: bool = (
        DEFAULT_NOTES_EXPORT_PLANNING_INCLUDE_CYCLE_NOTES
    )
    notes_export_planning_include_task_notes: bool = (
        DEFAULT_NOTES_EXPORT_PLANNING_INCLUDE_TASK_NOTES
    )
    planning_show_habit_actions: bool = DEFAULT_PLANNING_SHOW_HABIT_ACTIONS
    tasks_default_planning_preset: str = DEFAULT_TASKS_DEFAULT_PLANNING_PRESET
    timelog_auto_set_task_planning: bool = DEFAULT_TIMELOG_AUTO_SET_TASK_PLANNING
    todos_default_inbox_vision: str | None = DEFAULT_TODOS_DEFAULT_INBOX_VISION
    weight_unit: str = DEFAULT_WEIGHT_UNIT
    body_height_cm: float | None = DEFAULT_BODY_HEIGHT_CM

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        include_overrides: bool = True,
    ) -> PreferencesSettings:
        """Build preferences from config files and optional environment overrides."""
        source = os.environ if env is None else env
        config_path = resolve_config_path(source)
        file_values = load_config_file(config_path)
        preference_values = _get_config_table(
            file_values,
            config_path=config_path,
            table_name="preferences",
        )

        file_timezone = preference_values.get("timezone")
        file_language = preference_values.get("language")
        file_day_starts_at = preference_values.get("day_starts_at")
        file_week_starts_on = preference_values.get("week_starts_on")
        file_vision_experience_rate = preference_values.get("vision_experience_rate_per_hour")
        file_theme = preference_values.get("theme")
        file_calendar_first_day_of_week = preference_values.get("calendar_first_day_of_week")
        file_calendar_system = preference_values.get("calendar_system")
        file_calendar_seven_year_anchor_date = preference_values.get(
            "calendar_seven_year_anchor_date"
        )
        file_navigation_visible_modules = preference_values.get("navigation_visible_modules")
        file_notes_card_min_collapsed_lines = preference_values.get(
            "notes_card_min_collapsed_lines"
        )
        file_notes_export_include_cycle_notes = preference_values.get(
            "notes_export_planning_include_cycle_notes"
        )
        file_notes_export_include_task_notes = preference_values.get(
            "notes_export_planning_include_task_notes"
        )
        file_planning_show_habit_actions = preference_values.get("planning_show_habit_actions")
        file_tasks_default_planning_preset = preference_values.get("tasks_default_planning_preset")
        file_timelog_auto_set_task_planning = preference_values.get(
            "timelog_auto_set_task_planning"
        )
        file_todos_default_inbox_vision = preference_values.get("todos_default_inbox_vision")
        file_weight_unit = preference_values.get("weight_unit")
        file_body_height_cm = preference_values.get("body_height_cm")

        timezone_value = source.get("LIFEOS_TIMEZONE") if include_overrides else None
        if timezone_value is None and isinstance(file_timezone, str):
            timezone_value = file_timezone
        timezone_value = validate_timezone_name(timezone_value or detect_default_timezone(source))

        language_value = source.get("LIFEOS_LANGUAGE") if include_overrides else None
        if language_value is None and isinstance(file_language, str):
            language_value = file_language
        language_value = validate_language(language_value or detect_default_language(source))

        day_starts_at_value = source.get("LIFEOS_DAY_STARTS_AT") if include_overrides else None
        if day_starts_at_value is None and isinstance(file_day_starts_at, str):
            day_starts_at_value = file_day_starts_at
        day_starts_at_value = validate_day_starts_at(day_starts_at_value or DEFAULT_DAY_STARTS_AT)

        week_starts_on_value = source.get("LIFEOS_WEEK_STARTS_ON") if include_overrides else None
        if week_starts_on_value is None and isinstance(file_week_starts_on, str):
            week_starts_on_value = file_week_starts_on
        week_starts_on_value = validate_week_starts_on(
            week_starts_on_value or DEFAULT_WEEK_STARTS_ON
        )

        vision_experience_rate_value: int | str | None = (
            source.get("LIFEOS_VISION_EXPERIENCE_RATE_PER_HOUR") if include_overrides else None
        )
        if vision_experience_rate_value is None and file_vision_experience_rate is not None:
            vision_experience_rate_value = file_vision_experience_rate
        if vision_experience_rate_value is None:
            vision_experience_rate_value = DEFAULT_VISION_EXPERIENCE_RATE_PER_HOUR
        vision_experience_rate = validate_vision_experience_rate_per_hour(
            vision_experience_rate_value
        )

        theme_value = file_theme if isinstance(file_theme, str) else DEFAULT_THEME
        theme = validate_theme(theme_value)

        calendar_first_day_of_week_value = (
            file_calendar_first_day_of_week
            if file_calendar_first_day_of_week is not None
            else DEFAULT_CALENDAR_FIRST_DAY_OF_WEEK
        )
        calendar_first_day_of_week = validate_calendar_first_day_of_week(
            calendar_first_day_of_week_value
        )

        calendar_system_value = (
            file_calendar_system
            if isinstance(file_calendar_system, str)
            else DEFAULT_CALENDAR_SYSTEM
        )
        calendar_system = validate_calendar_system(calendar_system_value)

        calendar_seven_year_anchor_date_value = (
            file_calendar_seven_year_anchor_date
            if isinstance(file_calendar_seven_year_anchor_date, str)
            else DEFAULT_CALENDAR_SEVEN_YEAR_ANCHOR_DATE
        )
        calendar_seven_year_anchor_date = validate_calendar_seven_year_anchor_date(
            calendar_seven_year_anchor_date_value
        )

        navigation_visible_modules_value = (
            file_navigation_visible_modules
            if file_navigation_visible_modules is not None
            else DEFAULT_NAVIGATION_VISIBLE_MODULES
        )
        navigation_visible_modules = validate_navigation_visible_modules(
            navigation_visible_modules_value
        )

        notes_card_min_collapsed_lines_value = (
            file_notes_card_min_collapsed_lines
            if file_notes_card_min_collapsed_lines is not None
            else DEFAULT_NOTES_CARD_MIN_COLLAPSED_LINES
        )
        notes_card_min_collapsed_lines = validate_notes_card_min_collapsed_lines(
            notes_card_min_collapsed_lines_value
        )

        notes_export_include_cycle_notes = (
            bool(file_notes_export_include_cycle_notes)
            if isinstance(file_notes_export_include_cycle_notes, bool)
            else DEFAULT_NOTES_EXPORT_PLANNING_INCLUDE_CYCLE_NOTES
        )
        notes_export_include_task_notes = (
            bool(file_notes_export_include_task_notes)
            if isinstance(file_notes_export_include_task_notes, bool)
            else DEFAULT_NOTES_EXPORT_PLANNING_INCLUDE_TASK_NOTES
        )
        planning_show_habit_actions = (
            bool(file_planning_show_habit_actions)
            if isinstance(file_planning_show_habit_actions, bool)
            else DEFAULT_PLANNING_SHOW_HABIT_ACTIONS
        )

        tasks_default_planning_preset_value = (
            file_tasks_default_planning_preset
            if isinstance(file_tasks_default_planning_preset, str)
            else DEFAULT_TASKS_DEFAULT_PLANNING_PRESET
        )
        tasks_default_planning_preset = validate_tasks_default_planning_preset(
            tasks_default_planning_preset_value
        )

        timelog_auto_set_task_planning = (
            bool(file_timelog_auto_set_task_planning)
            if isinstance(file_timelog_auto_set_task_planning, bool)
            else DEFAULT_TIMELOG_AUTO_SET_TASK_PLANNING
        )
        todos_default_inbox_vision_value = (
            file_todos_default_inbox_vision
            if isinstance(file_todos_default_inbox_vision, str)
            else DEFAULT_TODOS_DEFAULT_INBOX_VISION
        )
        todos_default_inbox_vision = validate_todos_default_inbox_vision(
            todos_default_inbox_vision_value
        )

        weight_unit_value = (
            file_weight_unit if isinstance(file_weight_unit, str) else DEFAULT_WEIGHT_UNIT
        )
        weight_unit = validate_weight_unit(weight_unit_value)
        body_height_cm = validate_body_height_cm(file_body_height_cm)

        return cls(
            timezone=timezone_value,
            language=language_value,
            day_starts_at=day_starts_at_value,
            week_starts_on=week_starts_on_value,
            vision_experience_rate_per_hour=vision_experience_rate,
            config_file=config_path,
            theme=theme,
            calendar_first_day_of_week=calendar_first_day_of_week,
            calendar_system=calendar_system,
            calendar_seven_year_anchor_date=calendar_seven_year_anchor_date,
            navigation_visible_modules=navigation_visible_modules,
            notes_card_min_collapsed_lines=notes_card_min_collapsed_lines,
            notes_export_planning_include_cycle_notes=notes_export_include_cycle_notes,
            notes_export_planning_include_task_notes=notes_export_include_task_notes,
            planning_show_habit_actions=planning_show_habit_actions,
            tasks_default_planning_preset=tasks_default_planning_preset,
            timelog_auto_set_task_planning=timelog_auto_set_task_planning,
            todos_default_inbox_vision=todos_default_inbox_vision,
            weight_unit=weight_unit,
            body_height_cm=body_height_cm,
        )


def write_database_settings(
    settings: DatabaseSettings,
    *,
    preferences: PreferencesSettings | None = None,
) -> Path:
    """Persist database settings, keeping preferences in the same config file."""
    config_path = settings.config_file
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing_content = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    database_content = _replace_top_level_table(
        existing_content,
        table_name="database",
        replacement=_render_database_table(settings),
    )
    resolved_preferences = preferences
    if resolved_preferences is None:
        env = dict(os.environ)
        env["LIFEOS_CONFIG_FILE"] = str(config_path)
        resolved_preferences = PreferencesSettings.from_env(env)
    content = _replace_top_level_table(
        database_content,
        table_name="preferences",
        replacement=_render_preferences_table(resolved_preferences),
    )
    config_path.write_text(content, encoding="utf-8")
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass
    return config_path


def clear_config_cache() -> None:
    """Clear cached config lookups for the current process."""
    get_database_settings.cache_clear()
    get_preferences_settings.cache_clear()


@lru_cache(maxsize=1)
def get_database_settings() -> DatabaseSettings:
    """Return cached database settings for the current process."""
    return DatabaseSettings.from_env()


@lru_cache(maxsize=1)
def get_preferences_settings() -> PreferencesSettings:
    """Return cached user preference values for the current process."""
    return PreferencesSettings.from_env()
