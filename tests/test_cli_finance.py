"""CLI-level tests for the finance command namespace."""

from __future__ import annotations

import json
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.cli_support.help_audit import build_machine_readable_reference
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import finance as finance_services
from tests.support import make_record, make_session_scope, utc_datetime

ASSET_UUID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TREE_UUID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
NODE_UUID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SNAPSHOT_UUID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
RATE_SNAPSHOT_UUID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def test_finance_nested_commands_are_part_of_machine_reference() -> None:
    reference = build_machine_readable_reference(cli.build_parser())
    paths = {tuple(command["path"]) for command in reference["commands"]}

    for path in (
        ("finance", "asset", "add"),
        ("finance", "asset", "show"),
        ("finance", "tree", "update"),
        ("finance", "tree", "delete"),
        ("finance", "node", "list"),
        ("finance", "node", "show"),
        ("finance", "snapshot", "update"),
        ("finance", "snapshot", "delete"),
        ("finance", "rate-snapshot", "update"),
        ("finance", "rate-snapshot", "delete"),
    ):
        assert path in paths


def test_finance_asset_show_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_asset(_session: object, **_kwargs: object) -> object:
        return make_record(
            id=ASSET_UUID,
            code="BTC",
            name="Bitcoin",
            decimal_places=8,
            display_order=40,
            created_at=utc_datetime(2026, 1, 1),
            updated_at=utc_datetime(2026, 1, 2),
            deleted_at=None,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "get_finance_asset", fake_get_asset)

    exit_code = cli.main(["finance", "asset", "show", str(ASSET_UUID), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["id"] == str(ASSET_UUID)
    assert payload["code"] == "BTC"
    assert payload["decimal_places"] == 8


def test_finance_asset_show_missing_prints_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_asset(_session: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "get_finance_asset", fake_get_asset)

    exit_code = cli.main(["finance", "asset", "show", str(ASSET_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "was not found" in captured.err


def test_finance_node_list_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_nodes(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=NODE_UUID,
                tree_id=TREE_UUID,
                parent_id=None,
                name="Cash",
                currency_code=None,
                depth=0,
                display_order=1,
                children_count=0,
                created_at=utc_datetime(2026, 1, 1),
                updated_at=utc_datetime(2026, 1, 1),
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "list_finance_nodes", fake_list_nodes)

    exit_code = cli.main(["finance", "node", "list", "--tree-id", str(TREE_UUID), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload[0]["id"] == str(NODE_UUID)
    assert payload[0]["name"] == "Cash"


def test_finance_node_show_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_node(_session: object, **_kwargs: object) -> object:
        return make_record(
            id=NODE_UUID,
            tree_id=TREE_UUID,
            parent_id=None,
            name="Cash",
            currency_code=None,
            depth=0,
            display_order=1,
            children_count=0,
            created_at=utc_datetime(2026, 1, 1),
            updated_at=utc_datetime(2026, 1, 1),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "get_finance_node", fake_get_node)

    exit_code = cli.main(["finance", "node", "show", str(NODE_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "name: Cash" in captured.out
    assert "tree_id:" in captured.out


def test_finance_tree_update_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_tree(_session: object, **_kwargs: object) -> object:
        return make_record(id=TREE_UUID)

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "update_finance_tree", fake_update_tree)

    exit_code = cli.main(
        [
            "finance",
            "tree",
            "update",
            str(TREE_UUID),
            "--name",
            "Personal",
            "--default",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Updated finance tree {TREE_UUID}" in captured.out


def test_finance_tree_delete_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete_tree(_session: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "delete_finance_tree", fake_delete_tree)

    exit_code = cli.main(["finance", "tree", "delete", str(TREE_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Soft-deleted finance tree {TREE_UUID}" in captured.out


def test_finance_snapshot_update_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_snapshot(_session: object, **_kwargs: object) -> object:
        return make_record(id=SNAPSHOT_UUID)

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "update_finance_snapshot", fake_update_snapshot)

    exit_code = cli.main(["finance", "snapshot", "update", str(SNAPSHOT_UUID), "--title", "June"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Updated finance snapshot {SNAPSHOT_UUID}" in captured.out


def test_finance_snapshot_delete_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete_snapshot(_session: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(finance_services, "delete_finance_snapshot", fake_delete_snapshot)

    exit_code = cli.main(["finance", "snapshot", "delete", str(SNAPSHOT_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Soft-deleted finance snapshot {SNAPSHOT_UUID}" in captured.out


def test_finance_rate_snapshot_update_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_rate_snapshot(_session: object, **_kwargs: object) -> object:
        return make_record(id=RATE_SNAPSHOT_UUID)

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        finance_services,
        "update_finance_rate_snapshot",
        fake_update_rate_snapshot,
    )

    exit_code = cli.main(
        ["finance", "rate-snapshot", "update", str(RATE_SNAPSHOT_UUID), "--note", "July"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Updated finance rate snapshot {RATE_SNAPSHOT_UUID}" in captured.out


def test_finance_rate_snapshot_delete_prints_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete_rate_snapshot(_session: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        finance_services,
        "delete_finance_rate_snapshot",
        fake_delete_rate_snapshot,
    )

    exit_code = cli.main(["finance", "rate-snapshot", "delete", str(RATE_SNAPSHOT_UUID)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Soft-deleted finance rate snapshot {RATE_SNAPSHOT_UUID}" in captured.out
