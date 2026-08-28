from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import Column, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.backend_policy import backend_policy_for_drivername
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.body_measurement import BodyMeasurement
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.models.menstrual import MenstrualDay, MenstrualFactor
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services import data_ops
from lifeos_cli.db.types import UTCDateTime
from tests.support import sqlite_session_factory


class FakeBatchSession:
    @asynccontextmanager
    async def begin_nested(self):
        yield self


class RecordingSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> None:
        self.statements.append(statement)


def test_batch_update_resource_parses_typed_timelog_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(session: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "timelog", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="timelog",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "start_time": "2026-04-10T13:00:00+00:00",
                    "end_time": "2026-04-10T14:30:00+00:00",
                    "area_id": "22222222-2222-2222-2222-222222222222",
                    "task_id": "33333333-3333-3333-3333-333333333333",
                    "tag_ids": ["44444444-4444-4444-4444-444444444444"],
                    "person_ids": ["55555555-5555-5555-5555-555555555555"],
                }
            ],
        )
    )

    assert report.updated_count == 1
    assert captured["timelog_id"] == UUID("11111111-1111-1111-1111-111111111111")
    changes = captured["changes"]
    assert isinstance(changes, data_ops.timelogs.TimelogUpdateInput)
    assert str(changes.start_time) == "2026-04-10 13:00:00+00:00"
    assert str(changes.end_time) == "2026-04-10 14:30:00+00:00"
    assert changes.area_id == UUID("22222222-2222-2222-2222-222222222222")
    assert changes.task_id == UUID("33333333-3333-3333-3333-333333333333")
    assert changes.tag_ids == [UUID("44444444-4444-4444-4444-444444444444")]
    assert changes.person_ids == [UUID("55555555-5555-5555-5555-555555555555")]


def test_parse_datetime_snapshot_values_normalizes_offsets_to_utc() -> None:
    column: Column[datetime] = Column("start_time", UTCDateTime())

    parsed = data_ops._parse_column_value(column, "2026-06-13T21:00:00-04:00")

    assert parsed == datetime(2026, 6, 14, 1, 0, tzinfo=UTC)


def test_serialize_datetime_snapshot_values_uses_explicit_utc() -> None:
    value = datetime.fromisoformat("2026-06-13T21:00:00-04:00")

    serialized = data_ops._serialize_scalar(value)

    assert serialized == "2026-06-14T01:00:00Z"


def test_batch_update_resource_parses_extended_note_relation_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(session: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "note", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="note",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "tag_ids": ["22222222-2222-2222-2222-222222222222"],
                    "task_ids": [
                        "33333333-3333-3333-3333-333333333333",
                        "44444444-4444-4444-4444-444444444444",
                    ],
                    "vision_ids": ["55555555-5555-5555-5555-555555555555"],
                    "event_ids": ["66666666-6666-6666-6666-666666666666"],
                    "timelog_ids": ["77777777-7777-7777-7777-777777777777"],
                    "habit_action_ids": ["88888888-8888-8888-8888-888888888888"],
                }
            ],
        )
    )

    assert report.updated_count == 1
    assert captured["note_id"] == UUID("11111111-1111-1111-1111-111111111111")
    assert captured["tag_ids"] == [UUID("22222222-2222-2222-2222-222222222222")]
    assert captured["task_ids"] == [
        UUID("33333333-3333-3333-3333-333333333333"),
        UUID("44444444-4444-4444-4444-444444444444"),
    ]
    assert captured["vision_ids"] == [UUID("55555555-5555-5555-5555-555555555555")]
    assert captured["event_ids"] == [UUID("66666666-6666-6666-6666-666666666666")]
    assert captured["timelog_ids"] == [UUID("77777777-7777-7777-7777-777777777777")]
    assert captured["habit_action_ids"] == [UUID("88888888-8888-8888-8888-888888888888")]


def test_batch_update_note_rejects_legacy_single_task_field() -> None:
    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="note",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "task_id": "33333333-3333-3333-3333-333333333333",
                }
            ],
        )
    )

    assert report.updated_count == 0
    assert report.failed_count == 1
    assert report.failures[0].message.endswith(
        "`task_ids`, `vision_ids`, `event_ids`, `timelog_ids`, or `habit_action_ids`."
    )


