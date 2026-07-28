from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.cli import build_parser
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db.services.read_models import (
    EventView,
    HabitActionSummaryView,
    NoteView,
    PersonSummaryView,
    PersonView,
    TagSummaryView,
    TagView,
    TaskSummaryView,
    TaskView,
    TimelogTemplateView,
    TimelogView,
)
from lifeos_cli.db.services.timelog_support import (
    TimelogBatchUpdateInput,
    TimelogListInput,
    TimelogQueryFilters,
)
from tests.config_support import install_test_config


class CachedEngineSentinel:
    async def dispose(self) -> None:
        raise AssertionError("Web preference writes must not dispose the cached database engine")


def test_web_command_is_registered() -> None:
    parser = build_parser()

    args = parser.parse_args(["web", "serve", "--port", "9876"])

    assert args.resource == "web"
    assert args.web_command == "serve"
    assert args.port == 9876


def test_web_finance_decimal_serialization_avoids_scientific_zero() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.finance import _asset_decimal_str, _decimal_str

    assert _decimal_str(Decimal("0E-8")) == "0.00000000"
    assert _decimal_str(Decimal("1250.50000000")) == "1250.50000000"
    assert (
        _asset_decimal_str(
            Decimal("37916.37000000"),
            currency_code="CNY",
            decimal_places_by_code={"CNY": 2},
        )
        == "37916.37"
    )
    assert (
        _asset_decimal_str(
            Decimal("0E-8"),
            currency_code="BTC",
            decimal_places_by_code={"BTC": 8},
        )
        == "0.00000000"
    )


def test_web_finance_payloads_exclude_unconsumed_audit_fields() -> None:
    pytest.importorskip("fastapi")
    from lifeos_cli.db.models.finance import (
        FinanceAsset,
        FinanceRateSnapshot,
        FinanceSnapshot,
        FinanceTreeNode,
    )
    from lifeos_web.routers.finance import (
        _asset_payload,
        _rate_snapshot_payload,
        _snapshot_payload,
        _tree_payload,
    )

    timestamp = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)
    node_id = UUID("11111111-1111-1111-1111-111111111111")
    tree_id = UUID("22222222-2222-2222-2222-222222222222")
    snapshot_id = UUID("33333333-3333-3333-3333-333333333333")
    rate_snapshot_id = UUID("44444444-4444-4444-4444-444444444444")

    asset_payload = _asset_payload(
        cast(
            FinanceAsset,
            SimpleNamespace(
                id=UUID("55555555-5555-5555-5555-555555555555"),
                code="USD",
                name="US Dollar",
                decimal_places=2,
                display_order=10,
                is_default=True,
                metadata_json={"hidden": True},
                created_at=timestamp,
                updated_at=timestamp,
                deleted_at=None,
            ),
        )
    )
    assert asset_payload == {
        "id": "55555555-5555-5555-5555-555555555555",
        "code": "USD",
        "name": "US Dollar",
        "decimal_places": 2,
        "is_default": True,
    }

    node = cast(
        FinanceTreeNode,
        SimpleNamespace(
            id=node_id,
            tree_id=tree_id,
            parent_id=None,
            name="Cash",
            currency_code="USD",
            path="0001",
            depth=0,
            display_order=1,
            children_count=0,
            metadata_json={"hidden": True},
            created_at=timestamp,
            updated_at=timestamp,
            deleted_at=None,
        ),
    )
    tree_payload = _tree_payload(
        SimpleNamespace(
            id=tree_id,
            name="Balance",
            primary_currency="USD",
            display_order=1,
            is_default=True,
            metadata_json={"hidden": True},
            created_at=timestamp,
            updated_at=timestamp,
            deleted_at=None,
        ),
        nodes=[node],
    )
    assert set(tree_payload) == {
        "id",
        "name",
        "primary_currency",
        "display_order",
        "is_default",
        "nodes",
    }
    assert set(cast(list[dict[str, object]], tree_payload["nodes"])[0]) == {
        "id",
        "parent_id",
        "name",
        "currency_code",
        "path",
        "depth",
        "display_order",
    }

    snapshot = cast(
        FinanceSnapshot,
        SimpleNamespace(
            id=snapshot_id,
            tree_id=tree_id,
            tree=SimpleNamespace(name="Balance"),
            title="June",
            snapshot_ts=timestamp,
            period_start=None,
            period_end=None,
            primary_currency="USD",
            rate_snapshot_id=rate_snapshot_id,
            rate_snapshot_policy="selected",
            total_positive=Decimal("1"),
            total_negative=Decimal("0"),
            net_amount=Decimal("1"),
            exchange_rates={"rates": {"USD": {"rate": "1"}}},
            summary={"amounts_by_currency": {"USD": {"net_amount": "1"}}},
            note="detail note",
            created_at=timestamp,
            updated_at=timestamp,
            deleted_at=None,
            entries=[
                SimpleNamespace(
                    id=UUID("66666666-6666-6666-6666-666666666666"),
                    snapshot_id=snapshot_id,
                    node_id=node_id,
                    node=node,
                    amount=Decimal("1"),
                    currency_code="USD",
                    amount_converted=Decimal("1"),
                    note=None,
                    is_auto_generated=False,
                    created_at=timestamp,
                    updated_at=timestamp,
                    deleted_at=None,
                )
            ],
        ),
    )
    list_snapshot_payload = _snapshot_payload(
        snapshot,
        decimal_places_by_code={"USD": 2},
    )
    assert "summary" not in list_snapshot_payload
    assert "exchange_rates" not in list_snapshot_payload
    assert "entries" not in list_snapshot_payload
    assert "rate_snapshot_policy" not in list_snapshot_payload
    detail_snapshot_payload = _snapshot_payload(
        snapshot,
        decimal_places_by_code={"USD": 2},
        include_entries=True,
    )
    assert {"summary", "exchange_rates", "entries", "note"} <= set(detail_snapshot_payload)
    entry_payload = cast(list[dict[str, object]], detail_snapshot_payload["entries"])[0]
    assert "snapshot_id" not in entry_payload
    assert "node_path" not in entry_payload

    rate_snapshot_payload = _rate_snapshot_payload(
        cast(
            FinanceRateSnapshot,
            SimpleNamespace(
                id=rate_snapshot_id,
                captured_at=timestamp,
                source="manual",
                note=None,
                metadata_json={"hidden": True},
                created_at=timestamp,
                updated_at=timestamp,
                deleted_at=None,
                entries=[
                    SimpleNamespace(
                        id=UUID("77777777-7777-7777-7777-777777777777"),
                        rate_snapshot_id=rate_snapshot_id,
                        base_currency="USD",
                        quote_currency="CNY",
                        rate=Decimal("7.1"),
                        source="manual",
                        captured_at=timestamp,
                        is_derived=False,
                        metadata_json={"hidden": True},
                        created_at=timestamp,
                        updated_at=timestamp,
                        deleted_at=None,
                    )
                ],
            ),
        )
    )
    assert "metadata" not in rate_snapshot_payload
    rate_entry_payload = cast(list[dict[str, object]], rate_snapshot_payload["entries"])[0]
    assert "rate_snapshot_id" not in rate_entry_payload
    assert "is_derived" not in rate_entry_payload


def test_web_routes_do_not_expose_deleted_records() -> None:
    pytest.importorskip("fastapi")
    from fastapi.routing import APIRoute

    from lifeos_web.app import create_app

    app = create_app()
    routes_with_include_deleted = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and any(param.name == "include_deleted" for param in route.dependant.query_params)
    ]

    assert routes_with_include_deleted == []


def test_web_vision_payload_excludes_unconsumed_audit_fields() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.visions import _vision_payload

    timestamp = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)
    vision = SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        name="Portfolio",
        description="Reduce response payloads",
        area_id=UUID("22222222-2222-2222-2222-222222222222"),
        status="active",
        stage=3,
        experience_points=42,
        experience_rate_per_hour=120,
        created_at=timestamp,
        updated_at=timestamp,
        deleted_at=timestamp,
        people=(),
        tasks=(SimpleNamespace(id=UUID("33333333-3333-3333-3333-333333333333")),),
    )

    payload = _vision_payload(vision)

    assert set(payload) == {
        "id",
        "name",
        "description",
        "area_id",
        "status",
        "stage",
        "experience_points",
        "experience_rate_per_hour",
        "created_at",
        "people",
    }
    assert payload["created_at"] == "2026-06-01T13:00:00Z"
    assert "updated_at" not in payload
    assert "deleted_at" not in payload
    assert "tasks" not in payload
    assert "tasks" in _vision_payload(vision, include_tasks=True)


def test_web_task_hierarchy_payload_excludes_deleted_at() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.tasks import _task_tree_payload

    timestamp = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)

    def task_node(task_id: str, *, subtasks: tuple[object, ...] = ()) -> SimpleNamespace:
        return SimpleNamespace(
            id=UUID(task_id),
            vision_id=UUID("22222222-2222-2222-2222-222222222222"),
            parent_task_id=None,
            content="Audit endpoint payload",
            description=None,
            status="todo",
            priority=1,
            display_order=1,
            estimated_effort=None,
            planning_cycle_type=None,
            planning_cycle_days=None,
            planning_cycle_start_date=None,
            actual_effort_self=0,
            actual_effort_total=0,
            created_at=timestamp,
            updated_at=timestamp,
            deleted_at=timestamp,
            people=(),
            subtasks=subtasks,
            completion_percentage=0,
            depth=0,
        )

    payload = _task_tree_payload(
        task_node(
            "11111111-1111-1111-1111-111111111111",
            subtasks=(task_node("33333333-3333-3333-3333-333333333333"),),
        ),
        notes_count_by_task={
            UUID("11111111-1111-1111-1111-111111111111"): 2,
        },
        timelogs_count_by_task={
            UUID("33333333-3333-3333-3333-333333333333"): 1,
        },
    )

    assert payload["created_at"] == "2026-06-01T13:00:00+00:00"
    assert payload["updated_at"] == "2026-06-01T13:00:00+00:00"
    assert payload["notes_count"] == 2
    assert payload["timelogs_count"] == 0
    assert "actual_effort" not in payload
    assert "deleted_at" not in payload
    subtask_payload = cast(list[dict[str, object]], payload["subtasks"])[0]
    assert subtask_payload["notes_count"] == 0
    assert subtask_payload["timelogs_count"] == 1
    assert "deleted_at" not in subtask_payload


