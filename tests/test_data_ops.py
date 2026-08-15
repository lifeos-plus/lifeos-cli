from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import Column, select
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.db.backend_policy import backend_policy_for_drivername
from lifeos_cli.db.models.area import Area
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
                "people": [{"id": "11111111-1111-1111-1111-111111111111"}],
                "tag": [{"id": "22222222-2222-2222-2222-222222222222"}],
            },
            replace_existing=True,
        )
    )

    base_positions = [index for index, call in enumerate(call_order) if call[0] == "base"]
    sync_positions = [index for index, call in enumerate(call_order) if call[0] == "sync"]

    assert report.created_count == 2
    assert report.updated_count == 0
    assert report.imported_resources == ("people", "tag")
    assert call_order[0] == ("truncate", "-")
    assert max(base_positions) < min(sync_positions)
    assert call_order[-1] == ("hooks", "people,tag")


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
