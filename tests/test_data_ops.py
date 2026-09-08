from __future__ import annotations

import asyncio
import hashlib
import json
import stat
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
from lifeos_cli.db.base import Base
from lifeos_cli.db.models.aggregated_timelog_stats_groupby_area import (
    AggregatedTimelogStatsGroupByArea,
)
from lifeos_cli.db.models.area import Area
from lifeos_cli.db.models.body_measurement import BodyMeasurement
from lifeos_cli.db.models.daily_timelog_stats_groupby_area import DailyTimelogStatsGroupByArea
from lifeos_cli.db.models.finance import FinanceTree
from lifeos_cli.db.models.habit import Habit
from lifeos_cli.db.models.menstrual import MenstrualDay, MenstrualFactor
from lifeos_cli.db.models.note import Note
from lifeos_cli.db.models.person import Person
from lifeos_cli.db.models.timelog_template import TimelogTemplate
from lifeos_cli.db.models.vision import Vision
from lifeos_cli.db.services import data_ops
from lifeos_cli.db.services.bundle_codec import BundleCodecError, open_bundle_atomic
from lifeos_cli.db.services.bundle_tables import (
    BUNDLE_V4_TABLE_SPECS,
    DERIVED_TABLE_NAMES,
    BundleTableError,
    validate_domain_row,
)
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


class FakePostgresConnection:
    def __init__(self, isolation_level: str) -> None:
        self.isolation_level = isolation_level

    async def get_isolation_level(self) -> str:
        return self.isolation_level


class FakePostgresSession:
    def __init__(self, *, in_transaction: bool, isolation_level: str = "READ COMMITTED") -> None:
        self._in_transaction = in_transaction
        self.connection_options: dict[str, str] | None = None
        self._connection = FakePostgresConnection(isolation_level)

    def get_bind(self) -> object:
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def in_transaction(self) -> bool:
        return self._in_transaction

    async def connection(
        self,
        *,
        execution_options: dict[str, str] | None = None,
    ) -> FakePostgresConnection:
        self.connection_options = execution_options
        return self._connection


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


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "duration_days": -5,
            },
            "duration_days must be between 1 and 10000",
        ),
        (
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "status": "not-a-status",
            },
            "status must be one of",
        ),
        (
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "target_per_cycle": -2,
            },
            "target_per_cycle must be greater than zero",
        ),
    ],
)
def test_habit_snapshot_import_rejects_domain_invalid_rows(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(data_ops.DataOperationError, match=message):
        data_ops.prepare_snapshot_row("habit", 1, payload)


def test_snapshot_parser_does_not_coerce_string_booleans() -> None:
    with pytest.raises(data_ops.DataOperationError, match="must be a boolean"):
        data_ops.prepare_snapshot_row(
            "area",
            1,
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "is_active": "false",
            },
        )


def test_snapshot_parser_rejects_unknown_fields() -> None:
    with pytest.raises(data_ops.DataOperationError, match="unknown fields: typo_field"):
        data_ops.prepare_snapshot_row(
            "note",
            1,
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "typo_field": "silently ignored before strict validation",
            },
        )


def test_snapshot_parser_rejects_postgresql_unsupported_null_characters() -> None:
    with pytest.raises(data_ops.DataOperationError, match="unsupported by PostgreSQL"):
        data_ops.prepare_snapshot_row(
            "note",
            1,
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "content": "invalid\x00content",
            },
        )


def test_snapshot_parser_rejects_non_string_factor_names() -> None:
    with pytest.raises(data_ops.DataOperationError, match="factor_names.*must be a string"):
        data_ops.prepare_snapshot_row(
            "menstrual",
            1,
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "factor_names": [123],
            },
        )


def test_snapshot_parser_rejects_invalid_event_occurrence_action() -> None:
    with pytest.raises(data_ops.DataOperationError, match="action must be `skip`"):
        data_ops.prepare_snapshot_row(
            "event",
            1,
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "occurrence_exceptions": [
                    {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "action": "delete",
                        "instance_start": "2026-09-08T09:00:00Z",
                        "created_at": "2026-09-08T08:00:00Z",
                        "updated_at": "2026-09-08T08:00:00Z",
                        "deleted_at": None,
                    }
                ],
            },
        )


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

    monkeypatch.setattr(data_ops, "_apply_snapshot_base_row", fake_apply)
    monkeypatch.setattr(data_ops, "_sync_snapshot_relations", fake_sync)
    monkeypatch.setattr(data_ops, "run_post_import_hooks", fake_hooks)

    report = asyncio.run(
        data_ops.import_bundle(
            cast(AsyncSession, object()),
            bundle=data_ops.BundlePayload(
                manifest={"schema_version": data_ops.LEGACY_BUNDLE_SCHEMA_VERSION},
                resources={
                    "person": [{"id": "11111111-1111-1111-1111-111111111111"}],
                    "tag": [{"id": "22222222-2222-2222-2222-222222222222"}],
                },
            ),
        )
    )

    base_positions = [index for index, call in enumerate(call_order) if call[0] == "base"]
    sync_positions = [index for index, call in enumerate(call_order) if call[0] == "sync"]

    assert report.created_count == 2
    assert report.updated_count == 0
    assert report.imported_resources == ("person", "tag")
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