def test_web_task_list_basic_payload_excludes_full_task_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tasks

    timestamp = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)
    task = TaskView(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        vision_id=UUID("22222222-2222-2222-2222-222222222222"),
        parent_task_id=None,
        content="Focus",
        description="Full description",
        status="todo",
        priority=2,
        display_order=3,
        estimated_effort=45,
        planning_cycle_type="day",
        planning_cycle_days=1,
        planning_cycle_start_date=date(2026, 6, 30),
        actual_effort_self=10,
        actual_effort_total=15,
        created_at=timestamp,
        updated_at=timestamp,
        deleted_at=timestamp,
        people=(PersonSummaryView(id=UUID("33333333-3333-3333-3333-333333333333"), name="A"),),
    )

    async def fake_list_tasks(_session: object, **_kwargs: object) -> list[TaskView]:
        return [task]

    async def fake_count_tasks(_session: object, **_kwargs: object) -> int:
        return 1

    async def fake_load_task_relation_counts(
        _session: object,
        *,
        task_ids: list[UUID],
    ) -> tuple[dict[UUID, int], dict[UUID, int]]:
        assert task_ids == [UUID("11111111-1111-1111-1111-111111111111")]
        return (
            {UUID("11111111-1111-1111-1111-111111111111"): 4},
            {UUID("11111111-1111-1111-1111-111111111111"): 5},
        )

    monkeypatch.setattr(tasks.task_services, "list_tasks", fake_list_tasks)
    monkeypatch.setattr(tasks.task_services, "count_tasks", fake_count_tasks)
    monkeypatch.setattr(
        tasks.task_queries,
        "load_task_relation_counts",
        fake_load_task_relation_counts,
    )

    response = asyncio.run(
        tasks.list_tasks(
            cast(AsyncSession, object()),
            fields="basic",
        )
    )

    payload = cast(dict[str, object], response.items[0])
    assert payload == {
        "id": "11111111-1111-1111-1111-111111111111",
        "vision_id": "22222222-2222-2222-2222-222222222222",
        "parent_task_id": None,
        "content": "Focus",
        "status": "todo",
        "priority": 2,
        "display_order": 3,
        "planning_cycle_type": "day",
        "planning_cycle_days": 1,
        "planning_cycle_start_date": "2026-06-30",
        "people": [{"id": "33333333-3333-3333-3333-333333333333", "name": "A"}],
        "notes_count": 4,
        "timelogs_count": 5,
    }
    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "deleted_at" not in payload
    assert "estimated_effort" not in payload
    assert "actual_effort_total" not in payload
    assert response.meta["fields"] == "basic"


def test_web_general_payloads_exclude_unconsumed_audit_fields() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.areas import _area_payload
    from lifeos_web.routers.habits import _habit_model_payload
    from lifeos_web.routers.persons import _person_payload

    timestamp = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)

    area_payload = _area_payload(
        cast(
            Any,
            SimpleNamespace(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                name="Work",
                description=None,
                color="#3B82F6",
                icon=None,
                is_active=True,
                display_order=1,
                created_at=timestamp,
                updated_at=timestamp,
            ),
        )
    )
    assert "created_at" not in area_payload
    assert "updated_at" not in area_payload

    habit_payload = _habit_model_payload(
        cast(
            Any,
            SimpleNamespace(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                title="Read",
                description=None,
                start_date=date(2026, 6, 1),
                duration_days=30,
                cadence_frequency="daily",
                cadence_weekdays=None,
                target_per_cycle=1,
                status="active",
                task_id=None,
                created_at=timestamp,
                updated_at=timestamp,
                deleted_at=timestamp,
            ),
        )
    )
    assert "created_at" not in habit_payload
    assert "updated_at" not in habit_payload
    assert "deleted_at" not in habit_payload

    person_payload = _person_payload(
        cast(
            Any,
            SimpleNamespace(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                name="Ada",
                description=None,
                nicknames=(),
                birth_date=None,
                location=None,
                created_at=timestamp,
                updated_at=timestamp,
                deleted_at=timestamp,
                tags=(),
            ),
        )
    )
    assert "created_at" not in person_payload
    assert "updated_at" not in person_payload
    assert "deleted_at" not in person_payload
    assert "is_soft_deleted" not in person_payload


def test_web_person_payload_preserves_tag_categories() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.persons import _person_payload

    payload = _person_payload(
        PersonView(
            id=UUID("33333333-3333-3333-3333-333333333333"),
            name="Ada",
            description=None,
            nicknames=(),
            birth_date=None,
            location=None,
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            tags=(
                TagSummaryView(
                    id=UUID("44444444-4444-4444-4444-444444444444"),
                    name="Shanghai",
                    entity_type="person",
                    category="location",
                ),
            ),
        )
    )

    assert payload["tags"] == [
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "name": "Shanghai",
            "entity_type": "person",
            "category": "location",
            "description": None,
            "color": None,
            "created_at": "",
            "updated_at": "",
        }
    ]