def test_batch_update_resource_reports_attempted_rows_on_stopping_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    async def fake_update(session: object, **kwargs: object) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ValueError("boom")

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "tag", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="tag",
            rows=[
                {"id": "11111111-1111-1111-1111-111111111111", "name": "alpha"},
                {"id": "22222222-2222-2222-2222-222222222222", "name": "beta"},
                {"id": "33333333-3333-3333-3333-333333333333", "name": "gamma"},
            ],
            continue_on_error=False,
        )
    )

    assert call_count == 2
    assert report.processed_count == 2
    assert report.updated_count == 1
    assert report.failed_count == 1
    assert report.failures[0].index == 2


def test_import_bundle_applies_base_rows_before_relations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_order: list[tuple[str, str]] = []

    async def fake_truncate(session: object) -> None:
        call_order.append(("truncate", "-"))

    async def fake_apply(
        session: object,
        *,
        prepared_row: data_ops.PreparedSnapshotRow,
    ) -> str:
        call_order.append(("base", prepared_row.resource))
        return "created"

    async def fake_sync(
        session: object,
        *,
        prepared_row: data_ops.PreparedSnapshotRow,
    ) -> None:
        call_order.append(("sync", prepared_row.resource))

    async def fake_hooks(session: object, *, resources: set[str]) -> None:
        call_order.append(("hooks", ",".join(sorted(resources))))

    monkeypatch.setattr(data_ops, "truncate_supported_data", fake_truncate)
    monkeypatch.setattr(data_ops, "_apply_snapshot_base_row", fake_apply)
    monkeypatch.setattr(data_ops, "_sync_snapshot_relations", fake_sync)
    monkeypatch.setattr(data_ops, "run_post_import_hooks", fake_hooks)

    report = asyncio.run(
        data_ops.import_bundle(
            cast(AsyncSession, object()),
            bundle_rows={
                "person": [{"id": "11111111-1111-1111-1111-111111111111"}],
                "tag": [{"id": "22222222-2222-2222-2222-222222222222"}],
            },
            replace_existing=True,
        )
    )

    base_positions = [index for index, call in enumerate(call_order) if call[0] == "base"]
    sync_positions = [index for index, call in enumerate(call_order) if call[0] == "sync"]

    assert report.created_count == 2
    assert report.updated_count == 0
    assert report.imported_resources == ("person", "tag")
    assert call_order[0] == ("truncate", "-")
    assert max(base_positions) < min(sync_positions)
    assert call_order[-1] == ("hooks", "person,tag")


def test_truncate_supported_data_uses_backend_replace_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    postgres_session = RecordingSession()
    sqlite_session = RecordingSession()

    monkeypatch.setattr(
        data_ops,
        "get_database_settings",
        lambda: SimpleNamespace(
            database_schema="lifeos",
            backend_policy=backend_policy_for_drivername("postgresql+psycopg"),
        ),
    )
    asyncio.run(data_ops.truncate_supported_data(cast(AsyncSession, postgres_session)))

    assert len(postgres_session.statements) == 1
    assert "TRUNCATE TABLE" in str(postgres_session.statements[0])
    assert "CASCADE" in str(postgres_session.statements[0])

    monkeypatch.setattr(
        data_ops,
        "get_database_settings",
        lambda: SimpleNamespace(
            database_schema=None,
            backend_policy=backend_policy_for_drivername("sqlite+aiosqlite"),
        ),
    )
    asyncio.run(data_ops.truncate_supported_data(cast(AsyncSession, sqlite_session)))

    assert len(sqlite_session.statements) > 1
    assert all(str(statement).startswith("DELETE FROM ") for statement in sqlite_session.statements)


def test_read_bundle_rejects_missing_manifest(tmp_path: Path) -> None:
    bundle_path = tmp_path / "broken-bundle.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("note.jsonl", '{"id":"11111111-1111-1111-1111-111111111111"}\n')

    with pytest.raises(data_ops.DataOperationError, match="manifest.json"):
        data_ops.read_bundle(bundle_path)