def test_atomic_bundle_writer_removes_partial_output_on_failure(tmp_path: Path) -> None:
    bundle_path = tmp_path / "partial.zip"

    with pytest.raises(RuntimeError, match="interrupted"):
        with open_bundle_atomic(bundle_path) as writer:
            writer.write_entry("resources/note.jsonl", b"{}\n")
            raise RuntimeError("interrupted")

    assert not bundle_path.exists()
    assert not list(tmp_path.glob(".partial.zip.*.tmp"))


def test_atomic_bundle_writer_requires_manifest(tmp_path: Path) -> None:
    bundle_path = tmp_path / "missing-manifest.zip"

    with pytest.raises(BundleCodecError, match="missing its manifest"):
        with open_bundle_atomic(bundle_path) as writer:
            writer.write_entry("resources/note.jsonl", b"{}\n")

    assert not bundle_path.exists()


def test_bundle_export_includes_manifest_in_reader_size_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        bundle_path = tmp_path / "oversized.zip"
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                monkeypatch.setattr(data_ops, "MAX_BUNDLE_TOTAL_BYTES", 1)
                with pytest.raises(data_ops.DataOperationError, match="supported expanded size"):
                    await data_ops.export_bundle(session, output_path=bundle_path)
        assert not bundle_path.exists()

    asyncio.run(scenario())


def test_bundle_export_closes_row_stream_when_size_limit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_closed = False

    async def oversized_rows(_session: object, _table: object):
        nonlocal stream_closed
        try:
            yield {"oversized": "row"}
        finally:
            stream_closed = True

    async def scenario() -> None:
        bundle_path = tmp_path / "oversized-row.zip"
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                monkeypatch.setattr(data_ops, "MAX_BUNDLE_TOTAL_BYTES", 1)
                monkeypatch.setattr(data_ops, "iter_export_table_rows", oversized_rows)
                with pytest.raises(data_ops.DataOperationError, match="supported expanded size"):
                    await data_ops.export_bundle(session, output_path=bundle_path)
        assert not bundle_path.exists()

    asyncio.run(scenario())
    assert stream_closed


def test_postgres_bundle_export_starts_repeatable_read_snapshot() -> None:
    session = FakePostgresSession(in_transaction=False)

    asyncio.run(data_ops._start_bundle_export_snapshot(cast(AsyncSession, session)))

    assert session.connection_options == {"isolation_level": "REPEATABLE READ"}


def test_postgres_bundle_export_rejects_read_committed_transaction() -> None:
    session = FakePostgresSession(in_transaction=True)

    with pytest.raises(data_ops.DataOperationError, match="requires a fresh session"):
        asyncio.run(data_ops._start_bundle_export_snapshot(cast(AsyncSession, session)))


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


@pytest.mark.parametrize("schema_version", [4.0, True, "4", None])
def test_read_bundle_requires_integer_schema_version(
    tmp_path: Path,
    schema_version: object,
) -> None:
    bundle_path = tmp_path / "invalid-version.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps({"schema_version": schema_version}))

    with pytest.raises(data_ops.DataOperationError, match="schema_version must be an integer"):
        data_ops.read_bundle(bundle_path)


def test_read_bundle_rejects_nonfinite_json_numbers(tmp_path: Path) -> None:
    bundle_path = tmp_path / "nonfinite-json.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", '{"schema_version": NaN}')

    with pytest.raises(data_ops.DataOperationError, match="non-finite number"):
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


def test_bundle_rejects_a_missing_v4_entry(tmp_path: Path) -> None:
    bundle_path = tmp_path / "incomplete.zip"
    with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"schema_version": data_ops.BUNDLE_SCHEMA_VERSION, "entries": {}}),
        )

    with pytest.raises(data_ops.DataOperationError, match="entry set is incomplete"):
        data_ops.read_bundle(bundle_path)


def test_bundle_rejects_tampered_v4_content(tmp_path: Path) -> None:
    async def scenario() -> None:
        source_path = tmp_path / "source.zip"
        tampered_path = tmp_path / "tampered.zip"
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                session.add(Note(content="original"))
                await session.flush()
                await data_ops.export_bundle(session, output_path=source_path)
        with ZipFile(source_path, "r") as source:
            contents = {name: source.read(name) for name in source.namelist()}
        contents["tables/notes.jsonl"] = contents["tables/notes.jsonl"].replace(
            b'"original"',
            b'"tampered"',
        )
        with ZipFile(tampered_path, "w", compression=ZIP_DEFLATED) as target:
            for name, content in contents.items():
                target.writestr(name, content)

        with pytest.raises(data_ops.DataOperationError, match="Checksum mismatch"):
            data_ops.read_bundle(tampered_path)

    asyncio.run(scenario())


