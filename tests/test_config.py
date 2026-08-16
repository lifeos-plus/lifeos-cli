from __future__ import annotations

from pathlib import Path

from lifeos_cli.application.configuration import (
    InitializationPrompts,
    InitializationRequest,
    build_database_settings,
    build_preferences_settings,
    set_runtime_config_value,
)
from lifeos_cli.config import (
    DEFAULT_CONFIG_PATH,
    ConfigurationError,
    DatabaseSettings,
    PreferencesSettings,
    database_policy,
    default_sqlite_database_url,
    detect_default_language,
    ensure_database_driver_available,
    parse_boolean_value,
    resolve_config_path,
    validate_calendar_first_day_of_week,
    validate_calendar_seven_year_anchor_date,
    validate_calendar_system,
    validate_database_schema_name,
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


def test_database_settings_defaults_use_config_path_and_no_database_url(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-config.toml"
    settings = DatabaseSettings.from_env({"LIFEOS_CONFIG_FILE": str(config_path)})

    assert settings.database_url is None
    assert settings.database_schema == "lifeos"
    assert settings.database_echo is False
    assert settings.config_file == config_path


def test_database_settings_honors_env_values(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-config.toml"
    settings = DatabaseSettings.from_env(
        {
            "LIFEOS_CONFIG_FILE": str(config_path),
            "LIFEOS_DATABASE_URL": "postgresql+psycopg://localhost/custom",
            "LIFEOS_DATABASE_SCHEMA": "lifeos_dev",
            "LIFEOS_DATABASE_ECHO": "true",
        }
    )

    assert settings.database_url == "postgresql+psycopg://localhost/custom"
    assert settings.database_schema == "lifeos_dev"
    assert settings.database_echo is True


def test_database_settings_can_ignore_env_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "postgresql+psycopg://localhost/from_file"',
                'schema = "lifeos_notes"',
                "echo = false",
                "",
            )
        ),
        encoding="utf-8",
    )

    settings = DatabaseSettings.from_env(
        {
            "LIFEOS_CONFIG_FILE": str(config_path),
            "LIFEOS_DATABASE_URL": "postgresql+psycopg://localhost/from_env",
            "LIFEOS_DATABASE_SCHEMA": "lifeos_dev",
            "LIFEOS_DATABASE_ECHO": "true",
        },
        include_overrides=False,
    )

    assert settings.database_url == "postgresql+psycopg://localhost/from_file"
    assert settings.database_schema == "lifeos_notes"
    assert settings.database_echo is False


def test_database_settings_reads_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "postgresql+psycopg://localhost/from_file"',
                'schema = "lifeos_notes"',
                "echo = true",
                "",
            )
        ),
        encoding="utf-8",
    )

    settings = DatabaseSettings.from_env({"LIFEOS_CONFIG_FILE": str(config_path)})

    assert settings.database_url == "postgresql+psycopg://localhost/from_file"
    assert settings.database_schema == "lifeos_notes"
    assert settings.database_echo is True