def test_read_bundle_rejects_legacy_schema_version(tmp_path: Path) -> None:
    bundle_path = tmp_path / "legacy-bundle.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", '{"schema_version": 1}\n')

    with pytest.raises(
        data_ops.DataOperationError,
        match=(
            "Older bundle schemas are not supported after habit-action notes moved to linked notes"
        ),
    ):
        data_ops.read_bundle(bundle_path)


def test_read_bundle_maps_legacy_person_entry_name(tmp_path: Path) -> None:
    bundle_path = tmp_path / "legacy-person-bundle.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", '{"schema_version": 3}\n')
        archive.writestr(
            "people.jsonl",
            '{"id":"11111111-1111-1111-1111-111111111111"}\n',
        )

    payload = data_ops.read_bundle(bundle_path)

    assert payload.resources["person"] == [{"id": "11111111-1111-1111-1111-111111111111"}]
    assert "people" not in payload.resources


def test_validate_upsert_key_rejects_unsupported_resources_and_fields() -> None:
    data_ops.validate_upsert_key("area", "name")
    data_ops.validate_upsert_key("habit", "title")

    with pytest.raises(data_ops.DataOperationError, match="supported keys: none"):
        data_ops.validate_upsert_key("note", "content")
    with pytest.raises(data_ops.DataOperationError, match="supported keys: name"):
        data_ops.validate_upsert_key("area", "display_order")


def test_resolve_upsert_row_id_matches_existing_record_by_natural_key() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await data_ops.import_resource_snapshot(
                    session,
                    resource="area",
                    rows=[{"id": str(uuid4()), "name": "Health"}],
                )
                await session.commit()

            async with session_factory() as session:
                area_id = (
                    await session.execute(select(Area.id).where(Area.name == "Health"))
                ).scalar_one()

                resolved = await data_ops.resolve_upsert_row_id(
                    session,
                    resource="area",
                    row={"name": "Health", "color": "#111111"},
                    key_field="name",
                    index=1,
                )

                assert UUID(resolved["id"]) == area_id
                assert resolved["color"] == "#111111"

    asyncio.run(scenario())


def test_natural_key_upserts_ignore_soft_deleted_matches_for_every_supported_resource() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                cases: list[tuple[str, str, object, Any, Any]] = [
                    ("area", "name", "Health", Area(name="Health"), Area(name="Health")),
                    ("vision", "name", "Launch", Vision(name="Launch"), Vision(name="Launch")),
                    ("person", "name", "Alice", Person(name="Alice"), Person(name="Alice")),
                    (
                        "habit",
                        "title",
                        "Walk",
                        Habit(title="Walk", start_date=date(2026, 8, 1), duration_days=30),
                        Habit(title="Walk", start_date=date(2026, 9, 1), duration_days=30),
                    ),
                    (
                        "body-measurement",
                        "measured_at",
                        datetime(2026, 8, 19, 8, tzinfo=UTC),
                        BodyMeasurement(
                            measured_at=datetime(2026, 8, 19, 8, tzinfo=UTC),
                            weight_kg=Decimal("62.0"),
                        ),
                        BodyMeasurement(
                            measured_at=datetime(2026, 8, 19, 8, tzinfo=UTC),
                            weight_kg=Decimal("63.0"),
                        ),
                    ),
                    (
                        "menstrual",
                        "log_date",
                        date(2026, 8, 19),
                        MenstrualDay(log_date=date(2026, 8, 19)),
                        MenstrualDay(log_date=date(2026, 8, 19)),
                    ),
                    (
                        "menstrual-factor",
                        "name",
                        "travel",
                        MenstrualFactor(name="travel"),
                        MenstrualFactor(name="travel"),
                    ),
                ]
                expected_ids: dict[str, UUID] = {}
                for resource, _, _, deleted_row, active_row in cases:
                    deleted_row.soft_delete()
                    session.add_all([deleted_row, active_row])
                    await session.flush()
                    expected_ids[resource] = active_row.id
                await session.commit()

            async with session_factory() as session:
                for resource, key_field, key_value, _, _ in cases:
                    resolved = await data_ops.resolve_upsert_row_id(
                        session,
                        resource=resource,
                        row={key_field: key_value},
                        key_field=key_field,
                        index=1,
                    )

                    assert UUID(resolved["id"]) == expected_ids[resource]

    asyncio.run(scenario())


