from __future__ import annotations

import argparse
from functools import partial
from pathlib import Path

import pytest

from lifeos_cli.cli_support import runtime_utils
from lifeos_cli.cli_support.runtime_utils import make_sync_handler


async def _sample_async_handler(
    args: argparse.Namespace,
    *,
    offset: int,
) -> int:
    return int(args.value) + offset


def test_make_sync_handler_supports_partials() -> None:
    handler = make_sync_handler(partial(_sample_async_handler, offset=2))

    assert handler(argparse.Namespace(value=3)) == 5
    assert handler.__name__ == "_sample_async_handler".removesuffix("_async")


def test_print_database_runtime_error_redacts_original_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "config.toml"
    db_password = "supersecret"  # pragma: allowlist secret
    database_url = f"postgresql+psycopg://db-user:{db_password}@db.example/lifeos"
    config_path.write_text(
        f'[database]\nurl = "{database_url}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(config_path))
    runtime_utils.get_database_settings.cache_clear()

    exit_code = runtime_utils.print_database_runtime_error(
        RuntimeError("connect supersecret to db.example failed")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "supersecret" not in captured.err
    assert "Original error:" not in captured.err
    assert "Error type: RuntimeError" in captured.err
    runtime_utils.get_database_settings.cache_clear()
