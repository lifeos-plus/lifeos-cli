from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import (
    areas,
    events,
    person,
    tags,
    visions,
)
from tests.support import make_record, make_session_scope, utc_datetime


def test_main_area_add_creates_area(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_area(_session: object, **kwargs: object) -> object:
        assert kwargs["name"] == "Health"
        return make_record(id=UUID("11111111-1111-1111-1111-111111111111"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(areas, "create_area", fake_create_area)

    exit_code = cli.main(["area", "add", "Health"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created area 11111111-1111-1111-1111-111111111111" in captured.out


def test_main_area_update_rejects_conflicting_clear_icon_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "area",
            "update",
            "11111111-1111-1111-1111-111111111111",
            "--icon",
            "brain",
            "--clear-icon",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --icon or --clear-icon, not both." in captured.err


def test_main_summary_list_commands_print_headers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")

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

    async def fake_list_person(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                deleted_at=None,
                name="Alice",
                location="Toronto",
                tags=[make_record(name="family"), make_record(name="friend")],
            )
        ]

    async def fake_list_visions(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
                deleted_at=None,
                status="active",
                area_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
                name="Launch lifeos-cli",
            )
        ]

    async def fake_list_tags(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
                deleted_at=None,
                entity_type="task",
                category="priority",
                name="urgent",
            )
        ]

    async def fake_list_events(_session: object, **_kwargs: object) -> list[object]:
        return [
            make_record(
                id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
                deleted_at=None,
                status="planned",
                event_type="deadline",
                start_time=utc_datetime(2026, 4, 10, 13, 0),
                end_time=utc_datetime(2026, 4, 10, 14, 0),
                task_id=None,
                title="Ship release",
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(areas, "list_areas", fake_list_areas)
    monkeypatch.setattr(person, "list_person", fake_list_person)
    monkeypatch.setattr(visions, "list_visions", fake_list_visions)
    monkeypatch.setattr(tags, "list_tags", fake_list_tags)
    monkeypatch.setattr(events, "list_events", fake_list_events)

    assert cli.main(["area", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "area_id\tstatus\tdisplay_order\tname",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa\tactive\t10\tHealth",
    ]

    assert cli.main(["person", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "person_id\tstatus\tname\tlocation\ttags",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb\tactive\tAlice\tToronto\tfamily,friend",
    ]

    assert cli.main(["vision", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "vision_id\tstatus\tarea_id\tname",
        (
            "cccccccc-cccc-cccc-cccc-cccccccccccc\tactive\t"
            "dddddddd-dddd-dddd-dddd-dddddddddddd\tLaunch lifeos-cli"
        ),
    ]

    assert cli.main(["tag", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "tag_id\tstatus\tentity_type\tcategory\tname",
        "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee\tactive\ttask\tpriority\turgent",
    ]

    assert cli.main(["event", "list"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "event_id\tstatus\tevent_type\tstart_time\tend_time\ttask_id\ttitle",
        (
            "ffffffff-ffff-ffff-ffff-ffffffffffff\tplanned\tdeadline\t"
            "2026-04-10T13:00:00+00:00\t2026-04-10T14:00:00+00:00\t-\tShip release"
        ),
    ]
    clear_config_cache()


def test_main_event_add_creates_event(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_event(_session: object, **kwargs: object) -> object:
        payload = cast(events.EventCreateInput, kwargs["payload"])
        assert payload.title == "Doctor appointment"
        assert payload.event_type == "appointment"
        assert payload.person_ids == [UUID("11111111-1111-1111-1111-111111111111")]
        return make_record(id=UUID("12121212-1212-1212-1212-121212121212"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(events, "create_event", fake_create_event)

    exit_code = cli.main(
        [
            "event",
            "add",
            "Doctor appointment",
            "--start-time",
            "2026-04-10T09:00:00",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created event 12121212-1212-1212-1212-121212121212" in captured.out


def test_main_event_add_passes_recurrence_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_event(_session: object, **kwargs: object) -> object:
        payload = cast(events.EventCreateInput, kwargs["payload"])
        assert payload.recurrence_frequency == "daily"
        assert payload.recurrence_interval == 2
        assert payload.recurrence_count == 5
        assert payload.recurrence_rule == {"byweekday": ["monday", "wednesday", "friday"]}
        return make_record(id=UUID("34343434-3434-3434-3434-343434343434"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(events, "create_event", fake_create_event)

    exit_code = cli.main(
        [
            "event",
            "add",
            "Daily review",
            "--start-time",
            "2026-04-10T09:00:00",
            "--recurrence-frequency",
            "daily",
            "--recurrence-interval",
            "2",
            "--recurrence-count",
            "5",
            "--recurrence-weekdays",
            "monday,wednesday,friday",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created event 34343434-3434-3434-3434-343434343434" in captured.out


def test_main_event_add_passes_monthly_recurrence_frequency(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_event(_session: object, **kwargs: object) -> object:
        payload = cast(events.EventCreateInput, kwargs["payload"])
        assert payload.recurrence_frequency == "monthly"
        return make_record(id=UUID("56565656-5656-5656-5656-565656565656"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(events, "create_event", fake_create_event)

    exit_code = cli.main(
        [
            "event",
            "add",
            "Monthly review",
            "--start-time",
            "2026-04-30T16:00:00",
            "--recurrence-frequency",
            "monthly",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created event 56565656-5656-5656-5656-565656565656" in captured.out


def test_main_event_add_passes_event_type(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_event(_session: object, **kwargs: object) -> object:
        payload = cast(events.EventCreateInput, kwargs["payload"])
        assert payload.event_type == "timeblock"
        return make_record(id=UUID("45454545-4545-4545-4545-454545454545"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(events, "create_event", fake_create_event)

    exit_code = cli.main(
        [
            "event",
            "add",
            "Focus Work",
            "--type",
            "timeblock",
            "--start-time",
            "2026-04-10T09:00:00",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created event 45454545-4545-4545-4545-454545454545" in captured.out


def test_main_tag_add_creates_tag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_tag(_session: object, **kwargs: object) -> object:
        assert kwargs["name"] == "family"
        assert kwargs["entity_type"] == "person"
        return make_record(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tags, "create_tag", fake_create_tag)

    exit_code = cli.main(["tag", "add", "family", "--entity-type", "person"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created tag 22222222-2222-2222-2222-222222222222" in captured.out


def test_main_tag_update_can_clear_person(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_tag(_session: object, **kwargs: object) -> object:
        assert kwargs["clear_person"] is True
        assert kwargs["person_ids"] is None
        return make_record(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(tags, "update_tag", fake_update_tag)

    exit_code = cli.main(
        [
            "tag",
            "update",
            "22222222-2222-2222-2222-222222222222",
            "--clear-person",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated tag 22222222-2222-2222-2222-222222222222" in captured.out


def test_main_person_show_prints_tags(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_person(
        _session: object,
        *,
        person_id: UUID,
    ) -> object:
        return make_record(
            id=person_id,
            name="Alice",
            description="Friend",
            nicknames=["ally"],
            birth_date=None,
            location="Toronto",
            tags=[make_record(name="family"), make_record(name="friend")],
            created_at=utc_datetime(2026, 4, 9),
            updated_at=utc_datetime(2026, 4, 9),
            deleted_at=None,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(person, "get_person", fake_get_person)

    exit_code = cli.main(["person", "show", "33333333-3333-3333-3333-333333333333"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "name: Alice" in captured.out
    assert "tags: family, friend" in captured.out


def test_main_event_update_rejects_conflicting_clear_area_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "event",
            "update",
            "12121212-1212-1212-1212-121212121212",
            "--area-id",
            "11111111-1111-1111-1111-111111111111",
            "--clear-area",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --area-id or --clear-area, not both." in captured.err


def test_main_event_update_passes_scope_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_event(_session: object, **kwargs: object) -> object:
        assert kwargs["scope"] == "single"
        changes = cast(events.EventUpdateInput, kwargs["changes"])
        assert changes.event_type == "deadline"
        assert changes.title == "Updated review"
        instance_start = cast(datetime, kwargs["instance_start"])
        assert instance_start is not None
        assert str(instance_start.isoformat()) == "2026-04-10T09:00:00"
        return make_record(id=UUID("56565656-5656-5656-5656-565656565656"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(events, "update_event", fake_update_event)

    exit_code = cli.main(
        [
            "event",
            "update",
            "56565656-5656-5656-5656-565656565656",
            "--scope",
            "single",
            "--instance-start",
            "2026-04-10T09:00:00",
            "--type",
            "deadline",
            "--title",
            "Updated review",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated event 56565656-5656-5656-5656-565656565656" in captured.out


def test_main_event_delete_passes_scope_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete_event(_session: object, **kwargs: object) -> None:
        assert kwargs["scope"] == "all_future"
        instance_start = cast(datetime, kwargs["instance_start"])
        assert instance_start is not None
        assert str(instance_start.isoformat()) == "2026-04-10T09:00:00"

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(events, "delete_event", fake_delete_event)

    exit_code = cli.main(
        [
            "event",
            "delete",
            "56565656-5656-5656-5656-565656565656",
            "--scope",
            "all_future",
            "--instance-start",
            "2026-04-10T09:00:00",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Soft-deleted event 56565656-5656-5656-5656-565656565656" in captured.out


def test_main_person_update_can_clear_location(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_update_person(_session: object, **kwargs: object) -> object:
        assert kwargs["clear_location"] is True
        assert kwargs["location"] is None
        return make_record(id=UUID("33333333-3333-3333-3333-333333333333"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(person, "update_person", fake_update_person)

    exit_code = cli.main(
        [
            "person",
            "update",
            "33333333-3333-3333-3333-333333333333",
            "--clear-location",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated person 33333333-3333-3333-3333-333333333333" in captured.out


def test_main_vision_add_creates_vision(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_create_vision(_session: object, **kwargs: object) -> object:
        assert kwargs["name"] == "Launch lifeos-cli"
        assert kwargs["person_ids"] == [UUID("11111111-1111-1111-1111-111111111111")]
        return make_record(id=UUID("44444444-4444-4444-4444-444444444444"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(visions, "create_vision", fake_create_vision)

    exit_code = cli.main(
        [
            "vision",
            "add",
            "Launch lifeos-cli",
            "--person-id",
            "11111111-1111-1111-1111-111111111111",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created vision 44444444-4444-4444-4444-444444444444" in captured.out


def test_main_vision_update_rejects_conflicting_clear_area_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "vision",
            "update",
            "44444444-4444-4444-4444-444444444444",
            "--area-id",
            "11111111-1111-1111-1111-111111111111",
            "--clear-area",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --area-id or --clear-area, not both." in captured.err


def test_main_vision_experience_commands_call_services(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    async def fake_add_experience(_session: object, **kwargs: object) -> object:
        calls.append("add")
        assert kwargs["vision_id"] == UUID("44444444-4444-4444-4444-444444444444")
        assert kwargs["experience_points"] == 120
        return make_record(id=UUID("44444444-4444-4444-4444-444444444444"))

    async def fake_sync_experience(_session: object, **kwargs: object) -> object:
        calls.append("sync")
        assert kwargs["vision_id"] == UUID("44444444-4444-4444-4444-444444444444")
        return make_record(id=UUID("44444444-4444-4444-4444-444444444444"))

    async def fake_harvest(_session: object, **kwargs: object) -> object:
        calls.append("harvest")
        assert kwargs["vision_id"] == UUID("44444444-4444-4444-4444-444444444444")
        return make_record(id=UUID("44444444-4444-4444-4444-444444444444"))

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(visions, "add_experience_to_vision", fake_add_experience)
    monkeypatch.setattr(visions, "sync_vision_experience", fake_sync_experience)
    monkeypatch.setattr(visions, "harvest_vision", fake_harvest)

    add_exit_code = cli.main(
        [
            "vision",
            "add-experience",
            "44444444-4444-4444-4444-444444444444",
            "--points",
            "120",
        ]
    )
    sync_exit_code = cli.main(["vision", "sync-experience", "44444444-4444-4444-4444-444444444444"])
    harvest_exit_code = cli.main(["vision", "harvest", "44444444-4444-4444-4444-444444444444"])
    captured = capsys.readouterr()

    assert add_exit_code == 0
    assert sync_exit_code == 0
    assert harvest_exit_code == 0
    assert calls == ["add", "sync", "harvest"]
    assert "Updated vision 44444444-4444-4444-4444-444444444444" in captured.out
    assert "Synced vision 44444444-4444-4444-4444-444444444444" in captured.out
    assert "Harvested vision 44444444-4444-4444-4444-444444444444" in captured.out


def test_main_vision_read_model_commands_print_results(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_with_tasks(_session: object, **kwargs: object) -> object:
        assert kwargs["vision_id"] == UUID("44444444-4444-4444-4444-444444444444")
        return make_record(
            id=UUID("44444444-4444-4444-4444-444444444444"),
            name="Launch lifeos-cli",
            description=None,
            status="active",
            stage=0,
            experience_points=0,
            experience_rate_per_hour=60,
            area_id=None,
            person=[],
            tasks=[
                make_record(
                    id=UUID("55555555-5555-5555-5555-555555555555"),
                    status="done",
                    parent_task_id=None,
                    content="Draft release checklist",
                )
            ],
            created_at=None,
            updated_at=None,
            deleted_at=None,
        )

    async def fake_get_stats(_session: object, **kwargs: object) -> object:
        assert kwargs["vision_id"] == UUID("44444444-4444-4444-4444-444444444444")
        return visions.VisionStats(
            total_tasks=1,
            completed_tasks=1,
            in_progress_tasks=0,
            todo_tasks=0,
            completion_percentage=1.0,
            total_estimated_effort=30,
            total_actual_effort=45,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(visions, "get_vision_with_tasks", fake_get_with_tasks)
    monkeypatch.setattr(visions, "get_vision_stats", fake_get_stats)

    with_tasks_exit_code = cli.main(
        ["vision", "with-tasks", "44444444-4444-4444-4444-444444444444"]
    )
    stats_exit_code = cli.main(["vision", "stats", "44444444-4444-4444-4444-444444444444"])
    captured = capsys.readouterr()

    assert with_tasks_exit_code == 0
    assert stats_exit_code == 0
    assert "tasks:" in captured.out
    assert "  task_id\tstatus\tparent_task_id\tcontent" in captured.out
    assert "Draft release checklist" in captured.out
    assert "total_tasks: 1" in captured.out
    assert "completion_percentage: 1.00" in captured.out


def test_main_person_batch_delete_reports_missing_ids(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_batch_delete_person(
        _session: object,
        *,
        person_ids: list[UUID],
    ) -> object:
        assert person_ids == [UUID("33333333-3333-3333-3333-333333333333")]
        return make_record(
            deleted_count=0,
            failed_ids=(UUID("33333333-3333-3333-3333-333333333333"),),
            errors=("Person 33333333-3333-3333-3333-333333333333 was not found",),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(person, "batch_delete_person", fake_batch_delete_person)

    exit_code = cli.main(
        [
            "person",
            "batch",
            "delete",
            "--ids",
            "33333333-3333-3333-3333-333333333333",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Deleted people: 0" in captured.out
    assert "Failed person IDs" in captured.err