def test_bundle_rejects_boolean_manifest_entry_row_count(tmp_path: Path) -> None:
    async def scenario() -> None:
        source_path = tmp_path / "source.zip"
        malformed_path = tmp_path / "boolean-count.zip"
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                await data_ops.export_bundle(session, output_path=source_path)
        with ZipFile(source_path, "r") as source:
            contents = {name: source.read(name) for name in source.namelist()}
        manifest = json.loads(contents["manifest.json"])
        manifest["entries"]["tables/notes.jsonl"]["row_count"] = False
        contents["manifest.json"] = json.dumps(manifest).encode("utf-8")
        with ZipFile(malformed_path, "w", compression=ZIP_DEFLATED) as target:
            for name, content in contents.items():
                target.writestr(name, content)

        with pytest.raises(data_ops.DataOperationError, match="row count metadata"):
            data_ops.read_bundle(malformed_path)

    asyncio.run(scenario())


def test_bundle_export_rejects_postgresql_unsupported_null_characters(tmp_path: Path) -> None:
    async def scenario() -> None:
        bundle_path = tmp_path / "null-character.zip"
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                session.add(Note(content="invalid\x00content"))
                await session.flush()
                with pytest.raises(data_ops.DataOperationError, match="unsupported by PostgreSQL"):
                    await data_ops.export_bundle(session, output_path=bundle_path)
        assert not bundle_path.exists()

    asyncio.run(scenario())