def test_database_settings_rejects_invalid_schema_name(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-config.toml"
    try:
        DatabaseSettings.from_env(
            {
                "LIFEOS_CONFIG_FILE": str(config_path),
                "LIFEOS_DATABASE_SCHEMA": "lifeos-dev",
            }
        )
    except ConfigurationError as exc:
        assert "lifeos_dev" in str(exc)
    else:
        raise AssertionError("invalid schema name should fail validation")


def test_validate_database_schema_name_accepts_underscores() -> None:
    assert validate_database_schema_name("lifeos_dev") == "lifeos_dev"


def test_preferences_settings_honor_env_values(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-config.toml"
    settings = PreferencesSettings.from_env(
        {
            "LIFEOS_CONFIG_FILE": str(config_path),
            "LIFEOS_TIMEZONE": "America/Toronto",
            "LIFEOS_LANGUAGE": "zh_Hans.UTF-8",
            "LIFEOS_DAY_STARTS_AT": "04:00",
            "LIFEOS_WEEK_STARTS_ON": "sunday",
            "LIFEOS_VISION_EXPERIENCE_RATE_PER_HOUR": "120",
        }
    )

    assert settings.timezone == "America/Toronto"
    assert settings.language == "zh-Hans"
    assert settings.day_starts_at == "04:00"
    assert settings.week_starts_on == "sunday"
    assert settings.vision_experience_rate_per_hour == 120


def test_preferences_settings_read_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[preferences]",
                'timezone = "America/Toronto"',
                'language = "zh-Hans"',
                'day_starts_at = "04:00"',
                'week_starts_on = "sunday"',
                "vision_experience_rate_per_hour = 90",
                'theme = "night"',
                "calendar_first_day_of_week = 7",
                'calendar_system = "mayan_13_moon"',
                'calendar_seven_year_anchor_date = "2026-07-20"',
                'navigation_visible_modules = ["visions", "notes", "settings"]',
                "notes_card_min_collapsed_lines = 9",
                "notes_export_planning_include_cycle_notes = true",
                "notes_export_planning_include_task_notes = false",
                "planning_show_habit_actions = false",
                'tasks_default_planning_preset = "today"',
                "timelog_auto_set_task_planning = true",
                'todos_default_inbox_vision = "11111111-1111-1111-1111-111111111111"',
                "",
            )
        ),
        encoding="utf-8",
    )

    settings = PreferencesSettings.from_env({"LIFEOS_CONFIG_FILE": str(config_path)})

    assert settings.timezone == "America/Toronto"
    assert settings.language == "zh-Hans"
    assert settings.day_starts_at == "04:00"
    assert settings.week_starts_on == "sunday"
    assert settings.vision_experience_rate_per_hour == 90
    assert settings.theme == "night"
    assert settings.calendar_first_day_of_week == 7
    assert settings.calendar_system == "mayan_13_moon"
    assert settings.calendar_seven_year_anchor_date == "2026-07-20"
    assert settings.navigation_visible_modules == ("visions", "notes", "settings")
    assert settings.notes_card_min_collapsed_lines == 9
    assert settings.notes_export_planning_include_cycle_notes is True
    assert settings.notes_export_planning_include_task_notes is False
    assert settings.planning_show_habit_actions is False
    assert settings.tasks_default_planning_preset == "today"
    assert settings.timelog_auto_set_task_planning is True
    assert settings.todos_default_inbox_vision == "11111111-1111-1111-1111-111111111111"


def test_preferences_settings_can_ignore_env_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[preferences]",
                'timezone = "America/Toronto"',
                'language = "zh-Hans"',
                'day_starts_at = "04:00"',
                'week_starts_on = "sunday"',
                "vision_experience_rate_per_hour = 90",
                "",
            )
        ),
        encoding="utf-8",
    )

    settings = PreferencesSettings.from_env(
        {
            "LIFEOS_CONFIG_FILE": str(config_path),
            "LIFEOS_TIMEZONE": "UTC",
            "LIFEOS_LANGUAGE": "en",
            "LIFEOS_DAY_STARTS_AT": "00:00",
            "LIFEOS_WEEK_STARTS_ON": "monday",
            "LIFEOS_VISION_EXPERIENCE_RATE_PER_HOUR": "120",
        },
        include_overrides=False,
    )

    assert settings.timezone == "America/Toronto"
    assert settings.language == "zh-Hans"
    assert settings.day_starts_at == "04:00"
    assert settings.week_starts_on == "sunday"
    assert settings.vision_experience_rate_per_hour == 90
    assert settings.theme == "system"


def test_preferences_settings_rejects_invalid_vision_experience_rate(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[preferences]",
                'timezone = "America/Toronto"',
                'language = "zh-Hans"',
                'day_starts_at = "04:00"',
                'week_starts_on = "sunday"',
                "vision_experience_rate_per_hour = 0",
                "",
            )
        ),
        encoding="utf-8",
    )

    try:
        PreferencesSettings.from_env({"LIFEOS_CONFIG_FILE": str(config_path)})
    except ConfigurationError as exc:
        assert "between 1 and 3600" in str(exc)
    else:
        raise AssertionError("invalid vision experience rate should fail validation")


def test_validate_database_url_requires_postgresql_psycopg_driver() -> None:
    assert validate_database_url("sqlite+aiosqlite:///lifeos.db") == "sqlite+aiosqlite:///lifeos.db"

    try:
        validate_database_url("mysql+asyncmy://localhost/lifeos")
    except ConfigurationError as exc:
        assert "sqlite+aiosqlite://" in str(exc)
        assert "postgresql+psycopg://" in str(exc)
    else:
        raise AssertionError("unsupported driver should fail validation")


