"""CLI-level tests for the habit-action resource."""

from __future__ import annotations

from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.cli_support.help_audit import build_machine_readable_reference
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import habit_actions as habit_action_services
from tests.support import make_record, make_session_scope

ACTION_UUID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_habit_action_delete_and_batch_are_part_of_machine_reference() -> None:
    reference = build_machine_readable_reference(cli.build_parser())
    paths = {tuple(command["path"]) for command in reference["commands"]}

    assert ("habit-action", "delete") in paths
    assert ("habit-action", "batch", "delete") in paths


def test_habit_action_delete_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete(_session: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habit_action_services, "delete_habit_action", fake_delete)

    exit_code = cli.main(["habit-action", "delete", str(ACTION_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Soft-deleted habit action {ACTION_UUID}" in captured.out


def test_habit_action_delete_missing_prints_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete(_session: object, **_kwargs: object) -> None:
        raise habit_action_services.HabitActionNotFoundError(
            f"Habit action {ACTION_UUID} was not found"
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habit_action_services, "delete_habit_action", fake_delete)

    exit_code = cli.main(["habit-action", "delete", str(ACTION_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "was not found" in captured.err


def test_habit_action_batch_delete_prints_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_batch_delete(_session: object, **_kwargs: object) -> object:
        return make_record(deleted_count=1, failed_ids=(), errors=())

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(habit_action_services, "batch_delete_habit_actions", fake_batch_delete)

    exit_code = cli.main(["habit-action", "batch", "delete", "--ids", str(ACTION_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Deleted habit actions: 1" in captured.out
