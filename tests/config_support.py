from __future__ import annotations

from pathlib import Path

from lifeos_cli.config import clear_config_cache


def write_test_config(
    config_path: Path,
    *,
    include_database: bool = False,
    database_url: str = "postgresql+psycopg://localhost:5432/lifeos_test",
    database_schema: str | None = "lifeos_test",
    database_echo: bool = False,
    include_preferences: bool = False,
    timezone: str = "America/Toronto",
    language: str = "en",
    day_starts_at: str = "04:00",
    week_starts_on: str = "monday",
    calendar_system: str | None = None,
    mayan_new_year_start: str | None = None,
    seven_year_anchor_year: int | None = None,
    vision_experience_rate_per_hour: int | None = None,
    theme: str | None = None,
) -> Path:
    lines: list[str] = []
    if include_database:
        lines.extend(("[database]", f'url = "{database_url}"'))
        if database_schema is not None:
            lines.append(f'schema = "{database_schema}"')
        lines.extend((f"echo = {'true' if database_echo else 'false'}", ""))
    if include_preferences:
        lines.extend(
            (
                "[preferences]",
                f'timezone = "{timezone}"',
                f'language = "{language}"',
                f'day_starts_at = "{day_starts_at}"',
                f'week_starts_on = "{week_starts_on}"',
            )
        )
        if vision_experience_rate_per_hour is not None:
            lines.append(f"vision_experience_rate_per_hour = {vision_experience_rate_per_hour}")
        if theme is not None:
            lines.append(f'theme = "{theme}"')
        if calendar_system is not None:
            lines.append(f'calendar_system = "{calendar_system}"')
        if mayan_new_year_start is not None:
            lines.append(f'calendar_mayan_new_year_start = "{mayan_new_year_start}"')
        if seven_year_anchor_year is not None:
            lines.append(f"calendar_seven_year_anchor_year = {seven_year_anchor_year}")
        lines.append("")
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return config_path


def install_test_config(
    *,
    monkeypatch,
    tmp_path: Path,
    include_database: bool = False,
    database_url: str = "postgresql+psycopg://localhost:5432/lifeos_test",
    database_schema: str | None = "lifeos_test",
    database_echo: bool = False,
    include_preferences: bool = False,
    timezone: str = "America/Toronto",
    language: str = "en",
    day_starts_at: str = "04:00",
    week_starts_on: str = "monday",
    calendar_system: str | None = None,
    mayan_new_year_start: str | None = None,
    seven_year_anchor_year: int | None = None,
    vision_experience_rate_per_hour: int | None = None,
    theme: str | None = None,
) -> Path:
    config_path = write_test_config(
        tmp_path / "config.toml",
        include_database=include_database,
        database_url=database_url,
        database_schema=database_schema,
        database_echo=database_echo,
        include_preferences=include_preferences,
        timezone=timezone,
        language=language,
        day_starts_at=day_starts_at,
        week_starts_on=week_starts_on,
        calendar_system=calendar_system,
        mayan_new_year_start=mayan_new_year_start,
        seven_year_anchor_year=seven_year_anchor_year,
        vision_experience_rate_per_hour=vision_experience_rate_per_hour,
        theme=theme,
    )
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    return config_path