def test_validate_database_url_expands_sqlite_home_directory() -> None:
    expected_path = Path("~/.lifeos/lifeos.db").expanduser()

    assert validate_database_url("sqlite+aiosqlite:///~/.lifeos/lifeos.db") == (
        f"sqlite+aiosqlite:///{expected_path}"
    )


def test_resolve_config_path_defaults_to_lifeos_home_directory() -> None:
    assert resolve_config_path({"LIFEOS_CONFIG_FILE": ""}) == DEFAULT_CONFIG_PATH
    assert DEFAULT_CONFIG_PATH == Path.home() / ".lifeos" / "config.toml"


def test_default_sqlite_database_url_uses_default_file_name(tmp_path: Path) -> None:
    config_path = tmp_path / "nested" / "config.toml"
    expected_path = config_path.parent / "lifeos.db"

    assert default_sqlite_database_url({"LIFEOS_CONFIG_FILE": str(config_path)}) == (
        f"sqlite+aiosqlite:///{expected_path}"
    )


def test_database_policy_uses_database_drivername() -> None:
    policy = database_policy("sqlite+aiosqlite:///tmp/lifeos.db")

    assert policy.backend_name == "sqlite"
    assert policy.supports_schema is False


def test_ensure_database_driver_available_requires_postgres_extra(
    monkeypatch,
) -> None:
    def missing_driver(module_name: str):
        if module_name == "psycopg":
            raise ModuleNotFoundError("No module named 'psycopg'")
        raise AssertionError(f"unexpected module import: {module_name}")

    monkeypatch.setattr("lifeos_cli.config.import_module", missing_driver)

    try:
        ensure_database_driver_available("postgresql+psycopg://localhost/lifeos")
    except ConfigurationError as exc:
        assert "lifeos-cli[postgres]" in str(exc)
    else:
        raise AssertionError("missing postgres extra should fail driver preflight")


def test_database_settings_omit_schema_for_sqlite_url(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    settings = DatabaseSettings.from_env(
        {
            "LIFEOS_CONFIG_FILE": str(config_path),
            "LIFEOS_DATABASE_URL": "sqlite+aiosqlite:///lifeos.db",
            "LIFEOS_DATABASE_SCHEMA": "lifeos_dev",
        }
    )

    assert settings.database_url == "sqlite+aiosqlite:///lifeos.db"
    assert settings.database_schema is None


def test_build_database_settings_skip_schema_for_sqlite_prompts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    captured_defaults: list[str | None] = []

    def prompt_database_schema(default: str | None) -> str:
        captured_defaults.append(default)
        return "ignored"

    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone=None,
        language=None,
        day_starts_at=None,
        week_starts_on=None,
        vision_experience_rate_per_hour=None,
        non_interactive=False,
        is_interactive=True,
        prompts=InitializationPrompts(
            prompt_database_url=lambda default: "sqlite+aiosqlite:///lifeos.db",
            prompt_database_schema=prompt_database_schema,
            prompt_language=lambda default: "zh-Hans",
            prompt_database_echo=lambda default: False,
        ),
    )

    settings = build_database_settings(request)

    assert settings.database_url == "sqlite+aiosqlite:///lifeos.db"
    assert settings.database_schema is None
    assert captured_defaults == []


def test_build_database_settings_defaults_to_sqlite_when_database_url_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone=None,
        language=None,
        day_starts_at=None,
        week_starts_on=None,
        vision_experience_rate_per_hour=None,
        non_interactive=True,
        is_interactive=False,
        prompts=None,
    )

    settings = build_database_settings(request)

    assert settings.database_url == f"sqlite+aiosqlite:///{config_path.parent / 'lifeos.db'}"
    assert settings.database_schema is None
    assert settings.database_echo is False


def test_build_database_settings_rejects_explicit_sqlite_schema(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url="sqlite+aiosqlite:///lifeos.db",
        schema="lifeos_dev",
        echo=None,
        timezone=None,
        language=None,
        day_starts_at=None,
        week_starts_on=None,
        vision_experience_rate_per_hour=None,
        non_interactive=True,
        is_interactive=False,
        prompts=None,
    )

    try:
        build_database_settings(request)
    except ConfigurationError as exc:
        assert "only supported for `postgresql+psycopg://`" in str(exc)
    else:
        raise AssertionError("sqlite schema should fail validation")