def test_resolve_upsert_row_id_generates_id_when_no_match_exists() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                resolved = await data_ops.resolve_upsert_row_id(
                    session,
                    resource="area",
                    row={"name": "Fitness"},
                    key_field="name",
                    index=1,
                )

                assert UUID(resolved["id"])
                assert resolved["name"] == "Fitness"

    asyncio.run(scenario())


def test_resolve_upsert_row_id_rejects_ambiguous_natural_key() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                session.add(Vision(name="Launch"))
                session.add(Vision(name="Launch"))
                await session.commit()

            async with session_factory() as session:
                with pytest.raises(
                    data_ops.DataOperationError,
                    match="upsert key `name` is ambiguous",
                ):
                    await data_ops.resolve_upsert_row_id(
                        session,
                        resource="vision",
                        row={"name": "Launch"},
                        key_field="name",
                        index=1,
                    )

    asyncio.run(scenario())


def test_resolve_upsert_row_id_rejects_missing_key_value() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                with pytest.raises(
                    data_ops.DataOperationError,
                    match="Row 1 is missing a value for upsert key `name`",
                ):
                    await data_ops.resolve_upsert_row_id(
                        session,
                        resource="area",
                        row={"name": None},
                        key_field="name",
                        index=1,
                    )

    asyncio.run(scenario())


def test_resolve_upsert_row_id_rejects_unsupported_key_before_session_use() -> None:
    with pytest.raises(data_ops.DataOperationError, match="supported keys: none"):
        asyncio.run(
            data_ops.resolve_upsert_row_id(
                cast(AsyncSession, None),
                resource="note",
                row={"content": "hello"},
                key_field="content",
                index=1,
            )
        )


def test_body_measurement_is_supported_with_measured_at_upsert_key() -> None:
    assert "body-measurement" in data_ops.SUPPORTED_DATA_RESOURCES
    data_ops.validate_upsert_key("body-measurement", "measured_at")
    with pytest.raises(
        data_ops.DataOperationError,
        match="Natural-key upsert is not supported for 'body-measurement'",
    ):
        data_ops.validate_upsert_key("body-measurement", "weight_kg")


def test_health_data_resources_are_supported_with_safe_upsert_keys() -> None:
    assert "menstrual" in data_ops.SUPPORTED_DATA_RESOURCES
    assert "menstrual-factor" in data_ops.SUPPORTED_DATA_RESOURCES
    assert "sleep" in data_ops.SUPPORTED_DATA_RESOURCES
    data_ops.validate_upsert_key("menstrual", "log_date")
    data_ops.validate_upsert_key("menstrual-factor", "name")
    with pytest.raises(
        data_ops.DataOperationError,
        match="supported keys: none",
    ):
        data_ops.validate_upsert_key("sleep", "start_at")


def test_body_measurement_snapshot_round_trip_and_datetime_upsert_key() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                active_id = uuid4()
                await data_ops.import_resource_snapshot(
                    session,
                    resource="body-measurement",
                    rows=[
                        {
                            "id": str(uuid4()),
                            "measured_at": "2026-08-19T08:00:00+00:00",
                            "weight_kg": 62.0,
                            "created_at": "2026-08-18T08:05:00Z",
                            "updated_at": "2026-08-18T08:05:00Z",
                            "deleted_at": "2026-08-18T09:00:00Z",
                        },
                        {
                            "id": str(active_id),
                            "measured_at": "2026-08-19T08:00:00+00:00",
                            "weight_kg": 63.55,
                            "body_fat_percentage": 22.5,
                            "notes": "morning",
                            "created_at": "2026-08-19T08:05:00Z",
                            "updated_at": "2026-08-19T08:05:00Z",
                            "deleted_at": None,
                        },
                    ],
                )
                await session.commit()

            async with session_factory() as session:
                rows = await data_ops.export_resource_snapshot(
                    session,
                    resource="body-measurement",
                )
                assert len(rows) == 1
                assert rows[0]["measured_at"] == "2026-08-19T08:00:00Z"
                assert rows[0]["weight_kg"] == 63.55
                assert rows[0]["body_fat_percentage"] == 22.5

                resolved = await data_ops.resolve_upsert_row_id(
                    session,
                    resource="body-measurement",
                    row={"measured_at": "2026-08-19T04:00:00-04:00", "weight_kg": 64.0},
                    key_field="measured_at",
                    index=1,
                )
                assert UUID(resolved["id"]) == UUID(rows[0]["id"])
                assert UUID(resolved["id"]) == active_id

    asyncio.run(scenario())