def test_bundle_export_rejects_nonportable_integer_and_json_values(tmp_path: Path) -> None:
    async def scenario() -> None:
        for name, tree in (
            ("integer", FinanceTree(name="Integer", display_order=2**31)),
            ("json", FinanceTree(name="JSON", metadata_json={"nested": "invalid\x00value"})),
        ):
            bundle_path = tmp_path / f"{name}.zip"
            async with sqlite_session_factory() as session_factory:
                async with session_factory() as session:
                    session.add(tree)
                    await session.flush()
                    with pytest.raises(data_ops.DataOperationError):
                        await data_ops.export_bundle(session, output_path=bundle_path)
            assert not bundle_path.exists()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("table_name", "row", "message"),
    [
        (
            "associations",
            {
                "source_model": "event",
                "target_model": "tag",
                "link_type": "is_about",
            },
            "target_model",
        ),
        (
            "associations",
            {
                "source_model": "event",
                "target_model": "person",
                "link_type": "invalid",
            },
            "link_type",
        ),
        ("tag_associations", {"entity_type": "habit_action"}, "entity_type"),
        ("tasks", {"actual_effort_self": -1}, "actual_effort_self"),
        ("finance_tree_nodes", {"children_count": -1}, "children_count"),
    ],
)
def test_bundle_domain_validation_covers_database_invariants_before_restore(
    table_name: str,
    row: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(BundleTableError, match=message):
        validate_domain_row(table_name, row, row_number=1)


def test_legacy_bundle_cannot_replace_the_database() -> None:
    with pytest.raises(data_ops.DataOperationError, match="partial exports"):
        asyncio.run(
            data_ops.import_bundle(
                cast(AsyncSession, object()),
                bundle=data_ops.BundlePayload(
                    manifest={"schema_version": data_ops.LEGACY_BUNDLE_SCHEMA_VERSION},
                    resources={},
                ),
                replace_existing=True,
            )
        )


@pytest.mark.parametrize(
    "payload",
    [
        data_ops.BundlePayload(
            manifest={"schema_version": data_ops.BUNDLE_SCHEMA_VERSION},
            resources={},
        ),
        data_ops.BundlePayload(
            manifest={"schema_version": data_ops.BUNDLE_SCHEMA_VERSION},
            resources={"note": []},
            tables=data_ops.PreparedBundleTables(rows={}),
        ),
        data_ops.BundlePayload(
            manifest={"schema_version": data_ops.LEGACY_BUNDLE_SCHEMA_VERSION},
            resources={},
            tables=data_ops.PreparedBundleTables(rows={}),
        ),
    ],
)
def test_import_bundle_rejects_inconsistent_payload_contract(
    payload: data_ops.BundlePayload,
) -> None:
    with pytest.raises(data_ops.DataOperationError, match="bundle schema|Schema-v4"):
        asyncio.run(
            data_ops.import_bundle(
                cast(AsyncSession, object()),
                bundle=payload,
            )
        )


def test_lossless_bundle_replace_preserves_unexposed_and_soft_deleted_rows(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        finance_tree_id = uuid4()
        template_id = uuid4()
        deleted_note_id = uuid4()
        bundle_path = tmp_path / "lossless.zip"
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                session.add_all(
                    [
                        FinanceTree(
                            id=finance_tree_id,
                            name="Private balance sheet",
                            primary_currency="USD",
                            display_order=0,
                            is_default=True,
                        ),
                        TimelogTemplate(
                            id=template_id,
                            title="Deep work",
                            title_normalized="deep work",
                            position=0,
                            usage_count=7,
                        ),
                        Note(
                            id=deleted_note_id,
                            content="soft-deleted history",
                            deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
                        ),
                    ]
                )
                await session.flush()
                await data_ops.export_bundle(session, output_path=bundle_path)

                with ZipFile(bundle_path) as archive:
                    assert all(
                        name == "manifest.json" or name.startswith("tables/")
                        for name in archive.namelist()
                    )

                payload = data_ops.read_bundle(bundle_path)
                report = await data_ops.import_bundle(
                    session,
                    bundle=payload,
                    replace_existing=True,
                )
                await session.flush()
                session.expunge_all()

                assert report.failed_count == 0
                assert await session.get(FinanceTree, finance_tree_id) is not None
                restored_template = await session.get(TimelogTemplate, template_id)
                assert restored_template is not None
                assert restored_template.usage_count == 7
                restored_note = (
                    await session.execute(select(Note).execution_options(include_soft_deleted=True))
                ).scalar_one()
                assert restored_note.id == deleted_note_id
                assert restored_note.deleted_at is not None

        assert stat.S_IMODE(bundle_path.stat().st_mode) == 0o600

    asyncio.run(scenario())


def test_bundle_v4_contract_matches_current_authoritative_schema() -> None:
    """Force a bundle version decision whenever an authoritative table shape changes."""
    actual_tables = tuple(
        table for table in Base.metadata.sorted_tables if table.name not in DERIVED_TABLE_NAMES
    )

    assert tuple(spec.name for spec in BUNDLE_V4_TABLE_SPECS) == tuple(
        table.name for table in actual_tables
    )
    assert {spec.name: spec.columns for spec in BUNDLE_V4_TABLE_SPECS} == {
        table.name: tuple(column.name for column in table.columns) for table in actual_tables
    }
    schema_shape = []
    for spec in BUNDLE_V4_TABLE_SPECS:
        table = Base.metadata.tables[spec.name]
        columns = []
        for column_name in spec.columns:
            column = table.c[column_name]
            column_type = column.type
            columns.append(
                {
                    "name": column_name,
                    "type": f"{type(column_type).__module__}.{type(column_type).__qualname__}",
                    "length": getattr(column_type, "length", None),
                    "precision": getattr(column_type, "precision", None),
                    "scale": getattr(column_type, "scale", None),
                    "timezone": getattr(column_type, "timezone", None),
                    "none_as_null": getattr(column_type, "none_as_null", None),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "foreign_keys": sorted(
                        f"{foreign_key.column.table.name}.{foreign_key.column.name}"
                        for foreign_key in column.foreign_keys
                    ),
                }
            )
        schema_shape.append({"table": spec.name, "columns": columns})
    fingerprint = hashlib.sha256(
        json.dumps(schema_shape, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    expected_fingerprint = (
        "d6edbf508005a514d13b48f3d99e3367"  # pragma: allowlist secret
        "8058c46cf5e9495f8a1660b2ee923b0b"  # pragma: allowlist secret
    )
    assert fingerprint == expected_fingerprint


def test_timelog_import_hook_removes_stale_derived_rows_without_source_timelogs() -> None:
    async def scenario() -> None:
        async with sqlite_session_factory() as session_factory:
            async with session_factory() as session:
                area = Area(name="Work")
                session.add(area)
                await session.flush()
                session.add_all(
                    [
                        DailyTimelogStatsGroupByArea(
                            stat_date=date(2026, 9, 1),
                            timezone="UTC",
                            area_id=area.id,
                            minutes=60,
                            timelog_count=1,
                        ),
                        AggregatedTimelogStatsGroupByArea(
                            granularity="month",
                            period_start=date(2026, 9, 1),
                            period_end=date(2026, 9, 30),
                            timezone="UTC",
                            area_id=area.id,
                            minutes=60,
                            timelog_count=1,
                        ),
                    ]
                )
                await session.flush()

                await data_ops.run_post_import_hooks(session, resources={"timelog"})

                daily_rows = await session.execute(select(DailyTimelogStatsGroupByArea))
                assert not list(daily_rows.scalars())
                assert not list(
                    (await session.execute(select(AggregatedTimelogStatsGroupByArea))).scalars()
                )

    asyncio.run(scenario())


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