def test_write_database_settings_omit_schema_for_sqlite(tmp_path: Path) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    database_settings = DatabaseSettings(
        database_url="sqlite+aiosqlite:///lifeos.db",
        database_schema=None,
        database_echo=False,
        config_file=config_path,
    )
    preferences_settings = PreferencesSettings(
        timezone="America/Toronto",
        language="zh-Hans",
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=90,
        config_file=config_path,
    )

    written_path = write_database_settings(database_settings, preferences=preferences_settings)

    assert written_path == config_path
    content = config_path.read_text(encoding="utf-8")
    assert 'url = "sqlite+aiosqlite:///lifeos.db"' in content
    assert "schema =" not in content


def test_require_database_url_raises_helpful_error(tmp_path: Path) -> None:
    config_path = tmp_path / "missing-config.toml"
    settings = DatabaseSettings.from_env({"LIFEOS_CONFIG_FILE": str(config_path)})

    try:
        settings.require_database_url()
    except ConfigurationError as exc:
        assert "lifeos init" in str(exc)
    else:
        raise AssertionError("missing database URL should fail")


def test_validate_timezone_name_rejects_unknown_values() -> None:
    try:
        validate_timezone_name("Mars/Base")
    except ConfigurationError as exc:
        assert "IANA timezone" in str(exc)
    else:
        raise AssertionError("invalid timezone should fail validation")


def test_validate_language_accepts_bcp47_like_values() -> None:
    assert validate_language("zh_Hans.UTF-8") == "zh-Hans"
    assert validate_language("auto") == "auto"


def test_validate_web_preferences_reject_invalid_values() -> None:
    assert validate_calendar_first_day_of_week("7") == 7
    assert validate_calendar_system("mayan_13_moon") == "mayan_13_moon"
    assert validate_calendar_seven_year_anchor_date("2026-07-20") == "2026-07-20"
    assert validate_navigation_visible_modules(["visions", "notes", "visions"]) == (
        "visions",
        "notes",
    )
    assert validate_notes_card_min_collapsed_lines("9") == 9
    assert validate_tasks_default_planning_preset("this_week") == "this_week"
    assert (
        validate_todos_default_inbox_vision("11111111-1111-1111-1111-111111111111")
        == "11111111-1111-1111-1111-111111111111"
    )

    invalid_cases = (
        lambda: validate_calendar_first_day_of_week("8"),
        lambda: validate_calendar_system("julian"),
        lambda: validate_calendar_seven_year_anchor_date("2026-02-31"),
        lambda: validate_navigation_visible_modules(["visions", "unknown"]),
        lambda: validate_notes_card_min_collapsed_lines("4"),
        lambda: validate_tasks_default_planning_preset("tomorrow"),
        lambda: validate_todos_default_inbox_vision("not-a-uuid"),
    )
    for invalid in invalid_cases:
        try:
            invalid()
        except ConfigurationError:
            pass
        else:
            raise AssertionError("invalid Web preference should fail validation")


def test_validate_navigation_visible_modules_normalizes_legacy_person_key() -> None:
    assert validate_navigation_visible_modules(["persons", "notes"]) == (
        "person",
        "notes",
    )


def test_detect_default_language_uses_environment() -> None:
    assert detect_default_language({"LANG": "zh_Hans.UTF-8"}) == "zh-Hans"


def test_validate_day_starts_at_rejects_invalid_values() -> None:
    try:
        validate_day_starts_at("24:30")
    except ConfigurationError as exc:
        assert "HH:MM" in str(exc)
    else:
        raise AssertionError("invalid day start should fail validation")


def test_validate_week_starts_on_rejects_invalid_values() -> None:
    try:
        validate_week_starts_on("friday")
    except ConfigurationError as exc:
        assert "monday" in str(exc)
        assert "sunday" in str(exc)
    else:
        raise AssertionError("invalid week start should fail validation")


def test_validate_vision_experience_rate_per_hour_rejects_invalid_values() -> None:
    assert validate_vision_experience_rate_per_hour("60") == 60

    try:
        validate_vision_experience_rate_per_hour("0")
    except ConfigurationError as exc:
        assert "between 1 and 3600" in str(exc)
    else:
        raise AssertionError("invalid vision experience rate should fail")


