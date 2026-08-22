from __future__ import annotations

import builtins
import getpass
from pathlib import Path

import pytest

from lifeos_cli import cli
from lifeos_cli.application import configuration as application_configuration
from lifeos_cli.cli_support.system import config_handlers
from lifeos_cli.config import ConfigurationError, clear_config_cache


def _noop_database_subcommand(*, subcommand: str) -> None:
    del subcommand


@pytest.fixture(autouse=True)
def _allow_postgres_url_logic_tests_without_driver(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    if request.node.name == "test_main_init_reports_missing_postgres_extra":
        return
    monkeypatch.setattr(
        application_configuration,
        "ensure_database_driver_available",
        lambda database_url: None,
    )


def test_main_init_non_interactive_writes_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )

    exit_code = cli.main(
        [
            "init",
            "--non-interactive",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
            "--timezone",
            "America/Toronto",
            "--language",
            "zh-Hans",
            "--day-starts-at",
            "04:00",
            "--week-starts-on",
            "sunday",
            "--vision-experience-rate-per-hour",
            "120",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Wrote config file:" in captured.out
    assert "Database URL: postgresql+psycopg://db-user:***@localhost:5432/lifeos" in captured.out
    assert "Preference timezone: America/Toronto" in captured.out
    assert "Preference language: zh-Hans" in captured.out
    assert "Payload language for agent-authored records: zh-Hans" in captured.out
    assert "Agent payload rule:" in captured.out
    assert "Preference vision experience rate per hour: 120" in captured.out
    content = config_path.read_text(encoding="utf-8")
    assert 'url = "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"' in content
    assert 'timezone = "America/Toronto"' in content
    assert 'language = "zh-Hans"' in content
    assert 'day_starts_at = "04:00"' in content
    assert 'week_starts_on = "sunday"' in content
    assert "vision_experience_rate_per_hour = 120" in content
    clear_config_cache()


def test_main_init_non_interactive_defaults_to_sqlite_when_database_url_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    database_path = config_path.parent / "lifeos.db"
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )

    exit_code = cli.main(
        [
            "init",
            "--non-interactive",
            "--skip-ping",
            "--skip-migrate",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Database URL: sqlite+aiosqlite:///{database_path}" in captured.out
    assert "Database schema:" not in captured.out
    content = config_path.read_text(encoding="utf-8")
    assert f'url = "sqlite+aiosqlite:///{database_path}"' in content
    assert "schema =" not in content
    clear_config_cache()


def test_main_init_does_not_prompt_for_explicit_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    prompts: list[str] = []
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )
    monkeypatch.setattr(config_handlers.sys.stdin, "isatty", lambda: True)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        if prompt.startswith("Database schema"):
            return ""
        if prompt.startswith("Preferred language tag for human-authored payloads"):
            return ""
        if prompt.startswith("Enable SQL echo logging"):
            return ""
        raise AssertionError(f"unexpected prompt: {prompt}")

    monkeypatch.setattr(builtins, "input", fake_input)

    exit_code = cli.main(
        [
            "init",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Wrote config file:" in captured.out
    assert all(not prompt.startswith("Database URL") for prompt in prompts)
    assert any(prompt.startswith("Database schema") for prompt in prompts)
    assert any(
        prompt.startswith("Preferred language tag for human-authored payloads")
        for prompt in prompts
    )
    clear_config_cache()


def test_main_init_sqlite_does_not_prompt_for_schema_or_write_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    prompts: list[str] = []
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )
    monkeypatch.setattr(config_handlers.sys.stdin, "isatty", lambda: True)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        if prompt.startswith("Preferred language tag for human-authored payloads"):
            return ""
        if prompt.startswith("Enable SQL echo logging"):
            return ""
        raise AssertionError(f"unexpected prompt: {prompt}")

    monkeypatch.setattr(builtins, "input", fake_input)

    exit_code = cli.main(
        [
            "init",
            "--database-url",
            "sqlite+aiosqlite:///lifeos.db",
            "--skip-ping",
            "--skip-migrate",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Database URL: sqlite+aiosqlite:///lifeos.db" in captured.out
    assert "Database schema:" not in captured.out
    assert all(not prompt.startswith("Database schema") for prompt in prompts)
    assert "schema =" not in config_path.read_text(encoding="utf-8")
    clear_config_cache()


def test_main_init_interactive_accepts_default_sqlite_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    database_path = config_path.parent / "lifeos.db"
    prompts: list[str] = []
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )
    monkeypatch.setattr(config_handlers.sys.stdin, "isatty", lambda: True)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(builtins, "input", fake_input)

    def fake_secret_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(getpass, "getpass", fake_secret_input)

    exit_code = cli.main(
        [
            "init",
            "--skip-ping",
            "--skip-migrate",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert prompts[0] == (
        f"Database URL (hidden input) [default: sqlite+aiosqlite:///{database_path}]: "
    )
    assert "Database schema:" not in captured.out
    assert all(not prompt.startswith("Database schema") for prompt in prompts)
    assert f'url = "sqlite+aiosqlite:///{database_path}"' in config_path.read_text(encoding="utf-8")
    clear_config_cache()


def test_main_init_reports_missing_postgres_extra(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    def raise_missing_postgres_extra(database_url: str) -> None:
        del database_url
        raise ConfigurationError(
            "PostgreSQL support is not installed. Install the `postgres` extra, for example: "
            'uv tool install --upgrade "lifeos-cli[postgres]".'
        )

    monkeypatch.setattr(
        application_configuration,
        "ensure_database_driver_available",
        raise_missing_postgres_extra,
    )

    exit_code = cli.main(
        [
            "init",
            "--non-interactive",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "lifeos-cli[postgres]" in captured.err
    assert not config_path.exists()
    clear_config_cache()


def test_main_init_reprompts_invalid_schema_in_interactive_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    prompts: list[str] = []
    responses = iter(["lifeos-dev", "lifeos_dev", "", "", ""])
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )
    monkeypatch.setattr(config_handlers.sys.stdin, "isatty", lambda: True)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(builtins, "input", fake_input)

    exit_code = cli.main(
        [
            "init",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
            "--skip-ping",
            "--skip-migrate",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "lifeos_dev" in config_path.read_text(encoding="utf-8")
    assert "Use `lifeos_dev` instead of `lifeos-dev`." in captured.err
    assert sum(prompt.startswith("Database schema") for prompt in prompts) == 2
    clear_config_cache()


def test_main_init_rejects_invalid_schema_non_interactively(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(
        [
            "init",
            "--non-interactive",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
            "--schema",
            "lifeos-dev",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use `lifeos_dev` instead of `lifeos-dev`." in captured.err
    assert not config_path.exists()
    clear_config_cache()


def test_main_config_show_masks_database_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"',
                'schema = "lifeos"',
                "echo = false",
                "",
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
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(["config", "show"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Database URL: postgresql+psycopg://db-user:***@localhost:5432/lifeos" in captured.out
    assert "<db-password>" not in captured.out
    assert "Preference timezone: America/Toronto" in captured.out
    assert "Preference language: zh-Hans" in captured.out
    assert "Payload language for agent-authored records: zh-Hans" in captured.out
    assert "Agent payload rule:" in captured.out
    assert "Preference day starts at: 04:00" in captured.out
    assert "Preference week starts on: sunday" in captured.out
    assert "Preference vision experience rate per hour: 90" in captured.out
    clear_config_cache()


def test_main_config_update_updates_preference_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
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
                "[notes]",
                'default_editor = "nvim"',
                "",
            )
        ),
        encoding="utf-8",
    )
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(["config", "update", "preferences.timezone", "America/Toronto"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated key: preferences.timezone" in captured.out
    assert "Preference timezone: America/Toronto" in captured.out
    content = config_path.read_text(encoding="utf-8")
    assert 'timezone = "America/Toronto"' in content
    assert "[notes]" in content
    assert 'default_editor = "nvim"' in content
    clear_config_cache()


def test_main_config_update_rejects_deployment_scoped_database_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'schema = "lifeos"',
                "echo = false",
                "",
            )
        ),
        encoding="utf-8",
    )
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(["config", "update", "database.schema", "lifeos_dev"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "deployment-scoped" in captured.err
    assert "lifeos init --schema <name>" in captured.err
    assert 'schema = "lifeos"' in config_path.read_text(encoding="utf-8")
    clear_config_cache()


def test_main_config_update_updates_database_echo_strictly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"',
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
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(["config", "update", "database.echo", "true"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Database echo: true" in captured.out
    assert "db-user:***" in captured.out
    assert "echo = true" in config_path.read_text(encoding="utf-8")
    clear_config_cache()


def test_main_config_update_rejects_unknown_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(["config", "update", "preferences.unknown", "value"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Unsupported config key" in captured.err
    assert not config_path.exists()
    clear_config_cache()


def test_main_config_update_ignores_runtime_env_overrides_when_persisting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'schema = "lifeos"',
                "echo = false",
                "",
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
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")

    exit_code = cli.main(["config", "update", "preferences.language", "en-CA"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated key: preferences.language" in captured.out
    content = config_path.read_text(encoding="utf-8")
    assert 'timezone = "America/Toronto"' in content
    assert 'language = "en-CA"' in content
    clear_config_cache()


def test_main_config_update_updates_theme(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'schema = "lifeos"',
                "echo = false",
                "",
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
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))

    exit_code = cli.main(["config", "update", "preferences.theme", "night"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated key: preferences.theme" in captured.out
    assert "Preference theme: night" in captured.out
    assert 'theme = "night"' in config_path.read_text(encoding="utf-8")
    clear_config_cache()


def test_main_init_can_repair_invalid_existing_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            (
                "[database]",
                'url = "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos"',
                'schema = ""',
                "echo = false",
                "",
            )
        ),
        encoding="utf-8",
    )
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    monkeypatch.setattr(
        config_handlers,
        "run_configured_database_subcommand_in_subprocess",
        _noop_database_subcommand,
    )

    exit_code = cli.main(
        [
            "init",
            "--non-interactive",
            "--database-url",
            "postgresql+psycopg://db-user:<db-password>@localhost:5432/lifeos",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Wrote config file:" in captured.out
    rewritten = config_path.read_text(encoding="utf-8")
    assert 'schema = "lifeos"' in rewritten
    assert "[preferences]" in rewritten
    clear_config_cache()