@pytest.mark.parametrize("value", ["not-a-number", "NaN", "Infinity"])
def test_body_measurement_snapshot_rejects_non_finite_decimal_values(value: str) -> None:
    with pytest.raises(data_ops.DataOperationError, match="weight_kg"):
        data_ops.prepare_snapshot_row(
            "body-measurement",
            1,
            {
                "id": str(uuid4()),
                "measured_at": "2026-08-19T08:00:00Z",
                "weight_kg": value,
            },
        )


def test_batch_update_body_measurement_maps_canonical_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(session: object, *, measurement_id: object, payload: object) -> None:
        captured["measurement_id"] = measurement_id
        captured["payload"] = payload

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "body-measurement", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="body-measurement",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "measured_at": "2026-08-19T08:00:00+00:00",
                    "weight_kg": 64.2,
                    "body_fat_percentage": None,
                    "notes": "updated",
                }
            ],
        )
    )

    assert report.updated_count == 1
    assert captured["measurement_id"] == UUID("11111111-1111-1111-1111-111111111111")
    payload = cast(data_ops.body_measurements.BodyMeasurementUpdate, captured["payload"])
    assert payload.measured_at == datetime(2026, 8, 19, 8, tzinfo=UTC)
    assert payload.weight == Decimal("64.2")
    assert payload.unit == "kg"
    assert "body_fat_percentage" in payload.clear_fields
    assert payload.notes == "updated"


def test_batch_delete_body_measurement_routes_to_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_delete(session: object, **kwargs: object) -> SimpleNamespace:
        assert kwargs["measurement_ids"] == [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        return SimpleNamespace(deleted_count=2, failed_ids=(), errors=())

    monkeypatch.setitem(data_ops.DELETE_OPERATIONS, "body-measurement", fake_delete)

    report = asyncio.run(
        data_ops.batch_delete_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="body-measurement",
            record_ids=[
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            ],
        )
    )

    assert report.deleted_count == 2
    assert report.failed_count == 0


def test_menstrual_day_snapshot_round_trip_with_factors_and_log_date_upsert_key() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await data_ops.import_resource_snapshot(
                    session,
                    resource="menstrual-factor",
                    rows=[
                        {
                            "id": str(uuid4()),
                            "name": "travel",
                            "created_at": "2026-08-19T00:00:00Z",
                            "updated_at": "2026-08-19T00:00:00Z",
                            "deleted_at": None,
                        }
                    ],
                )
                await data_ops.import_resource_snapshot(
                    session,
                    resource="menstrual",
                    rows=[
                        {
                            "id": str(uuid4()),
                            "log_date": "2026-08-19",
                            "in_period": True,
                            "flow_amount": "medium",
                            "symptoms": ["headache"],
                            "mood_changes": True,
                            "protection_used": None,
                            "spotting": False,
                            "notes": "evening",
                            "factor_names": ["travel"],
                            "created_at": "2026-08-19T00:00:00Z",
                            "updated_at": "2026-08-19T00:00:00Z",
                            "deleted_at": None,
                        }
                    ],
                )
                await session.commit()

            async with session_factory() as session:
                rows = await data_ops.export_resource_snapshot(
                    session,
                    resource="menstrual",
                )
                assert len(rows) == 1
                assert rows[0]["log_date"] == "2026-08-19"
                assert rows[0]["factor_names"] == ["travel"]
                assert rows[0]["symptoms"] == ["headache"]

                resolved = await data_ops.resolve_upsert_row_id(
                    session,
                    resource="menstrual",
                    row={"log_date": "2026-08-19", "notes": "updated"},
                    key_field="log_date",
                    index=1,
                )
                assert UUID(resolved["id"]) == UUID(rows[0]["id"])

    asyncio.run(scenario())