def test_validate_theme_rejects_invalid_values() -> None:
    assert validate_theme("night") == "night"

    try:
        validate_theme("unknown")
    except ConfigurationError as exc:
        assert "Preference `theme`" in str(exc)
        assert "system" in str(exc)
    else:
        raise AssertionError("invalid theme should fail")


def test_parse_boolean_value_rejects_invalid_values() -> None:
    assert parse_boolean_value("true", field_name="Config key `database.echo`") is True
    assert parse_boolean_value("0", field_name="Config key `database.echo`") is False

    try:
        parse_boolean_value("maybe", field_name="Config key `database.echo`")
    except ConfigurationError as exc:
        assert "true, false" in str(exc)
    else:
        raise AssertionError("invalid boolean string should fail")


def test_write_database_settings_can_write_preferences_without_database_url(tmp_path: Path) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    database_settings = DatabaseSettings(
        database_url=None,
        database_schema="lifeos",
        database_echo=False,
        config_file=config_path,
    )
    preferences_settings = PreferencesSettings(
        timezone="America/Toronto",
        language="zh-Hans",
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=90,
        config_file=config_path,
    )

    written_path = write_database_settings(database_settings, preferences=preferences_settings)

    assert written_path == config_path
    content = config_path.read_text(encoding="utf-8")
    assert "[database]" in content
    assert "url =" not in content
    assert 'schema = "lifeos"' in content
    assert 'timezone = "America/Toronto"' in content
    assert 'theme = "system"' in content


def test_write_database_settings_persists_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    database_settings = DatabaseSettings(
        database_url="postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
        database_schema="lifeos",
        database_echo=False,
        config_file=config_path,
    )
    preferences_settings = PreferencesSettings(
        timezone="America/Toronto",
        language="zh-Hans",
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=90,
        config_file=config_path,
    )

    written_path = write_database_settings(database_settings, preferences=preferences_settings)

    assert written_path == config_path
    content = config_path.read_text(encoding="utf-8")
    assert "[database]" in content
    assert "[preferences]" in content
    assert 'url = "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"' in content
    assert 'timezone = "America/Toronto"' in content
    assert "vision_experience_rate_per_hour = 90" in content
    assert 'theme = "system"' in content


def test_write_database_settings_preserves_other_top_level_sections(tmp_path: Path) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            (
                "# Existing file header",
                "[database]",
                'url = "postgresql+psycopg://old-user:<old-password>@localhost:5432/old_lifeos"',
                'schema = "old_schema"',
                "echo = true",
                "",
                "[preferences]",
                'timezone = "UTC"',
                'language = "en"',
                'day_starts_at = "00:00"',
                'week_starts_on = "monday"',
                "vision_experience_rate_per_hour = 60",
                "",
                "[notes]",
                'default_editor = "nvim"',
                "",
            )
        ),
        encoding="utf-8",
    )
    database_settings = DatabaseSettings(
        database_url="postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
        database_schema="lifeos_dev",
        database_echo=False,
        config_file=config_path,
    )
    preferences_settings = PreferencesSettings(
        timezone="America/Toronto",
        language="zh-Hans",
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=120,
        config_file=config_path,
    )

    written_path = write_database_settings(database_settings, preferences=preferences_settings)

    assert written_path == config_path
    content = config_path.read_text(encoding="utf-8")
    assert "# Existing file header" in content
    assert "[notes]" in content
    assert 'default_editor = "nvim"' in content
    assert 'schema = "lifeos_dev"' in content
    assert 'timezone = "America/Toronto"' in content
    assert 'language = "zh-Hans"' in content
    assert "vision_experience_rate_per_hour = 120" in content
    assert (
        'url = "postgresql+psycopg://old-user:<old-password>@localhost:5432/old_lifeos"'
        not in content
    )


