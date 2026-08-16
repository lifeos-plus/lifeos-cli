"""Configuration workflows shared by CLI entrypoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from lifeos_cli.cli_support.runtime_utils import refresh_runtime_configuration
from lifeos_cli.config import (
    DEFAULT_DATABASE_SCHEMA,
    DEFAULT_DAY_STARTS_AT,
    DEFAULT_THEME,
    DEFAULT_VISION_EXPERIENCE_RATE_PER_HOUR,
    DEFAULT_WEEK_STARTS_ON,
    ConfigurationError,
    DatabaseSettings,
    PreferencesSettings,
    clear_config_cache,
    database_policy,
    default_sqlite_database_url,
    detect_default_language,
    detect_default_timezone,
    ensure_database_driver_available,
    normalize_database_schema,
    parse_boolean_value,
    resolve_config_path,
    validate_calendar_first_day_of_week,
    validate_calendar_seven_year_anchor_date,
    validate_calendar_system,
    validate_database_url,
    validate_day_starts_at,
    validate_language,
    validate_navigation_visible_modules,
    validate_notes_card_min_collapsed_lines,
    validate_tasks_default_planning_preset,
    validate_theme,
    validate_timezone_name,
    validate_todos_default_inbox_vision,
    validate_vision_experience_rate_per_hour,
    validate_week_starts_on,
    write_database_settings,
)


@dataclass(frozen=True)
class InitializationPrompts:
    """Interactive prompt callables used to collect missing config values."""

    prompt_database_url: Callable[[str | None], str]
    prompt_database_schema: Callable[[str | None], str]
    prompt_language: Callable[[str | None], str]
    prompt_database_echo: Callable[[bool], bool]


@dataclass(frozen=True)
class InitializationRequest:
    """Input values for configuration initialization."""

    database_url: str | None
    schema: str | None
    echo: bool | None
    timezone: str | None
    language: str | None
    day_starts_at: str | None
    week_starts_on: str | None
    vision_experience_rate_per_hour: int | None
    non_interactive: bool
    is_interactive: bool
    prompts: InitializationPrompts | None = None


SUPPORTED_CONFIG_KEYS = (
    "database.url",
    "database.echo",
    "preferences.timezone",
    "preferences.language",
    "preferences.day_starts_at",
    "preferences.week_starts_on",
    "preferences.vision_experience_rate_per_hour",
    "preferences.theme",
    "preferences.calendar_first_day_of_week",
    "preferences.calendar_system",
    "preferences.calendar_seven_year_anchor_date",
    "preferences.navigation_visible_modules",
    "preferences.notes_card_min_collapsed_lines",
    "preferences.notes_export_planning_include_cycle_notes",
    "preferences.notes_export_planning_include_task_notes",
    "preferences.planning_show_habit_actions",
    "preferences.tasks_default_planning_preset",
    "preferences.timelog_auto_set_task_planning",
    "preferences.todos_default_inbox_vision",
)


@dataclass(frozen=True)
class ConfigSetResult:
    """Result of one config update write operation."""

    key: str
    config_path: Path
    database_settings: DatabaseSettings
    preferences_settings: PreferencesSettings


def build_database_settings(request: InitializationRequest) -> DatabaseSettings:
    """Build database settings from explicit input, current config, and prompts."""
    config_path = resolve_config_path()
    try:
        current = DatabaseSettings.from_env(include_overrides=False)
    except (ConfigurationError, ValueError):
        current = DatabaseSettings(
            database_url=None,
            database_schema=DEFAULT_DATABASE_SCHEMA,
            database_echo=False,
            config_file=config_path,
        )
    database_url = request.database_url or current.database_url or default_sqlite_database_url()
    database_echo = current.database_echo if request.echo is None else request.echo
    if database_url is not None:
        database_url = validate_database_url(database_url)
        ensure_database_driver_available(database_url)
    supports_database_schema = (
        database_policy(database_url).supports_schema if database_url is not None else True
    )
    database_schema = (
        request.schema
        if request.schema is not None
        else current.database_schema
        if supports_database_schema
        else None
    )

    if not request.non_interactive and request.is_interactive:
        if request.prompts is None:
            raise ConfigurationError(
                "Interactive initialization requires prompt handlers to collect missing values."
            )
        if request.database_url is None:
            database_url = request.prompts.prompt_database_url(database_url)
            ensure_database_driver_available(database_url)
            supports_database_schema = database_policy(database_url).supports_schema
            if not supports_database_schema:
                database_schema = None
        if request.schema is None and supports_database_schema:
            database_schema = request.prompts.prompt_database_schema(database_schema)
        if request.echo is None:
            database_echo = request.prompts.prompt_database_echo(database_echo)

    return DatabaseSettings(
        database_url=database_url,
        database_schema=normalize_database_schema(
            database_url=database_url,
            configured_schema=database_schema,
            explicit=request.schema is not None,
        ),
        database_echo=database_echo,
        config_file=config_path,
    )


def build_preferences_settings(request: InitializationRequest) -> PreferencesSettings:
    """Build preference settings from explicit input and current config."""
    config_path = resolve_config_path()
    try:
        current = PreferencesSettings.from_env(include_overrides=False)
    except (ConfigurationError, ValueError):
        current = PreferencesSettings(
            timezone=detect_default_timezone(),
            language=detect_default_language(),
            day_starts_at=DEFAULT_DAY_STARTS_AT,
            week_starts_on=DEFAULT_WEEK_STARTS_ON,
            vision_experience_rate_per_hour=DEFAULT_VISION_EXPERIENCE_RATE_PER_HOUR,
            config_file=config_path,
            theme=DEFAULT_THEME,
        )

    timezone_value = request.timezone or current.timezone
    language_value = request.language or current.language
    day_starts_at_value = request.day_starts_at or current.day_starts_at
    week_starts_on_value = request.week_starts_on or current.week_starts_on
    vision_experience_rate_value = (
        current.vision_experience_rate_per_hour
        if request.vision_experience_rate_per_hour is None
        else request.vision_experience_rate_per_hour
    )

    if not request.non_interactive and request.is_interactive and request.language is None:
        if request.prompts is None:
            raise ConfigurationError(
                "Interactive initialization requires prompt handlers to collect missing values."
            )
        language_value = request.prompts.prompt_language(language_value)

    return PreferencesSettings(
        timezone=validate_timezone_name(timezone_value),
        language=validate_language(language_value),
        day_starts_at=validate_day_starts_at(day_starts_at_value),
        week_starts_on=validate_week_starts_on(week_starts_on_value),
        vision_experience_rate_per_hour=validate_vision_experience_rate_per_hour(
            vision_experience_rate_value
        ),
        config_file=config_path,
        theme=validate_theme(current.theme),
        calendar_first_day_of_week=current.calendar_first_day_of_week,
        calendar_system=current.calendar_system,
        calendar_seven_year_anchor_date=current.calendar_seven_year_anchor_date,
        navigation_visible_modules=current.navigation_visible_modules,
        notes_card_min_collapsed_lines=current.notes_card_min_collapsed_lines,
        notes_export_planning_include_cycle_notes=(
            current.notes_export_planning_include_cycle_notes
        ),
        notes_export_planning_include_task_notes=current.notes_export_planning_include_task_notes,
        planning_show_habit_actions=current.planning_show_habit_actions,
        tasks_default_planning_preset=current.tasks_default_planning_preset,
        timelog_auto_set_task_planning=current.timelog_auto_set_task_planning,
        todos_default_inbox_vision=current.todos_default_inbox_vision,
    )


def persist_runtime_settings(
    database_settings: DatabaseSettings,
    preferences_settings: PreferencesSettings,
) -> Path:
    """Write config changes and refresh runtime caches."""
    config_path = write_database_settings(
        database_settings,
        preferences=preferences_settings,
    )
    refresh_runtime_configuration()
    return config_path


def set_runtime_config_value(
    *,
    key: str,
    value: str,
    refresh_runtime: bool = True,
) -> ConfigSetResult:
    """Persist one supported runtime config key and refresh caches."""
    normalized_key = key.strip()
    if normalized_key == "database.schema":
        raise ConfigurationError(
            "Config key `database.schema` is deployment-scoped. "
            "Re-run `lifeos init --schema <name>` to change it."
        )
    if normalized_key not in SUPPORTED_CONFIG_KEYS:
        supported_keys = ", ".join(SUPPORTED_CONFIG_KEYS)
        raise ConfigurationError(
            f"Unsupported config key {normalized_key!r}. Supported keys: {supported_keys}"
        )

    database_settings = DatabaseSettings.from_env(include_overrides=False)
    preferences_settings = PreferencesSettings.from_env(include_overrides=False)

    if normalized_key == "database.url":
        validated_database_url = validate_database_url(value)
        ensure_database_driver_available(validated_database_url)
        current_backend = database_settings.database_backend
        next_backend = database_policy(validated_database_url).backend_name
        if current_backend is not None and current_backend != next_backend:
            raise ConfigurationError(
                "Switching between PostgreSQL and SQLite with `config update database.url` is not "
                "supported. Re-run `lifeos init --database-url ...` and provide `--schema` "
                "when targeting PostgreSQL."
            )
        database_settings = replace(
            database_settings,
            database_url=validated_database_url,
            database_schema=normalize_database_schema(
                database_url=validated_database_url,
                configured_schema=database_settings.database_schema,
                explicit=False,
            ),
        )
    elif normalized_key == "database.echo":
        database_settings = replace(
            database_settings,
            database_echo=parse_boolean_value(value, field_name="Config key `database.echo`"),
        )
    elif normalized_key == "preferences.timezone":
        preferences_settings = replace(
            preferences_settings,
            timezone=validate_timezone_name(value),
        )
    elif normalized_key == "preferences.language":
        preferences_settings = replace(
            preferences_settings,
            language=validate_language(value),
        )
    elif normalized_key == "preferences.day_starts_at":
        preferences_settings = replace(
            preferences_settings,
            day_starts_at=validate_day_starts_at(value),
        )
    elif normalized_key == "preferences.week_starts_on":
        preferences_settings = replace(
            preferences_settings,
            week_starts_on=validate_week_starts_on(value),
        )
    elif normalized_key == "preferences.vision_experience_rate_per_hour":
        preferences_settings = replace(
            preferences_settings,
            vision_experience_rate_per_hour=validate_vision_experience_rate_per_hour(value),
        )
    elif normalized_key == "preferences.theme":
        preferences_settings = replace(
            preferences_settings,
            theme=validate_theme(value),
        )
    elif normalized_key == "preferences.calendar_first_day_of_week":
        preferences_settings = replace(
            preferences_settings,
            calendar_first_day_of_week=validate_calendar_first_day_of_week(value),
        )
    elif normalized_key == "preferences.calendar_system":
        preferences_settings = replace(
            preferences_settings,
            calendar_system=validate_calendar_system(value),
        )
    elif normalized_key == "preferences.calendar_seven_year_anchor_date":
        preferences_settings = replace(
            preferences_settings,
            calendar_seven_year_anchor_date=validate_calendar_seven_year_anchor_date(value),
        )
    elif normalized_key == "preferences.navigation_visible_modules":
        preferences_settings = replace(
            preferences_settings,
            navigation_visible_modules=validate_navigation_visible_modules(value),
        )
    elif normalized_key == "preferences.notes_card_min_collapsed_lines":
        preferences_settings = replace(
            preferences_settings,
            notes_card_min_collapsed_lines=validate_notes_card_min_collapsed_lines(value),
        )
    elif normalized_key == "preferences.notes_export_planning_include_cycle_notes":
        preferences_settings = replace(
            preferences_settings,
            notes_export_planning_include_cycle_notes=parse_boolean_value(
                value,
                field_name="Config key `preferences.notes_export_planning_include_cycle_notes`",
            ),
        )
    elif normalized_key == "preferences.notes_export_planning_include_task_notes":
        preferences_settings = replace(
            preferences_settings,
            notes_export_planning_include_task_notes=parse_boolean_value(
                value,
                field_name="Config key `preferences.notes_export_planning_include_task_notes`",
            ),
        )
    elif normalized_key == "preferences.planning_show_habit_actions":
        preferences_settings = replace(
            preferences_settings,
            planning_show_habit_actions=parse_boolean_value(
                value,
                field_name="Config key `preferences.planning_show_habit_actions`",
            ),
        )
    elif normalized_key == "preferences.tasks_default_planning_preset":
        preferences_settings = replace(
            preferences_settings,
            tasks_default_planning_preset=validate_tasks_default_planning_preset(value),
        )
    elif normalized_key == "preferences.timelog_auto_set_task_planning":
        preferences_settings = replace(
            preferences_settings,
            timelog_auto_set_task_planning=parse_boolean_value(
                value,
                field_name="Config key `preferences.timelog_auto_set_task_planning`",
            ),
        )
    elif normalized_key == "preferences.todos_default_inbox_vision":
        preferences_settings = replace(
            preferences_settings,
            todos_default_inbox_vision=validate_todos_default_inbox_vision(value),
        )

    written_path = write_database_settings(
        database_settings,
        preferences=preferences_settings,
    )
    if refresh_runtime:
        refresh_runtime_configuration()
    else:
        clear_config_cache()
    return ConfigSetResult(
        key=normalized_key,
        config_path=written_path,
        database_settings=database_settings,
        preferences_settings=preferences_settings,
    )