def test_web_person_timelog_activity_payload_exposes_timeline_fields() -> None:
    pytest.importorskip("fastapi")
    from lifeos_cli.db.services.person_activity_queries import (
        PersonActivity,
        _timelog_total_minutes,
    )
    from lifeos_web.routers.persons import _activity_payload

    timestamp = datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)
    activity = PersonActivity(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        activity_type="timelog",
        title="Deep work",
        description=None,
        activity_date=timestamp,
        start_time=timestamp,
        end_time=datetime(2026, 7, 2, 9, 30, tzinfo=timezone.utc),
        area_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    payload = _activity_payload(activity)

    assert payload["status"] is None
    assert payload["start_time"] == "2026-07-02T09:00:00+00:00"
    assert payload["end_time"] == "2026-07-02T09:30:00+00:00"
    assert payload["area_id"] == "22222222-2222-2222-2222-222222222222"
    assert _timelog_total_minutes([activity]) == 30


def test_web_habit_action_payload_uses_slim_habit_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers import habits

    habit_id = UUID("11111111-1111-1111-1111-111111111111")

    async def fake_get_habit(_session: object, *, habit_id: UUID) -> object:
        assert habit_id == UUID("11111111-1111-1111-1111-111111111111")
        return SimpleNamespace(
            id=habit_id,
            title="Walk",
            description="Midday walk",
            start_date=date(2026, 6, 1),
            duration_days=30,
            cadence_frequency="daily",
            cadence_weekdays=None,
            target_per_cycle=1,
            status="active",
            task_id=UUID("22222222-2222-2222-2222-222222222222"),
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
        )

    monkeypatch.setattr(habits.habit_services, "get_habit", fake_get_habit)

    action = SimpleNamespace(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        habit_id=habit_id,
        habit_title="Walk",
        action_date=date(2026, 6, 30),
        status="pending",
        notes=None,
        created_at=datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
        deleted_at=None,
    )

    plain_payload = habits._habit_action_payload(action)
    assert plain_payload == {
        "id": "33333333-3333-3333-3333-333333333333",
        "habit_id": "11111111-1111-1111-1111-111111111111",
        "action_date": "2026-06-30",
        "status": "pending",
        "notes": None,
        "linked_notes_count": 0,
    }

    summary_payload = asyncio.run(
        habits._action_with_habit_summary(cast(AsyncSession, object()), action)
    )
    assert "habit_title" not in summary_payload
    assert summary_payload["habit"] == {
        "title": "Walk",
        "description": "Midday walk",
        "start_date": "2026-06-01",
        "duration_days": 30,
        "cadence_frequency": "daily",
    }
    habit_summary = cast(dict[str, object], summary_payload["habit"])
    assert "id" not in habit_summary
    assert "task_id" not in habit_summary


def test_cli_rejects_deleted_record_visibility_flags_on_consumer_commands() -> None:
    parser = build_parser()
    rejected_commands = (
        ("area", "list", "--include-deleted"),
        ("area", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("event", "list", "--include-deleted"),
        ("event", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("finance", "asset-list", "--include-deleted"),
        ("finance", "tree-list", "--include-deleted"),
        ("finance", "tree-show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("finance", "rate-snapshot-list", "--include-deleted"),
        (
            "finance",
            "rate-snapshot-show",
            "11111111-1111-1111-1111-111111111111",
            "--include-deleted",
        ),
        (
            "finance",
            "snapshot-show",
            "11111111-1111-1111-1111-111111111111",
            "--include-deleted",
        ),
        ("habit", "list", "--include-deleted"),
        ("habit", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("habit-action", "list", "--include-deleted"),
        ("habit-action", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("note", "list", "--include-deleted"),
        ("note", "search", "query", "--include-deleted"),
        ("note", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("people", "list", "--include-deleted"),
        ("people", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("tag", "list", "--include-deleted"),
        ("tag", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("task", "list", "--include-deleted"),
        ("task", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("timelog", "list", "--include-deleted"),
        ("timelog", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("vision", "list", "--include-deleted"),
        ("vision", "show", "11111111-1111-1111-1111-111111111111", "--include-deleted"),
        ("data", "export", "note", "--exclude-deleted"),
    )

    for command in rejected_commands:
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(command)
        assert exc_info.value.code == 2


def test_planned_event_recurrence_until_accepts_utc_z_suffix() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.planned_events import _create_input
    from lifeos_web.schemas import PlannedEventCreate

    payload = PlannedEventCreate(
        title="Daily focus",
        start_time=datetime(2026, 6, 16, 16, 0, tzinfo=timezone.utc),
        is_recurring=True,
        recurrence_pattern={
            "frequency": "daily",
            "until": "2026-06-20T16:00:00.000Z",
        },
    )

    parsed = _create_input(payload)

    assert parsed.recurrence_until is not None
    assert parsed.recurrence_until.isoformat() == "2026-06-20T16:00:00+00:00"


def test_planned_event_rrule_preserves_advanced_recurrence_details() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.planned_events import _create_input, _planned_event_payload
    from lifeos_web.schemas import PlannedEventCreate

    payload = PlannedEventCreate(
        title="Second Monday review",
        start_time=datetime(2026, 4, 13, 16, 0, tzinfo=timezone.utc),
        is_recurring=True,
        rrule_string="FREQ=MONTHLY;BYDAY=2MO;BYMONTH=4,5",
    )

    parsed = _create_input(payload)

    assert parsed.recurrence_frequency == "monthly"
    assert parsed.recurrence_rule == {
        "bymonth": [4, 5],
        "byweekday_ordinals": [{"weekday": "monday", "ordinal": 2}],
    }

    event_payload = _planned_event_payload(
        EventView(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            title="Second Monday review",
            description=None,
            status="planned",
            event_type="appointment",
            priority=0,
            is_all_day=False,
            start_time=datetime(2026, 4, 13, 16, 0, tzinfo=timezone.utc),
            end_time=None,
            recurrence_frequency="monthly",
            recurrence_interval=1,
            recurrence_count=None,
            recurrence_until=None,
            recurrence_rule={
                "bymonth": [4, 5],
                "byweekday_ordinals": [{"weekday": "monday", "ordinal": 2}],
            },
            recurrence_parent_event_id=None,
            recurrence_instance_start=None,
            area_id=None,
            task_id=None,
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            deleted_at=None,
        )
    )

    assert event_payload["recurrence_pattern"] == {
        "frequency": "monthly",
        "interval": 1,
        "count": None,
        "until": None,
        "bymonth": [4, 5],
        "byweekday_ordinals": [{"weekday": "monday", "ordinal": 2}],
    }
    assert event_payload["rrule_string"] == "FREQ=MONTHLY;BYDAY=2MO;BYMONTH=4,5"
    assert "created_at" not in event_payload
    assert "updated_at" not in event_payload


def test_planned_event_create_ignores_rrule_when_not_recurring() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.planned_events import _create_input
    from lifeos_web.schemas import PlannedEventCreate

    payload = PlannedEventCreate(
        title="One-off review",
        start_time=datetime(2026, 4, 13, 16, 0, tzinfo=timezone.utc),
        is_recurring=False,
        rrule_string="FREQ=MONTHLY;BYDAY=2MO",
    )

    parsed = _create_input(payload)

    assert parsed.recurrence_frequency is None
    assert parsed.recurrence_rule is None


def test_web_app_registers_core_resource_routes() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.app import app

    route_paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is not None:
            route_paths.add(path)
            continue
        include_context = getattr(route, "include_context", None)
        original_router = getattr(route, "original_router", None)
        if include_context is None or original_router is None:
            continue
        prefix = getattr(include_context, "prefix", "") or ""
        route_paths.update(
            f"{prefix}{child.path}"
            for child in original_router.routes
            if getattr(child, "path", None) is not None
        )

    assert "/api/v1/tasks/" in route_paths
    assert "/api/v1/timelogs/" in route_paths
    assert "/api/v1/timelogs/templates/" in route_paths
    assert "/api/v1/notes/" in route_paths
    assert "/api/v1/visions/" in route_paths
    assert "/api/v1/habits/" in route_paths
    assert "/api/v1/habits/habit-task-associations/" in route_paths
    assert "/api/v1/persons/" in route_paths
    assert "/api/v1/tags/" in route_paths
    assert "/api/v1/finance/trees" in route_paths


def test_web_tasks_list_uses_count_for_pagination_and_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tasks as task_router

    captured: dict[str, object] = {}

    async def fake_list_tasks(_session: object, **kwargs: object) -> list[object]:
        captured["list_kwargs"] = kwargs
        return [
            SimpleNamespace(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                vision_id=UUID("22222222-2222-2222-2222-222222222222"),
                parent_task_id=None,
                content="Needle task",
                status="todo",
            )
        ]

    async def fake_count_tasks(_session: object, **kwargs: object) -> int:
        captured["count_kwargs"] = kwargs
        return 123

    async def fake_load_task_relation_counts(
        _session: object,
        *,
        task_ids: list[UUID],
    ) -> tuple[dict[UUID, int], dict[UUID, int]]:
        assert task_ids == [UUID("11111111-1111-1111-1111-111111111111")]
        return ({}, {})

    monkeypatch.setattr(task_router.task_services, "list_tasks", fake_list_tasks)
    monkeypatch.setattr(task_router.task_services, "count_tasks", fake_count_tasks)
    monkeypatch.setattr(
        task_router.task_queries,
        "load_task_relation_counts",
        fake_load_task_relation_counts,
    )

    response = asyncio.run(
        task_router.list_tasks(
            cast(AsyncSession, object()),
            page=2,
            size=50,
            query="Needle",
        )
    )

    assert captured["list_kwargs"] == {
        "vision_id": None,
        "vision_in": None,
        "status": None,
        "status_in": None,
        "exclude_status": None,
        "planning_cycle_type": None,
        "planning_cycle_start_date": None,
        "calendar_system": None,
        "first_day_of_week": None,
        "query": "Needle",
        "limit": 50,
        "offset": 50,
    }
    assert captured["count_kwargs"] == {
        "vision_id": None,
        "vision_in": None,
        "status": None,
        "status_in": None,
        "exclude_status": None,
        "planning_cycle_type": None,
        "planning_cycle_start_date": None,
        "calendar_system": None,
        "first_day_of_week": None,
        "query": "Needle",
    }
    assert response.pagination.total == 123
    assert response.pagination.pages == 3
    assert response.meta["query"] == "Needle"


def test_web_tasks_reorder_route_precedes_task_id_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tasks as task_router
    from lifeos_web.schemas import TaskReorderItem, TaskReorderRequest

    captured: dict[str, object] = {}

    async def fake_reorder_tasks(_session: object, **kwargs: object) -> None:
        captured["task_orders"] = kwargs["task_orders"]

    monkeypatch.setattr(task_router.task_services, "reorder_tasks", fake_reorder_tasks)

    task_route_paths = [getattr(route, "path", None) for route in task_router.router.routes]

    task_one_id = "11111111-1111-1111-1111-111111111111"
    task_two_id = "22222222-2222-2222-2222-222222222222"

    assert task_route_paths.index("/tasks/reorder") < task_route_paths.index("/tasks/{task_id}")

    asyncio.run(
        task_router.reorder_tasks(
            TaskReorderRequest(
                task_orders=[
                    TaskReorderItem(id=UUID(task_two_id), display_order=0),
                    TaskReorderItem(id=UUID(task_one_id), display_order=1),
                ],
            ),
            cast(AsyncSession, object()),
        )
    )

    assert captured["task_orders"] == [
        (UUID(task_two_id), 0),
        (UUID(task_one_id), 1),
    ]


def test_web_static_assets_disable_cache(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.app import SPAStaticFiles

    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>LifeOS</html>", encoding="utf-8")
    (assets_dir / "app.js").write_text("console.log('lifeos')", encoding="utf-8")

    static_files = SPAStaticFiles(directory=static_dir, html=True)
    scope = {"type": "http", "method": "GET", "headers": []}

    asset_response = asyncio.run(static_files.get_response("assets/app.js", scope))
    spa_response = asyncio.run(static_files.get_response("timelog", scope))

    assert asset_response.status_code == 200
    assert asset_response.headers["cache-control"] == "no-store"
    assert spa_response.status_code == 200
    assert spa_response.headers["cache-control"] == "no-store"

    for reserved_path in ("api/v1/missing", "health/missing", "assets/missing"):
        route_error: object | None = None
        try:
            asyncio.run(static_files.get_response(reserved_path, scope))
        except Exception as exc:
            route_error = exc
        else:
            pytest.fail(f"{reserved_path} should not fall back to SPA index.html")

        assert getattr(route_error, "status_code", None) == 404


def test_web_server_preflights_configured_database_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from lifeos_web import server

    checked_urls: list[str] = []

    monkeypatch.setattr(
        server,
        "get_database_settings",
        lambda: SimpleNamespace(
            require_database_url=lambda: "postgresql+psycopg://localhost/lifeos"
        ),
    )
    monkeypatch.setattr(server, "ensure_database_driver_available", checked_urls.append)
    monkeypatch.setattr(server, "ensure_database_url_storage_ready", lambda _url: None)

    server.preflight_database_runtime()

    assert checked_urls == ["postgresql+psycopg://localhost/lifeos"]


def test_web_timelog_without_area_filter_maps_to_lifeos_without_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    captured: dict[str, TimelogListInput | TimelogQueryFilters] = {}

    async def fake_count_timelogs(_session: object, *, filters: TimelogQueryFilters) -> int:
        captured["count_filters"] = filters
        return 0

    async def fake_list_timelogs(_session: object, *, query: TimelogListInput) -> list[object]:
        captured["list_query"] = query
        return []

    monkeypatch.setattr(
        timelogs.timelog_services,
        "count_timelogs",
        fake_count_timelogs,
    )
    monkeypatch.setattr(
        timelogs.timelog_services,
        "list_timelogs",
        fake_list_timelogs,
    )

    response = asyncio.run(
        timelogs.list_timelogs(
            cast(AsyncSession, object()),
            page=1,
            size=50,
            without_area=True,
        )
    )

    count_filters = captured["count_filters"]
    list_query = captured["list_query"]
    assert isinstance(count_filters, TimelogQueryFilters)
    assert isinstance(list_query, TimelogListInput)
    assert count_filters.without_area is True
    assert list_query.filters.without_area is True
    assert response.meta["without_area"] is True


def test_web_timelog_template_list_maps_pagination_and_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelog_templates

    captured: dict[str, object] = {}

    async def fake_count_templates(_session: object) -> int:
        return 12

    async def fake_list_templates(_session: object, *, query: object) -> list[object]:
        captured["query"] = query
        return []

    monkeypatch.setattr(
        timelog_templates.template_services,
        "count_templates",
        fake_count_templates,
    )
    monkeypatch.setattr(
        timelog_templates.template_services,
        "list_templates",
        fake_list_templates,
    )

    response = asyncio.run(
        timelog_templates.list_timelog_templates(
            cast(AsyncSession, object()),
            page=2,
            size=5,
            order_by="usage",
        )
    )

    query = captured["query"]
    assert isinstance(query, timelog_templates.template_services.TimelogTemplateListInput)
    assert query.limit == 5
    assert query.offset == 5
    assert query.order_by == "usage"
    assert response.pagination.total == 12
    assert response.pagination.pages == 3
    assert response.meta["order_by"] == "usage"


def test_web_timelog_template_payload_excludes_unconsumed_audit_fields() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.timelog_templates import _template_payload

    payload = _template_payload(
        TimelogTemplateView(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            title="Focus",
            area_id=UUID("22222222-2222-2222-2222-222222222222"),
            area_name="Work",
            area_color="#111111",
            person_ids=(UUID("33333333-3333-3333-3333-333333333333"),),
            people=(
                PersonSummaryView(
                    id=UUID("33333333-3333-3333-3333-333333333333"),
                    name="A",
                ),
            ),
            default_duration_minutes=25,
            position=1,
            usage_count=2,
            last_used_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            deleted_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
    )

    assert payload["person_ids"] == ["33333333-3333-3333-3333-333333333333"]
    assert payload["people"] == [
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "A",
            "display_name": "A",
            "primary_nickname": "A",
            "tags": [],
        }
    ]
    assert payload["created_at"] == "2026-06-01T13:00:00+00:00"
    assert "updated_at" not in payload
    assert "deleted_at" not in payload


def test_web_timelog_template_update_preserves_explicit_nulls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelog_templates
    from lifeos_web.schemas import TimelogTemplateUpdate

    template_id = UUID("11111111-1111-1111-1111-111111111111")
    captured: dict[str, object] = {}

    async def fake_update_template(_session: object, **kwargs: object) -> TimelogTemplateView:
        captured.update(kwargs)
        return TimelogTemplateView(
            id=template_id,
            title="Focus",
            area_id=None,
            area_name=None,
            area_color=None,
            person_ids=(),
            people=(PersonSummaryView(id=UUID("22222222-2222-2222-2222-222222222222"), name="A"),),
            default_duration_minutes=None,
            position=0,
            usage_count=0,
            last_used_at=None,
            created_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 17, tzinfo=timezone.utc),
            deleted_at=None,
        )

    monkeypatch.setattr(
        timelog_templates.template_services,
        "update_template",
        fake_update_template,
    )

    response = asyncio.run(
        timelog_templates.update_timelog_template(
            template_id,
            TimelogTemplateUpdate(
                title=None,
                area_id=None,
                default_duration_minutes=None,
                position=None,
                usage_count=None,
            ),
            cast(AsyncSession, object()),
        )
    )

    changes = captured["changes"]
    assert isinstance(changes, timelog_templates.template_services.TimelogTemplateUpdateInput)
    assert changes.area_provided is True
    assert changes.area_id is None
    assert changes.default_duration_minutes_provided is True
    assert changes.default_duration_minutes is None
    assert changes.person_ids_provided is False
    assert response["people"] == [
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "A",
            "display_name": "A",
            "primary_nickname": "A",
            "tags": [],
        }
    ]


def test_web_timelog_without_task_filter_maps_to_lifeos_without_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    captured: dict[str, TimelogListInput | TimelogQueryFilters] = {}

    async def fake_count_timelogs(_session: object, *, filters: TimelogQueryFilters) -> int:
        captured["count_filters"] = filters
        return 0

    async def fake_list_timelogs(_session: object, *, query: TimelogListInput) -> list[object]:
        captured["list_query"] = query
        return []

    monkeypatch.setattr(
        timelogs.timelog_services,
        "count_timelogs",
        fake_count_timelogs,
    )
    monkeypatch.setattr(
        timelogs.timelog_services,
        "list_timelogs",
        fake_list_timelogs,
    )

    response = asyncio.run(
        timelogs.list_timelogs(
            cast(AsyncSession, object()),
            page=1,
            size=50,
            without_task=True,
        )
    )

    count_filters = captured["count_filters"]
    list_query = captured["list_query"]
    assert isinstance(count_filters, TimelogQueryFilters)
    assert isinstance(list_query, TimelogListInput)
    assert count_filters.without_task is True
    assert list_query.filters.without_task is True
    assert response.meta["without_task"] is True


def test_web_timelog_window_filters_map_to_lifeos_window_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    captured: dict[str, TimelogListInput | TimelogQueryFilters] = {}

    async def fake_count_timelogs(_session: object, *, filters: TimelogQueryFilters) -> int:
        captured["count_filters"] = filters
        return 0

    async def fake_list_timelogs(_session: object, *, query: TimelogListInput) -> list[object]:
        captured["list_query"] = query
        return []

    monkeypatch.setattr(
        timelogs.timelog_services,
        "count_timelogs",
        fake_count_timelogs,
    )
    monkeypatch.setattr(
        timelogs.timelog_services,
        "list_timelogs",
        fake_list_timelogs,
    )

    window_start = datetime(2026, 4, 10, 16, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 4, 11, 15, 59, 59, 999000, tzinfo=timezone.utc)

    response = asyncio.run(
        timelogs.list_timelogs(
            cast(AsyncSession, object()),
            page=1,
            size=50,
            window_start=window_start,
            window_end=window_end,
        )
    )

    count_filters = captured["count_filters"]
    list_query = captured["list_query"]
    assert isinstance(count_filters, TimelogQueryFilters)
    assert isinstance(list_query, TimelogListInput)
    assert count_filters.start_date is None
    assert count_filters.end_date is None
    assert count_filters.window_start == window_start
    assert count_filters.window_end == window_end
    assert list_query.filters.window_start == window_start
    assert list_query.filters.window_end == window_end
    assert response.meta["window_start"] == window_start.isoformat()
    assert response.meta["window_end"] == window_end.isoformat()


def test_web_timelog_rejects_mixed_date_and_window_filters() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            timelogs.list_timelogs(
                cast(AsyncSession, object()),
                start_date=date(2026, 4, 10),
                end_date=date(2026, 4, 10),
                window_start=datetime(2026, 4, 10, 16, 0, tzinfo=timezone.utc),
            )
        )

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "Use either start_date/end_date or window_start/window_end" in str(
        getattr(exc_info.value, "detail", "")
    )


def test_web_timelog_rejects_task_id_with_without_task() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            timelogs.list_timelogs(
                cast(AsyncSession, object()),
                task_id=UUID("11111111-1111-1111-1111-111111111111"),
                without_task=True,
            )
        )

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "Use either task_id or without_task" in str(getattr(exc_info.value, "detail", ""))


def test_web_timelog_rejects_with_task_with_other_task_filters() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            timelogs.list_timelogs(
                cast(AsyncSession, object()),
                task_id=UUID("11111111-1111-1111-1111-111111111111"),
                with_task=True,
            )
        )

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "Use only one of task_id, without_task, or with_task" in str(
        getattr(exc_info.value, "detail", "")
    )


def test_web_timelog_rejects_partial_date_filter() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            timelogs.list_timelogs(
                cast(AsyncSession, object()),
                start_date=date(2026, 4, 10),
            )
        )

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "start_date and end_date must be provided together" in str(
        getattr(exc_info.value, "detail", "")
    )


def test_web_timelog_latest_end_time_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs

    async def fake_get_latest_timelog_end_time(_session: object) -> datetime | None:
        return datetime(2026, 7, 4, 16, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(
        timelogs.timelog_services,
        "get_latest_timelog_end_time",
        fake_get_latest_timelog_end_time,
    )

    response = asyncio.run(timelogs.get_latest_timelog_end_time(cast(AsyncSession, object())))

    assert response == {"end_time": "2026-07-04T16:30:00+00:00"}


def test_web_timelog_payload_exposes_linked_task_summary() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.timelogs import _timelog_payload

    task_id = UUID("22222222-2222-2222-2222-222222222222")
    payload = _timelog_payload(
        TimelogView(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            title="Focused work",
            tracking_method="manual",
            start_time=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            location=None,
            energy_level=None,
            notes=None,
            area_id=None,
            task_id=task_id,
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            linked_notes_count=0,
            task=TaskSummaryView(
                id=task_id,
                vision_id=UUID("33333333-3333-3333-3333-333333333333"),
                parent_task_id=None,
                content="Ship web timelog task linkage",
                status="in_progress",
            ),
        )
    )

    assert payload["task_id"] == str(task_id)
    assert payload["task"] == {
        "id": str(task_id),
        "vision_id": "33333333-3333-3333-3333-333333333333",
        "parent_task_id": None,
        "content": "Ship web timelog task linkage",
        "status": "in_progress",
    }


def test_web_timelog_payload_serializes_naive_storage_datetimes_as_utc() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.timelogs import _timelog_payload

    payload = _timelog_payload(
        TimelogView(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            title="SQLite-backed work",
            tracking_method="manual",
            start_time=datetime(2026, 6, 13, 21, 0),
            end_time=datetime(2026, 6, 13, 21, 5),
            location=None,
            energy_level=None,
            notes=None,
            area_id=None,
            task_id=None,
            created_at=datetime(2026, 6, 13, 21, 9, 24),
            updated_at=datetime(2026, 6, 13, 21, 9, 24),
            deleted_at=None,
            linked_notes_count=0,
            task=None,
        )
    )

    assert payload["start_time"] == "2026-06-13T21:00:00Z"
    assert payload["end_time"] == "2026-06-13T21:05:00Z"
    assert payload["created_at"] == "2026-06-13T21:09:24Z"


def test_web_person_note_activity_payload_avoids_duplicate_note_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db.services import person_activity_queries

    note_id = UUID("11111111-1111-1111-1111-111111111111")
    person_id = UUID("22222222-2222-2222-2222-222222222222")
    timestamp = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)
    note = SimpleNamespace(
        id=note_id,
        content="Remember the meeting notes",
        updated_at=timestamp,
    )

    async def fake_load_person_entity_ids(
        _session: object,
        *,
        person_id: UUID,
    ) -> dict[str, list[UUID]]:
        return {}

    async def fake_load_person_note_ids(
        _session: object,
        *,
        person_id: UUID,
    ) -> list[UUID]:
        return [note_id]

    class FakeResult:
        def scalars(self) -> list[object]:
            return [note]

    class FakeSession:
        async def execute(self, _statement: object) -> FakeResult:
            return FakeResult()

    monkeypatch.setattr(
        person_activity_queries,
        "_load_person_entity_ids",
        fake_load_person_entity_ids,
    )
    monkeypatch.setattr(
        person_activity_queries,
        "_load_person_note_ids",
        fake_load_person_note_ids,
    )

    activities = asyncio.run(
        person_activity_queries._load_activity_items(
            cast(AsyncSession, FakeSession()),
            person_id=person_id,
            activity_filter="note",
        )
    )

    assert activities == [
        person_activity_queries.PersonActivity(
            id=note_id,
            activity_type="note",
            title="Remember the meeting notes",
            description=None,
            activity_date=timestamp,
        )
    ]


def test_web_task_update_null_planning_cycle_translates_to_clear_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tasks
    from lifeos_web.schemas import TaskUpdate

    captured: dict[str, object] = {}

    async def fake_update_task(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(tasks.task_services, "update_task", fake_update_task)

    asyncio.run(
        tasks.update_task(
            UUID("55555555-5555-5555-5555-555555555555"),
            TaskUpdate(
                planning_cycle_type=None,
                planning_cycle_days=None,
                planning_cycle_start_date=None,
            ),
            cast(AsyncSession, object()),
        )
    )

    assert captured["clear_planning_cycle"] is True
    assert captured["planning_cycle_type"] is None
    assert captured["planning_cycle_days"] is None
    assert captured["planning_cycle_start_date"] is None


def test_web_task_update_null_parent_and_estimated_effort_translate_to_clear_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tasks
    from lifeos_web.schemas import TaskUpdate

    captured: dict[str, object] = {}

    async def fake_update_task(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(tasks.task_services, "update_task", fake_update_task)

    asyncio.run(
        tasks.update_task(
            UUID("55555555-5555-5555-5555-555555555555"),
            TaskUpdate(parent_task_id=None, estimated_effort=None),
            cast(AsyncSession, object()),
        )
    )

    assert captured["clear_parent"] is True
    assert captured["clear_estimated_effort"] is True


def test_web_vision_update_null_description_and_experience_clear_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import visions
    from lifeos_web.schemas import VisionUpdate

    captured: dict[str, object] = {}

    async def fake_update_vision(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Vision",
            description=None,
            status="active",
            stage=0,
            experience_points=0,
            experience_rate_per_hour=None,
            area_id=None,
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            people=(),
            tasks=(),
        )

    monkeypatch.setattr(visions.vision_services, "update_vision", fake_update_vision)

    asyncio.run(
        visions.update_vision(
            UUID("55555555-5555-5555-5555-555555555555"),
            VisionUpdate(description=None, experience_rate_per_hour=None),
            cast(AsyncSession, object()),
        )
    )

    assert captured["clear_description"] is True
    assert captured["clear_experience_rate"] is True
    assert captured["clear_area"] is False


def test_web_vision_recompute_efforts_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db.services.visions import VisionEffortRecomputeResult
    from lifeos_web.routers import visions

    vision_id = UUID("55555555-5555-5555-5555-555555555555")
    root_id = UUID("11111111-1111-1111-1111-111111111111")
    captured: dict[str, object] = {}

    async def fake_recompute(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return VisionEffortRecomputeResult(
            vision_id=vision_id,
            recomputed_roots=(root_id,),
        )

    monkeypatch.setattr(
        visions.vision_services,
        "recompute_vision_task_efforts",
        fake_recompute,
    )

    response = asyncio.run(
        visions.recompute_vision_efforts(
            vision_id,
            cast(AsyncSession, object()),
        )
    )

    assert captured["vision_id"] == vision_id
    assert response == {
        "vision_id": str(vision_id),
        "recomputed_roots": [str(root_id)],
    }


def test_web_vision_sync_experience_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import visions

    vision_id = UUID("55555555-5555-5555-5555-555555555555")
    captured: dict[str, object] = {}

    async def fake_sync_experience(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            id=vision_id,
            name="Vision",
            description=None,
            status="active",
            stage=1,
            experience_points=120,
            experience_rate_per_hour=None,
            area_id=None,
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            people=(),
            tasks=(),
        )

    monkeypatch.setattr(
        visions.vision_services,
        "sync_vision_experience",
        fake_sync_experience,
    )

    response = asyncio.run(
        visions.sync_vision_experience(
            vision_id,
            cast(AsyncSession, object()),
        )
    )

    assert captured["vision_id"] == vision_id
    assert response["experience_points"] == 120
    assert response["experience_rate_per_hour"] is None


def test_web_vision_update_area_id_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import visions
    from lifeos_web.schemas import VisionUpdate

    area_id = UUID("11111111-1111-1111-1111-111111111111")
    person_id = UUID("33333333-3333-3333-3333-333333333333")
    captured: dict[str, object] = {}

    async def fake_update_vision(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            name="Vision",
            description=None,
            status="active",
            stage=0,
            experience_points=0,
            experience_rate_per_hour=None,
            area_id=area_id,
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            people=(),
            tasks=(),
        )

    monkeypatch.setattr(visions.vision_services, "update_vision", fake_update_vision)

    response = asyncio.run(
        visions.update_vision(
            UUID("55555555-5555-5555-5555-555555555555"),
            VisionUpdate(area_id=area_id, person_ids=[person_id]),
            cast(AsyncSession, object()),
        )
    )

    assert captured["area_id"] == area_id
    assert captured["clear_area"] is False
    assert captured["person_ids"] == [person_id]
    assert captured["clear_people"] is False
    assert response["area_id"] == str(area_id)
    assert set(response).issuperset({"id", "name", "area_id"})


def test_web_habit_update_null_fields_translate_to_clear_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits
    from lifeos_web.schemas import HabitUpdate

    captured: dict[str, object] = {}

    async def fake_update_habit(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(habits.habit_services, "update_habit", fake_update_habit)
    monkeypatch.setattr(
        habits,
        "_habit_model_payload",
        lambda habit: {"id": str(habit.id)},
    )

    asyncio.run(
        habits.update_habit(
            UUID("55555555-5555-5555-5555-555555555555"),
            HabitUpdate(
                description=None,
                duration_days=None,
                cadence_weekdays=None,
                task_id=None,
            ),
            cast(AsyncSession, object()),
        )
    )

    assert captured["clear_description"] is True
    assert captured["clear_weekdays"] is True
    assert captured["clear_task"] is True


def test_web_habit_create_passes_repeat_count_and_cadence_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits
    from lifeos_web.schemas import HabitCreate

    captured: dict[str, object] = {}

    async def fake_create_habit(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(habits.habit_services, "create_habit", fake_create_habit)
    monkeypatch.setattr(
        habits,
        "_habit_model_payload",
        lambda habit: {"id": str(habit.id)},
    )

    asyncio.run(
        habits.create_habit(
            HabitCreate(
                title="Weekend calls",
                start_date=date(2026, 4, 9),
                repeat_count=3,
                cadence_frequency="weekly",
                cadence_weekdays=["saturday", "sunday"],
                target_per_cycle=1,
            ),
            cast(AsyncSession, object()),
        )
    )

    assert captured["duration_days"] is None
    assert captured["repeat_count"] == 3
    assert captured["end_date"] is None
    assert captured["cadence_frequency"] == "weekly"
    assert captured["cadence_weekdays"] == ["saturday", "sunday"]
    assert captured["target_per_cycle"] == 1


def test_web_habit_update_passes_end_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits
    from lifeos_web.schemas import HabitUpdate

    captured: dict[str, object] = {}

    async def fake_update_habit(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(id=UUID("22222222-2222-2222-2222-222222222222"))

    monkeypatch.setattr(habits.habit_services, "update_habit", fake_update_habit)
    monkeypatch.setattr(
        habits,
        "_habit_model_payload",
        lambda habit: {"id": str(habit.id)},
    )

    asyncio.run(
        habits.update_habit(
            UUID("55555555-5555-5555-5555-555555555555"),
            HabitUpdate(end_date=date(2026, 5, 1)),
            cast(AsyncSession, object()),
        )
    )

    assert captured["duration_days"] is None
    assert captured["repeat_count"] is None
    assert captured["end_date"] == date(2026, 5, 1)


def test_web_habit_actions_by_date_uses_lifecycle_aware_action_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits

    captured: dict[str, object] = {}

    async def fake_list_habit_actions(_session: object, **kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        habits.habit_action_services,
        "list_habit_actions",
        fake_list_habit_actions,
    )

    response = asyncio.run(
        habits.list_actions_by_date(
            date(2026, 4, 9),
            cast(AsyncSession, object()),
        )
    )

    assert "habit_status" not in captured
    assert captured["date_values"] == (date(2026, 4, 9),)
    assert response.items == []


def test_web_habit_actions_range_passes_reference_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits

    captured_expire: dict[str, object] = {}
    captured_count: dict[str, object] = {}
    captured_list: dict[str, object] = {}

    async def fake_reconcile_planning_habit_action_lifecycle(
        _session: object,
        **kwargs: object,
    ) -> int:
        captured_expire.update(kwargs)
        return 0

    async def fake_count_habit_actions(_session: object, **kwargs: object) -> int:
        captured_count.update(kwargs)
        return 0

    async def fake_list_habit_actions(_session: object, **kwargs: object) -> list[object]:
        captured_list.update(kwargs)
        return []

    monkeypatch.setattr(
        habits.planning_lifecycle_services,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile_planning_habit_action_lifecycle,
    )
    monkeypatch.setattr(
        habits.habit_action_services,
        "count_habit_actions",
        fake_count_habit_actions,
    )
    monkeypatch.setattr(
        habits.habit_action_services,
        "list_habit_actions",
        fake_list_habit_actions,
    )

    response = asyncio.run(
        habits.list_actions_in_range(
            cast(AsyncSession, object()),
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            reference_date=date(2026, 4, 9),
            cadence_frequency="weekly",
        )
    )

    assert captured_expire["start_date"] == date(2026, 4, 1)
    assert captured_expire["end_date"] == date(2026, 4, 30)
    assert captured_expire["reference_date"] == date(2026, 4, 9)
    assert captured_count["start_date"] == date(2026, 4, 1)
    assert captured_count["end_date"] == date(2026, 4, 30)
    assert captured_count["cadence_frequency"] == "weekly"
    assert "reference_date" not in captured_count
    assert captured_list["start_date"] == date(2026, 4, 1)
    assert captured_list["end_date"] == date(2026, 4, 30)
    assert captured_list["cadence_frequency"] == "weekly"
    assert "reference_date" not in captured_list
    assert captured_list["limit"] == 1000
    assert captured_list["offset"] == 0
    assert response.items == []
    assert response.meta == {
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "reference_date": "2026-04-09",
        "cadence_frequency": "weekly",
    }


def test_web_habit_actions_for_habit_uses_center_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits

    captured: dict[str, object] = {}

    async def fake_list_habit_actions(_session: object, **kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        habits.habit_action_services,
        "list_habit_actions",
        fake_list_habit_actions,
    )

    response = asyncio.run(
        habits.list_actions_for_habit(
            UUID("55555555-5555-5555-5555-555555555555"),
            cast(AsyncSession, object()),
            center_date=date(2026, 7, 20),
            days_before=14,
            days_after=21,
            status_filter="pending",
            size=50,
        )
    )

    assert captured["habit_id"] == UUID("55555555-5555-5555-5555-555555555555")
    assert captured["status"] == "pending"
    assert captured["start_date"] == date(2026, 7, 6)
    assert captured["end_date"] == date(2026, 8, 10)
    assert captured["limit"] == 50
    assert response.items == []
    assert response.meta == {
        "status_filter": "pending",
        "center_date": "2026-07-20",
        "days_before": 14,
        "days_after": 21,
    }


def test_web_habit_action_update_null_notes_maps_to_clear_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits
    from lifeos_web.schemas import HabitActionUpdate

    captured: dict[str, object] = {}

    async def fake_update_habit_action(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
        )

    monkeypatch.setattr(
        habits.habit_action_services, "update_habit_action", fake_update_habit_action
    )

    def fake_habit_action_payload(action: Any) -> dict[str, str]:
        return {"id": str(action.id)}

    monkeypatch.setattr(habits, "_habit_action_payload", fake_habit_action_payload)

    asyncio.run(
        habits.update_action(
            UUID("66666666-6666-6666-6666-666666666666"),
            UUID("77777777-7777-7777-7777-777777777777"),
            HabitActionUpdate(notes=None),
            cast(AsyncSession, object()),
        )
    )

    assert captured["clear_notes"] is True


def test_web_habit_action_by_date_update_null_notes_maps_to_clear_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import habits
    from lifeos_web.schemas import HabitActionUpdate

    captured: dict[str, object] = {}

    async def fake_update_habit_action_by_date(
        _session: object,
        **kwargs: object,
    ) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
        )

    monkeypatch.setattr(
        habits.habit_action_services,
        "update_habit_action_by_date",
        fake_update_habit_action_by_date,
    )

    def fake_habit_action_payload(action: Any) -> dict[str, str]:
        return {"id": str(action.id)}

    monkeypatch.setattr(habits, "_habit_action_payload", fake_habit_action_payload)

    asyncio.run(
        habits.update_action_by_date(
            UUID("55555555-5555-5555-5555-555555555555"),
            datetime(2026, 6, 1, tzinfo=timezone.utc).date(),
            HabitActionUpdate(notes=None),
            cast(AsyncSession, object()),
        )
    )

    assert captured["clear_notes"] is True


def test_web_timelog_update_null_fields_translate_to_clear_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db.services.timelog_support import TimelogUpdateInput
    from lifeos_web.routers import timelogs
    from lifeos_web.schemas import TimelogUpdate

    captured_changes: TimelogUpdateInput | None = None

    async def fake_update_timelog(
        _session: object,
        *,
        changes: TimelogUpdateInput,
        **_kwargs: object,
    ) -> object:
        nonlocal captured_changes
        captured_changes = changes
        return {
            "title": "work",
            "tracking_method": "manual",
            "start_time": datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            "end_time": datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            "location": None,
            "energy_level": None,
            "notes": None,
            "area_id": None,
            "task_id": None,
            "person_ids": [],
            "tag_ids": [],
            "created_at": datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            "deleted_at": None,
        }

    monkeypatch.setattr(timelogs.timelog_services, "update_timelog", fake_update_timelog)

    asyncio.run(
        timelogs.update_timelog(
            UUID("55555555-5555-5555-5555-555555555555"),
            TimelogUpdate(
                location=None,
                energy_level=None,
                notes=None,
                area_id=None,
                task_id=None,
                person_ids=[],
            ),
            cast(AsyncSession, object()),
        )
    )

    assert captured_changes is not None
    assert captured_changes.clear_location is True
    assert captured_changes.clear_energy_level is True
    assert captured_changes.clear_notes is True
    assert captured_changes.clear_area is True
    assert captured_changes.clear_task is True
    assert captured_changes.clear_people is True


def test_web_timelog_batch_task_replace_maps_to_lifeos_task_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import timelogs
    from lifeos_web.schemas import TimelogBatchTaskUpdate, TimelogBatchUpdate

    task_id = UUID("22222222-2222-2222-2222-222222222222")
    timelog_id = UUID("11111111-1111-1111-1111-111111111111")
    captured: dict[str, TimelogBatchUpdateInput] = {}

    async def fake_batch_update_timelogs(
        _session: object,
        *,
        timelog_ids: list[UUID],
        changes: TimelogBatchUpdateInput,
    ) -> object:
        assert timelog_ids == [timelog_id]
        captured["changes"] = changes
        return SimpleNamespace(
            updated_count=1,
            unchanged_ids=(),
            failed_ids=(),
            errors=(),
        )

    monkeypatch.setattr(
        timelogs.timelog_services,
        "batch_update_timelogs",
        fake_batch_update_timelogs,
    )

    response = asyncio.run(
        timelogs.batch_update_timelogs(
            TimelogBatchUpdate(
                timelog_ids=[timelog_id],
                update_type="task",
                task=TimelogBatchTaskUpdate(mode="replace", task_id=task_id),
            ),
            cast(AsyncSession, object()),
        )
    )

    changes = captured["changes"].changes
    assert changes.task_id == task_id
    assert changes.clear_task is False
    assert response["updated_count"] == 1


def test_web_tag_create_maps_to_lifeos_tag_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags
    from lifeos_web.schemas import TagCreate

    captured: dict[str, object] = {}

    async def fake_create_tag(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return TagView(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            name="project",
            entity_type="note",
            category="general",
            description=None,
            color=None,
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            people=(),
        )

    monkeypatch.setattr(tags.tag_services, "create_tag", fake_create_tag)

    response = asyncio.run(
        tags.create_tag(
            TagCreate(name="Project", entity_type="note", category="general"),
            cast(AsyncSession, object()),
        )
    )

    assert captured == {
        "name": "Project",
        "entity_type": "note",
        "category": "general",
        "description": None,
        "color": None,
    }
    assert response["id"] == "11111111-1111-1111-1111-111111111111"
    assert response["name"] == "project"


def test_web_tag_list_selector_payload_excludes_unconsumed_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags

    tag = TagView(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        name="project",
        entity_type="note",
        category="general",
        description="Internal description",
        color="#ffffff",
        created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        deleted_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        people=(PersonSummaryView(id=UUID("22222222-2222-2222-2222-222222222222"), name="A"),),
    )

    async def fake_list_tags(_session: object, **kwargs: object) -> list[TagView]:
        assert kwargs["entity_type"] == "note"
        assert kwargs["limit"] == 1000
        return [tag]

    monkeypatch.setattr(tags.tag_services, "list_tags", fake_list_tags)

    response = asyncio.run(
        tags.list_tags(
            cast(AsyncSession, object()),
            entity_type="note",
            size=1000,
            fields="selector",
        )
    )

    payload = cast(dict[str, object], response.items[0])
    assert payload == {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "project",
        "entity_type": "note",
        "category": "general",
    }
    assert "description" not in payload
    assert "color" not in payload
    assert "created_at" not in payload
    assert "updated_at" not in payload
    assert "deleted_at" not in payload
    assert "people" not in payload
    assert response.meta["fields"] == "selector"


def test_web_tag_categories_include_builtin_and_existing_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags

    async def fake_list_tag_categories(
        _session: object,
        *,
        entity_type: str | None = None,
    ) -> list[str]:
        assert entity_type == "person"
        return ["community", "relationship"]

    monkeypatch.setattr(tags.tag_services, "list_tag_categories", fake_list_tag_categories)

    response = asyncio.run(
        tags.list_tag_categories(cast(AsyncSession, object()), entity_type="person")
    )

    values = [item["value"] for item in response]
    assert values == [
        "community",
        "general",
        "location",
        "profession",
        "relation",
        "relationship",
        "team",
    ]


def test_web_tag_category_create_returns_normalized_option() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags
    from lifeos_web.schemas import TagCategoryCreate

    response = asyncio.run(
        tags.create_tag_category(
            TagCategoryCreate(label="Close Circle"),
            entity_type="person",
        )
    )

    assert response == {
        "value": "close_circle",
        "label": "Close Circle",
        "entity_type": "person",
    }


def test_web_tag_category_rename_maps_to_lifeos_tag_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags
    from lifeos_web.schemas import TagCategoryUpdate

    captured: dict[str, object] = {}

    async def fake_rename_tag_category(_session: object, **kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(tags.tag_services, "rename_tag_category", fake_rename_tag_category)

    response = asyncio.run(
        tags.rename_tag_category(
            "relationship",
            TagCategoryUpdate(label="Close Circle"),
            cast(AsyncSession, object()),
            entity_type="person",
        )
    )

    assert captured == {
        "entity_type": "person",
        "category": "relationship",
        "new_category": "close_circle",
    }
    assert response["value"] == "close_circle"
    assert response["entity_type"] == "person"


def test_web_tag_bulk_category_update_returns_updated_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags
    from lifeos_web.schemas import TagBulkCategoryUpdate

    tag_id = UUID("11111111-1111-1111-1111-111111111111")
    missing_id = UUID("22222222-2222-2222-2222-222222222222")
    updated_tag = TagView(
        id=tag_id,
        name="mentor",
        entity_type="person",
        category="relationship",
        description=None,
        color=None,
        created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        deleted_at=None,
        people=(),
    )

    async def fake_bulk_update_tag_categories(
        _session: object,
        *,
        tag_ids: list[UUID],
        category: str,
    ) -> tuple[list[TagView], list[UUID], list[str]]:
        assert tag_ids == [tag_id, missing_id]
        assert category == "relationship"
        return [updated_tag], [missing_id], [f"Tag {missing_id} was not found"]

    monkeypatch.setattr(
        tags.tag_services,
        "bulk_update_tag_categories",
        fake_bulk_update_tag_categories,
    )

    response = asyncio.run(
        tags.bulk_update_tag_categories(
            TagBulkCategoryUpdate(ids=[tag_id, missing_id], category="relationship"),
            cast(AsyncSession, object()),
        )
    )

    assert response["updated_count"] == 1
    assert response["failed_ids"] == [str(missing_id)]
    updated_tags = cast(list[dict[str, object]], response["updated_tags"])
    assert updated_tags[0]["category"] == "relationship"


def test_web_tag_usage_endpoint_returns_tagged_record_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import tags

    tag_id = UUID("11111111-1111-1111-1111-111111111111")
    tag = TagView(
        id=tag_id,
        name="mentor",
        entity_type="person",
        category="relationship",
        description=None,
        color=None,
        created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        deleted_at=None,
        people=(),
    )

    async def fake_get_tag(_session: object, *, tag_id: UUID) -> TagView | None:
        assert tag_id == UUID("11111111-1111-1111-1111-111111111111")
        return tag

    async def fake_count_tag_usage(_session: object, *, tag_id: UUID) -> int:
        assert tag_id == UUID("11111111-1111-1111-1111-111111111111")
        return 12

    monkeypatch.setattr(tags.tag_services, "get_tag", fake_get_tag)
    monkeypatch.setattr(tags.tag_services, "count_tag_usage", fake_count_tag_usage)

    response = asyncio.run(tags.get_tag_usage(tag_id, cast(AsyncSession, object())))

    assert response == {
        "tag_id": str(tag_id),
        "tag_name": "mentor",
        "entity_type": "person",
        "category": "relationship",
        "usage_by_entity_type": {"person": 12},
        "total_usage": 12,
    }


def test_web_stats_tag_usage_endpoint_returns_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import stats

    tag_id = UUID("11111111-1111-1111-1111-111111111111")

    async def fake_count_tag_usage_by_entity_type(
        _session: object,
        *,
        entity_type: str,
    ) -> dict[UUID, int]:
        assert entity_type == "person"
        return {tag_id: 12}

    monkeypatch.setattr(
        stats.tag_services,
        "count_tag_usage_by_entity_type",
        fake_count_tag_usage_by_entity_type,
    )

    response = asyncio.run(
        stats.get_tag_usage_by_entity_type("person", cast(AsyncSession, object()))
    )

    assert response == {
        "entity_type": "person",
        "tag_stats": [{"id": str(tag_id), "usage_count": 12}],
        "total_tags": 1,
    }


def test_web_stats_aggregated_areas_uses_mayan_calendar_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import stats

    area_id = UUID("11111111-1111-1111-1111-111111111111")
    captured_ranges: list[tuple[date, date]] = []

    async def fake_get_range(
        _session: object,
        *,
        start_date: date,
        end_date: date,
    ) -> object:
        captured_ranges.append((start_date, end_date))
        return SimpleNamespace(
            rows=(
                SimpleNamespace(
                    area_id=area_id,
                    minutes=60,
                ),
            )
        )

    monkeypatch.setattr(
        stats.timelog_stats,
        "get_timelog_stats_groupby_area_for_range",
        fake_get_range,
    )

    response = asyncio.run(
        stats.list_aggregated_areas(
            cast(AsyncSession, object()),
            granularity="month",
            start=date(2026, 7, 24),
            end=date(2026, 7, 27),
            calendar_system="mayan_13_moon",
            first_day_of_week=1,
        )
    )

    assert captured_ranges == [
        (date(2026, 6, 27), date(2026, 7, 24)),
        (date(2026, 7, 25), date(2026, 7, 25)),
        (date(2026, 7, 26), date(2026, 8, 22)),
    ]
    assert response.meta["calendar_system"] == "mayan_13_moon"
    assert response.items == [
        {
            "granularity": "month",
            "period_start": "2026-06-27",
            "period_end": "2026-07-24",
            "area_id": str(area_id),
            "minutes": 60,
        },
        {
            "granularity": "month",
            "period_start": "2026-07-25",
            "period_end": "2026-07-25",
            "area_id": str(area_id),
            "minutes": 60,
        },
        {
            "granularity": "month",
            "period_start": "2026-07-26",
            "period_end": "2026-08-22",
            "area_id": str(area_id),
            "minutes": 60,
        },
    ]


def test_web_stats_aggregated_areas_rejects_invalid_calendar_system() -> None:
    pytest.importorskip("fastapi")

    from fastapi import HTTPException

    from lifeos_web.routers import stats

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            stats.list_aggregated_areas(
                cast(AsyncSession, object()),
                granularity="month",
                start=date(2026, 7, 24),
                end=date(2026, 7, 27),
                calendar_system="martian",
            )
        )

    assert exc_info.value.status_code == 400
    assert "calendar_system" in str(exc_info.value.detail)


def test_web_note_person_usage_stats_endpoint_returns_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db.services.notes import NotePersonUsage
    from lifeos_web.routers import notes

    person_id = UUID("11111111-1111-1111-1111-111111111111")

    async def fake_count_note_usage_by_person(_session: object) -> list[NotePersonUsage]:
        return [
            NotePersonUsage(
                id=person_id,
                name="Alice",
                display_name="Alice",
                usage_count=3,
            )
        ]

    monkeypatch.setattr(
        notes.note_services,
        "count_note_usage_by_person",
        fake_count_note_usage_by_person,
    )

    response = asyncio.run(notes.get_note_person_usage_stats(cast(AsyncSession, object())))

    assert response == {
        "person_stats": [
            {
                "id": str(person_id),
                "name": "Alice",
                "display_name": "Alice",
                "usage_count": 3,
            }
        ],
        "total_persons": 1,
    }


def test_web_note_create_maps_selector_associations_to_lifeos_note_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import notes
    from lifeos_web.schemas import NoteCreate

    tag_id = UUID("11111111-1111-1111-1111-111111111111")
    person_id = UUID("22222222-2222-2222-2222-222222222222")
    task_id = UUID("33333333-3333-3333-3333-333333333333")
    timelog_id = UUID("44444444-4444-4444-4444-444444444444")
    habit_action_id = UUID("66666666-6666-6666-6666-666666666666")
    captured: dict[str, object] = {}

    async def fake_create_note(_session: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            id=UUID("55555555-5555-5555-5555-555555555555"),
            content=kwargs["content"],
            created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
            deleted_at=None,
            tags=(),
            people=(),
            tasks=(),
            visions=(),
            events=(),
            timelogs=(),
            habit_actions=(),
        )

    monkeypatch.setattr(notes.note_services, "create_note", fake_create_note)

    asyncio.run(
        notes.create_note(
            NoteCreate(
                content="Capture context",
                tag_ids=[tag_id],
                person_ids=[person_id],
                task_id=task_id,
                timelog_ids=[timelog_id],
                habit_action_ids=[habit_action_id],
            ),
            cast(AsyncSession, object()),
        )
    )

    assert captured == {
        "content": "Capture context",
        "tag_ids": [tag_id],
        "person_ids": [person_id],
        "task_ids": [task_id],
        "timelog_ids": [timelog_id],
        "habit_action_ids": [habit_action_id],
    }


def test_web_note_payload_exposes_primary_task_for_notes_page() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.notes import _note_payload

    task = TaskSummaryView(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        vision_id=UUID("44444444-4444-4444-4444-444444444444"),
        parent_task_id=None,
        content="Investigate note association",
        status="todo",
    )
    tag = TagSummaryView(
        id=UUID("66666666-6666-6666-6666-666666666666"),
        name="research",
    )
    person = PersonSummaryView(
        id=UUID("77777777-7777-7777-7777-777777777777"),
        name="Alice",
    )
    note = NoteView(
        id=UUID("55555555-5555-5555-5555-555555555555"),
        content="Capture context",
        created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        deleted_at=None,
        tags=(tag,),
        people=(person,),
        tasks=(task,),
        habit_actions=(
            HabitActionSummaryView(
                id=UUID("88888888-8888-8888-8888-888888888888"),
                habit_id=UUID("99999999-9999-9999-9999-999999999999"),
                habit_title="Morning Walk",
                action_date=date(2026, 7, 5),
                status="done",
            ),
        ),
    )

    payload = _note_payload(note)

    assert payload["tasks"] == [
        {
            "id": str(task.id),
            "vision_id": str(task.vision_id),
            "parent_task_id": None,
            "content": "Investigate note association",
            "status": "todo",
        }
    ]
    assert payload["task"] == payload["tasks"][0]
    assert payload["tags"] == [
        {
            "id": str(tag.id),
            "name": "research",
            "entity_type": "note",
            "category": "general",
            "description": None,
            "color": None,
            "created_at": "",
            "updated_at": "",
        }
    ]
    assert payload["people"] == [
        {
            "id": str(person.id),
            "name": "Alice",
            "display_name": "Alice",
            "primary_nickname": "Alice",
            "birth_date": None,
            "location": None,
            "tags": [],
        }
    ]
    assert payload["habit_actions"] == [
        {
            "id": "88888888-8888-8888-8888-888888888888",
            "habit_id": "99999999-9999-9999-9999-999999999999",
            "habit_title": "Morning Walk",
            "action_date": "2026-07-05",
            "status": "done",
        }
    ]
    assert "persons" not in payload


def test_web_note_payload_uses_null_primary_task_without_association() -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.notes import _note_payload

    note = NoteView(
        id=UUID("55555555-5555-5555-5555-555555555555"),
        content="Capture context",
        created_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc),
        deleted_at=None,
    )

    payload = _note_payload(note)

    assert payload["tasks"] == []
    assert payload["task"] is None
    assert payload["people"] == []
    assert "persons" not in payload
    assert payload["tags"] == []


def test_web_timezone_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
    )
    monkeypatch.delenv("LIFEOS_TIMEZONE", raising=False)
    clear_config_cache()

    initial = asyncio.run(get_preference("system.timezone"))
    assert initial["value"] == "UTC"

    updated = asyncio.run(
        set_preference(
            "system.timezone",
            PreferenceUpdate(value="America/Toronto", module="system"),
        )
    )
    assert updated["value"] == "America/Toronto"

    reloaded = asyncio.run(get_preference("system.timezone"))
    assert reloaded["value"] == "America/Toronto"
    assert "LIFEOS_TIMEZONE" not in os.environ

    assert 'timezone = "America/Toronto"' in config_path.read_text(encoding="utf-8")


def test_web_timezone_preference_converges_env_override_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db import session as db_session
    from lifeos_web.routers.preferences import get_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
    )
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/New_York")
    monkeypatch.setattr(db_session, "_CACHED_ENGINE", CachedEngineSentinel())
    clear_config_cache()

    current = asyncio.run(get_preference("system.timezone"))

    assert current["value"] == "America/New_York"
    assert 'timezone = "America/New_York"' in config_path.read_text(encoding="utf-8")


def test_web_timezone_preference_updates_process_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
    )
    monkeypatch.setenv("LIFEOS_TIMEZONE", "America/New_York")
    clear_config_cache()

    updated = asyncio.run(
        set_preference(
            "system.timezone",
            PreferenceUpdate(value="America/Toronto", module="system"),
        )
    )
    reloaded = asyncio.run(get_preference("system.timezone"))

    assert updated["value"] == "America/Toronto"
    assert reloaded["value"] == "America/Toronto"
    assert os.environ["LIFEOS_TIMEZONE"] == "America/Toronto"
    assert 'timezone = "America/Toronto"' in config_path.read_text(encoding="utf-8")


def test_web_vision_experience_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers import preferences as preferences_router
    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        vision_experience_rate_per_hour=60,
    )
    sync_calls: list[str] = []

    async def fake_sync_dependents(key: str) -> None:
        sync_calls.append(key)

    monkeypatch.setattr(
        preferences_router,
        "_sync_config_preference_dependents",
        fake_sync_dependents,
    )

    updated = asyncio.run(
        set_preference(
            "visions.experience_rate_per_hour",
            PreferenceUpdate(value=120, module="visions"),
        )
    )
    assert updated["value"] == 120

    reloaded = asyncio.run(get_preference("visions.experience_rate_per_hour"))
    assert reloaded["value"] == 120

    assert "vision_experience_rate_per_hour = 120" in config_path.read_text(encoding="utf-8")
    assert sync_calls == ["visions.experience_rate_per_hour"]


def test_web_theme_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_cli.db import session as db_session
    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        theme="system",
    )
    monkeypatch.setattr(db_session, "_CACHED_ENGINE", CachedEngineSentinel())

    updated = asyncio.run(
        set_preference(
            "appearance.theme",
            PreferenceUpdate(value="night", module="appearance"),
        )
    )
    assert updated["value"] == "night"

    clear_config_cache()
    reloaded = asyncio.run(get_preference("appearance.theme"))
    assert reloaded["value"] == "night"

    assert 'theme = "night"' in config_path.read_text(encoding="utf-8")


def test_web_language_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        language="en",
    )
    monkeypatch.delenv("LIFEOS_LANGUAGE", raising=False)
    clear_config_cache()

    updated = asyncio.run(
        set_preference(
            "system.language",
            PreferenceUpdate(value="auto", module="system"),
        )
    )

    assert updated["value"] == "auto"
    clear_config_cache()
    reloaded = asyncio.run(get_preference("system.language"))
    assert reloaded["value"] == "auto"
    assert 'language = "auto"' in config_path.read_text(encoding="utf-8")


def test_web_visible_modules_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
    )

    updated = asyncio.run(
        set_preference(
            "navigation.visible_modules",
            PreferenceUpdate(value=["visions", "notes", "settings"], module="navigation"),
        )
    )

    assert updated["value"] == ["visions", "notes", "settings"]
    clear_config_cache()
    reloaded = asyncio.run(get_preference("navigation.visible_modules"))
    assert reloaded["value"] == ["visions", "notes", "settings"]
    assert 'navigation_visible_modules = ["visions", "notes", "settings"]' in (
        config_path.read_text(encoding="utf-8")
    )


def test_web_calendar_preferences_persist_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
    )

    updated_system = asyncio.run(
        set_preference(
            "calendar.system",
            PreferenceUpdate(value="mayan_13_moon", module="calendar"),
        )
    )
    updated_first_day = asyncio.run(
        set_preference(
            "calendar.first_day_of_week",
            PreferenceUpdate(value=7, module="calendar"),
        )
    )
    updated_anchor_date = asyncio.run(
        set_preference(
            "calendar.seven_year_anchor_date",
            PreferenceUpdate(value="2026-07-20", module="calendar"),
        )
    )

    assert updated_system["value"] == "mayan_13_moon"
    assert updated_first_day["value"] == 7
    assert updated_anchor_date["value"] == "2026-07-20"
    clear_config_cache()
    assert asyncio.run(get_preference("calendar.system"))["value"] == "mayan_13_moon"
    assert asyncio.run(get_preference("calendar.first_day_of_week"))["value"] == 7
    assert asyncio.run(get_preference("calendar.seven_year_anchor_date"))["value"] == "2026-07-20"

    content = config_path.read_text(encoding="utf-8")
    assert 'calendar_system = "mayan_13_moon"' in content
    assert "calendar_first_day_of_week = 7" in content
    assert 'calendar_seven_year_anchor_date = "2026-07-20"' in content


def test_web_note_collapse_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
    )

    updated = asyncio.run(
        set_preference(
            "notes.card_min_collapsed_lines",
            PreferenceUpdate(value=11, module="notes"),
        )
    )

    assert updated["value"] == 11
    clear_config_cache()
    reloaded = asyncio.run(get_preference("notes.card_min_collapsed_lines"))
    assert reloaded["value"] == 11
    assert "notes_card_min_collapsed_lines = 11" in config_path.read_text(encoding="utf-8")


def test_web_default_inbox_vision_preference_persists_to_cli_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("fastapi")

    from lifeos_web.routers.preferences import PreferenceUpdate, get_preference, set_preference

    config_path = install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
    )
    vision_id = "11111111-1111-1111-1111-111111111111"

    updated = asyncio.run(
        set_preference(
            "todos.default_inbox_vision",
            PreferenceUpdate(value=vision_id, module="todos"),
        )
    )

    assert updated["value"] == vision_id
    clear_config_cache()
    reloaded = asyncio.run(get_preference("todos.default_inbox_vision"))
    assert reloaded["value"] == vision_id
    assert f'todos_default_inbox_vision = "{vision_id}"' in config_path.read_text(encoding="utf-8")