def test_set_runtime_config_value_rejects_backend_switch_between_postgresql_and_sqlite(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "postgresql+psycopg://localhost/lifeos"',
                'schema = "lifeos_dev"',
                "echo = false",
                "",
                "[preferences]",
                'timezone = "UTC"',
                'language = "en"',
                'day_starts_at = "00:00"',
                'week_starts_on = "monday"',
                "vision_experience_rate_per_hour = 60",
                "",
            )
        ),
        encoding="utf-8",
    )

    try:
        set_runtime_config_value(
            key="database.url",
            value="sqlite+aiosqlite:///tmp/lifeos.db",
        )
    except ConfigurationError as exc:
        assert "Switching between PostgreSQL and SQLite" in str(exc)
        assert "lifeos init --database-url" in str(exc)
    else:
        raise AssertionError("cross-backend config set should fail")

    content = config_path.read_text(encoding="utf-8")
    assert 'url = "postgresql+psycopg://localhost/lifeos"' in content
    assert 'schema = "lifeos_dev"' in content


def test_set_runtime_config_value_updates_sqlite_url_within_same_backend(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "sqlite+aiosqlite:///tmp/old-lifeos.db"',
                "echo = false",
                "",
                "[preferences]",
                'timezone = "UTC"',
                'language = "en"',
                'day_starts_at = "00:00"',
                'week_starts_on = "monday"',
                "vision_experience_rate_per_hour = 60",
                "",
            )
        ),
        encoding="utf-8",
    )

    result = set_runtime_config_value(
        key="database.url",
        value="sqlite+aiosqlite:///tmp/new-lifeos.db",
    )

    assert result.database_settings.database_url == "sqlite+aiosqlite:///tmp/new-lifeos.db"
    assert result.database_settings.database_schema is None
    content = config_path.read_text(encoding="utf-8")
    assert 'url = "sqlite+aiosqlite:///tmp/new-lifeos.db"' in content
    assert "schema =" not in content


def test_set_runtime_config_value_updates_theme_preference(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'schema = "lifeos"',
                "echo = false",
                "",
                "[preferences]",
                'timezone = "UTC"',
                'language = "en"',
                'day_starts_at = "00:00"',
                'week_starts_on = "monday"',
                "vision_experience_rate_per_hour = 60",
                "",
            )
        ),
        encoding="utf-8",
    )

    result = set_runtime_config_value(key="preferences.theme", value="night")

    assert result.preferences_settings.theme == "night"
    assert 'theme = "night"' in config_path.read_text(encoding="utf-8")


def test_set_runtime_config_value_updates_web_preferences(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'schema = "lifeos"',
                "echo = false",
                "",
                "[preferences]",
                'timezone = "UTC"',
                'language = "en"',
                'day_starts_at = "00:00"',
                'week_starts_on = "monday"',
                "vision_experience_rate_per_hour = 60",
                "",
            )
        ),
        encoding="utf-8",
    )

    set_runtime_config_value(
        key="preferences.navigation_visible_modules",
        value="visions,notes,settings",
    )
    set_runtime_config_value(
        key="preferences.notes_card_min_collapsed_lines",
        value="11",
    )
    set_runtime_config_value(
        key="preferences.todos_default_inbox_vision",
        value="11111111-1111-1111-1111-111111111111",
    )

    content = config_path.read_text(encoding="utf-8")
    assert 'navigation_visible_modules = ["visions", "notes", "settings"]' in content
    assert "notes_card_min_collapsed_lines = 11" in content
    assert 'todos_default_inbox_vision = "11111111-1111-1111-1111-111111111111"' in content


def test_build_database_settings_uses_injected_prompts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone=None,
        language=None,
        day_starts_at=None,
        week_starts_on=None,
        vision_experience_rate_per_hour=None,
        non_interactive=False,
        is_interactive=True,
        prompts=InitializationPrompts(
            prompt_database_url=lambda default: (
                "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"
            ),
            prompt_database_schema=lambda default: "lifeos_dev",
            prompt_language=lambda default: "zh-Hans",
            prompt_database_echo=lambda default: True,
        ),
    )
    monkeypatch.setattr(
        "lifeos_cli.application.configuration.ensure_database_driver_available",
        lambda database_url: None,
    )

    settings = build_database_settings(request)

    assert (
        settings.database_url == "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"
    )
    assert settings.database_schema == "lifeos_dev"
    assert settings.database_echo is True
    assert settings.config_file == config_path


def test_build_preferences_settings_uses_explicit_values(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone="America/Toronto",
        language="zh-Hans",
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=120,
        non_interactive=True,
        is_interactive=False,
        prompts=None,
    )

    settings = build_preferences_settings(request)

    assert settings.timezone == "America/Toronto"
    assert settings.language == "zh-Hans"
    assert settings.day_starts_at == "04:00"
    assert settings.week_starts_on == "sunday"
    assert settings.vision_experience_rate_per_hour == 120
    assert settings.config_file == config_path