def test_sleep_segment_snapshot_round_trip() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await data_ops.import_resource_snapshot(
                    session,
                    resource="sleep",
                    rows=[
                        {
                            "id": str(uuid4()),
                            "sleep_date": "2026-08-18",
                            "start_at": "2026-08-18T22:30:00+00:00",
                            "end_at": "2026-08-19T06:30:00+00:00",
                            "duration_minutes": 480,
                            "created_at": "2026-08-19T00:00:00Z",
                            "updated_at": "2026-08-19T00:00:00Z",
                            "deleted_at": None,
                        }
                    ],
                )
                await session.commit()

            async with session_factory() as session:
                rows = await data_ops.export_resource_snapshot(
                    session,
                    resource="sleep",
                )
                assert len(rows) == 1
                assert rows[0]["start_at"] == "2026-08-18T22:30:00Z"
                assert rows[0]["duration_minutes"] == 480

    asyncio.run(scenario())


def test_batch_update_menstrual_day_maps_canonical_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(session: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "menstrual", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="menstrual",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "log_date": "2026-08-19",
                    "flow_amount": "medium",
                    "symptoms": None,
                    "factor_names": ["travel"],
                }
            ],
        )
    )

    assert report.updated_count == 1
    assert captured["day_id"] == UUID("11111111-1111-1111-1111-111111111111")
    assert captured["log_date"] == date(2026, 8, 19)
    assert captured["flow_amount"] == "medium"
    assert captured["clear_symptoms"] is True
    assert captured["factor_names"] == ["travel"]


def test_batch_update_menstrual_factor_maps_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(session: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "menstrual-factor", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="menstrual-factor",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "name": "exercise",
                }
            ],
        )
    )

    assert report.updated_count == 1
    assert captured == {
        "factor_id": UUID("11111111-1111-1111-1111-111111111111"),
        "name": "exercise",
    }


def test_batch_update_records_integrity_error_as_row_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_update(session: object, **kwargs: object) -> None:
        raise IntegrityError("stmt", {}, Exception("unique conflict"))

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "body-measurement", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="body-measurement",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "measured_at": "2026-08-19T08:00:00Z",
                }
            ],
        )
    )

    assert report.updated_count == 0
    assert report.failed_count == 1
    assert "unique conflict" in report.failures[0].message


def test_batch_update_sleep_segment_maps_canonical_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_update(session: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setitem(data_ops.UPDATE_OPERATIONS, "sleep", fake_update)

    report = asyncio.run(
        data_ops.batch_update_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource="sleep",
            rows=[
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "start_at": "2026-08-18T22:30:00+00:00",
                    "end_at": "2026-08-19T06:30:00+00:00",
                }
            ],
        )
    )

    assert report.updated_count == 1
    assert captured["segment_id"] == UUID("11111111-1111-1111-1111-111111111111")
    assert captured["start_at"] == datetime(2026, 8, 18, 22, 30, tzinfo=UTC)
    assert captured["end_at"] == datetime(2026, 8, 19, 6, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("resource", "arg_name"),
    [
        ("menstrual", "day_ids"),
        ("menstrual-factor", "factor_ids"),
        ("sleep", "segment_ids"),
    ],
)
def test_batch_delete_health_resources_routes_to_service(
    monkeypatch: pytest.MonkeyPatch,
    resource: str,
    arg_name: str,
) -> None:
    async def fake_delete(session: object, **kwargs: object) -> SimpleNamespace:
        assert kwargs[arg_name] == [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        return SimpleNamespace(deleted_count=2, failed_ids=(), errors=())

    monkeypatch.setitem(data_ops.DELETE_OPERATIONS, resource, fake_delete)

    report = asyncio.run(
        data_ops.batch_delete_resource(
            cast(AsyncSession, FakeBatchSession()),
            resource=resource,
            record_ids=[
                UUID("11111111-1111-1111-1111-111111111111"),
                UUID("22222222-2222-2222-2222-222222222222"),
            ],
        )
    )

    assert report.deleted_count == 2
    assert report.failed_count == 0
