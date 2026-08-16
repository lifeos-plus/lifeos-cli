from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.application.serialization import to_jsonable
from lifeos_cli.cli_support.json_output import print_json_payload
from lifeos_cli.config import DatabaseSettings, PreferencesSettings
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import (
    areas,
    notes,
    planning_lifecycle,
    schedules,
    tasks,
    timelogs,
    visions,
)
from tests.support import make_record, make_session_scope, utc_datetime


def test_json_output_flag_is_documented_in_read_command_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["area", "list", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "--json" in captured.out
    assert "structured JSON output" in captured.out


def test_area_list_json_prints_one_object_per_record(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_areas(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                deleted_at=None,
                is_active=True,
                display_order=10,
                name="Health",
                description=None,
                color="#3B82F6",
                icon=None,
                created_at=utc_datetime(2026, 4, 10, 12, 0),
                updated_at=utc_datetime(2026, 4, 10, 12, 0),
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(areas, "list_areas", fake_list_areas)

    exit_code = cli.main(["area", "list", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == [
        {
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "deleted_at": None,
            "is_active": True,
            "display_order": 10,
            "name": "Health",
            "description": None,
            "color": "#3B82F6",
            "icon": None,
            "created_at": "2026-04-10T12:00:00Z",
            "updated_at": "2026-04-10T12:00:00Z",
        }
    ]


def test_area_show_json_prints_one_object(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_area(_session: object, **_kwargs: object) -> object:
        return make_record(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            name="Health",
            deleted_at=None,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(areas, "get_area", fake_get_area)

    exit_code = cli.main(["area", "show", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert payload["name"] == "Health"


def test_empty_list_json_prints_empty_array(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_visions(_session: object, **_kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(visions, "list_visions", fake_list_visions)

    exit_code = cli.main(["vision", "list", "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == []


def test_note_search_json_preserves_full_content(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_content = "first line\nsecond line\n\n  spaced  content  "

    async def fake_search_notes(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                content=original_content,
                created_at=utc_datetime(2026, 4, 10),
                updated_at=utc_datetime(2026, 4, 10),
                deleted_at=None,
                tags=(),
                people=(),
                tasks=(),
                visions=(),
                events=(),
                timelogs=(),
                habit_actions=(),
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(notes, "search_notes", fake_search_notes)

    exit_code = cli.main(["note", "search", "first", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload[0]["content"] == original_content
    assert "\n" in payload[0]["content"]


def test_timelog_list_json_with_count_emits_items_and_total(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_timelogs(_session: object, **_kwargs: object) -> list[object]:
        return [make_record(id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"), title="Deep work")]

    async def fake_count_timelogs(_session: object, **_kwargs: object) -> int:
        return 7

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(timelogs, "list_timelogs", fake_list_timelogs)
    monkeypatch.setattr(timelogs, "count_timelogs", fake_count_timelogs)

    exit_code = cli.main(["timelog", "list", "--json", "--count"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["total_count"] == 7
    assert payload["items"][0]["id"] == "cccccccc-cccc-cccc-cccc-cccccccccccc"


def test_default_text_output_remains_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_areas(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                deleted_at=None,
                is_active=True,
                display_order=10,
                name="Health",
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(areas, "list_areas", fake_list_areas)

    exit_code = cli.main(["area", "list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "area_id\tstatus\tdisplay_order\tname" in captured.out
    assert "Health" in captured.out


def test_json_output_preserves_unicode_and_decimal_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_json_payload(
        make_record(
            name="健康",
            amount=Decimal("1.23000000"),
            timestamp=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        )
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["name"] == "健康"
    assert payload["amount"] == "1.23000000"
    assert payload["timestamp"] == "2026-04-10T12:00:00Z"


def test_to_jsonable_serializes_datetime_with_utc_suffix() -> None:
    assert to_jsonable(utc_datetime(2026, 4, 10, 12, 0)) == "2026-04-10T12:00:00Z"


def test_schedule_show_json_emits_structured_day(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_reconcile(_session: object, **_kwargs: object) -> None:
        return None

    async def fake_get_day(_session: object, **_kwargs: object) -> object:
        return make_record(
            local_date=date(2026, 4, 10),
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        planning_lifecycle,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile,
    )
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_day)

    exit_code = cli.main(["schedule", "show", "--date", "2026-04-10", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["local_date"] == "2026-04-10"
    assert payload["tasks"] == []


def test_schedule_list_json_emits_structured_days(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_reconcile(_session: object, **_kwargs: object) -> None:
        return None

    async def fake_get_day(_session: object, **_kwargs: object) -> object:
        return make_record(
            local_date=date(2026, 4, 10),
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        planning_lifecycle,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile,
    )
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_day)

    exit_code = cli.main(["schedule", "list", "--date", "2026-04-10", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert len(payload) == 1
    assert payload[0]["local_date"] == "2026-04-10"


def test_planning_show_json_emits_structured_view(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_view(_session: object, **_kwargs: object) -> object:
        return make_record(
            cycle_type="week",
            period_start=date(2026, 4, 13),
            period_end=date(2026, 4, 19),
            total_tasks=0,
            roots=(),
            context_root_ids=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tasks, "get_planning_view", fake_get_view)

    exit_code = cli.main(
        ["planning", "show", "--cycle-type", "week", "--at", "2026-04-15", "--json"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["cycle_type"] == "week"
    assert payload["period_start"] == "2026-04-13"
    assert payload["total_tasks"] == 0


def test_config_show_json_masks_secrets_by_default(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = Path("/tmp/lifeos-config.toml")
    monkeypatch.setattr(
        "lifeos_cli.cli_support.system.config_handlers.get_database_settings",
        lambda: DatabaseSettings(
            database_url="postgresql://user:super-secret@localhost/lifeos",  # pragma: allowlist secret  # noqa: E501
            database_schema="main",
            database_echo=False,
            config_file=config_file,
        ),
    )
    monkeypatch.setattr(
        "lifeos_cli.cli_support.system.config_handlers.get_preferences_settings",
        lambda: PreferencesSettings(
            timezone="Asia/Shanghai",
            language="zh-Hans",
            day_starts_at="04:00",
            week_starts_on="monday",
            vision_experience_rate_per_hour=1,
            config_file=config_file,
        ),
    )

    exit_code = cli.main(["config", "show", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["database_schema"] == "main"
    assert "super-secret" not in payload["database_url"]
    assert payload["preferences"]["timezone"] == "Asia/Shanghai"


def test_config_show_json_show_secrets_emits_full_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_file = Path("/tmp/lifeos-config.toml")
    monkeypatch.setattr(
        "lifeos_cli.cli_support.system.config_handlers.get_database_settings",
        lambda: DatabaseSettings(
            database_url="postgresql://user:super-secret@localhost/lifeos",  # pragma: allowlist secret  # noqa: E501
            database_schema=None,
            database_echo=True,
            config_file=config_file,
        ),
    )
    monkeypatch.setattr(
        "lifeos_cli.cli_support.system.config_handlers.get_preferences_settings",
        lambda: PreferencesSettings(
            timezone="Asia/Shanghai",
            language="en",
            day_starts_at="04:00",
            week_starts_on="monday",
            vision_experience_rate_per_hour=1,
            config_file=config_file,
        ),
    )

    exit_code = cli.main(["config", "show", "--json", "--show-secrets"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "super-secret" in payload["database_url"]
    assert "database_schema" not in payload