def test_build_preferences_settings_preserves_existing_web_preferences(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    config_path.write_text(
        "\n".join(
            (
                "[preferences]",
                'timezone = "UTC"',
                'language = "en"',
                'day_starts_at = "00:00"',
                'week_starts_on = "monday"',
                "vision_experience_rate_per_hour = 60",
                'theme = "night"',
                "calendar_first_day_of_week = 7",
                'calendar_system = "mayan_13_moon"',
                'calendar_seven_year_anchor_date = "2026-07-20"',
                'navigation_visible_modules = ["visions", "notes", "settings"]',
                "notes_card_min_collapsed_lines = 11",
                "notes_export_planning_include_cycle_notes = true",
                "notes_export_planning_include_task_notes = false",
                "planning_show_habit_actions = false",
                'tasks_default_planning_preset = "this_week"',
                "timelog_auto_set_task_planning = true",
                'todos_default_inbox_vision = "11111111-1111-1111-1111-111111111111"',
                "",
            )
        ),
        encoding="utf-8",
    )
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone="America/Toronto",
        language=None,
        day_starts_at=None,
        week_starts_on=None,
        vision_experience_rate_per_hour=None,
        non_interactive=True,
        is_interactive=False,
        prompts=None,
    )

    settings = build_preferences_settings(request)

    assert settings.timezone == "America/Toronto"
    assert settings.theme == "night"
    assert settings.calendar_first_day_of_week == 7
    assert settings.calendar_system == "mayan_13_moon"
    assert settings.calendar_seven_year_anchor_date == "2026-07-20"
    assert settings.navigation_visible_modules == ("visions", "notes", "settings")
    assert settings.notes_card_min_collapsed_lines == 11
    assert settings.notes_export_planning_include_cycle_notes is True
    assert settings.notes_export_planning_include_task_notes is False
    assert settings.planning_show_habit_actions is False
    assert settings.tasks_default_planning_preset == "this_week"
    assert settings.timelog_auto_set_task_planning is True
    assert settings.todos_default_inbox_vision == "11111111-1111-1111-1111-111111111111"


def test_build_preferences_settings_rejects_invalid_explicit_vision_experience_rate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone="America/Toronto",
        language="zh-Hans",
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=0,
        non_interactive=True,
        is_interactive=False,
        prompts=None,
    )

    try:
        build_preferences_settings(request)
    except ConfigurationError as exc:
        assert "between 1 and 3600" in str(exc)
    else:
        raise AssertionError("invalid vision experience rate should fail validation")


def test_build_preferences_settings_uses_environment_defaults(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("TZ", "America/Toronto")
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.setenv("LANG", "zh_Hans.UTF-8")
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone=None,
        language=None,
        day_starts_at=None,
        week_starts_on=None,
        vision_experience_rate_per_hour=None,
        non_interactive=True,
        is_interactive=False,
        prompts=None,
    )

    settings = build_preferences_settings(request)

    assert settings.timezone == "America/Toronto"
    assert settings.language == "zh-Hans"
    assert settings.day_starts_at == "00:00"
    assert settings.week_starts_on == "monday"
    assert settings.vision_experience_rate_per_hour == 60


def test_build_preferences_settings_uses_injected_language_prompt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "lifeos" / "config.toml"
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    request = InitializationRequest(
        database_url=None,
        schema=None,
        echo=None,
        timezone="America/Toronto",
        language=None,
        day_starts_at="04:00",
        week_starts_on="sunday",
        vision_experience_rate_per_hour=120,
        non_interactive=False,
        is_interactive=True,
        prompts=InitializationPrompts(
            prompt_database_url=lambda default: (
                "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"
            ),
            prompt_database_schema=lambda default: "lifeos",
            prompt_language=lambda default: "zh-Hans",
            prompt_database_echo=lambda default: False,
        ),
    )

    settings = build_preferences_settings(request)

    assert settings.timezone == "America/Toronto"
    assert settings.language == "zh-Hans"
    assert settings.day_starts_at == "04:00"
    assert settings.week_starts_on == "sunday"
    assert settings.vision_experience_rate_per_hour == 120
