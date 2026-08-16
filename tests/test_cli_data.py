from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import data_ops
from tests.support import make_session_scope


class FakeAsyncSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        return None

    @asynccontextmanager
    async def begin_nested(self):
        yield self


def _make_session_factory_getter(session: FakeAsyncSession):
    def _get_factory():
        def _factory() -> FakeAsyncSession:
            return session

        return _factory

    return _get_factory


def test_main_data_export_prints_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_export_resource_snapshot(
        _session: object,
        *,
        resource: str,
    ) -> list[dict[str, object]]:
        assert resource == "note"
        return [{"id": "11111111-1111-1111-1111-111111111111", "content": "hello"}]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(data_ops, "export_resource_snapshot", fake_export_resource_snapshot)

    exit_code = cli.main(["data", "export", "note", "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"id": "11111111-1111-1111-1111-111111111111"' in captured.out
    assert '"content": "hello"' in captured.out


def test_main_data_export_all_uses_bundle_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = tmp_path / "lifeos-bundle.zip"

    async def fake_export_bundle(
        _session: object,
        *,
        output_path: Path,
    ) -> data_ops.BundleExportReport:
        assert output_path == bundle_path
        return data_ops.BundleExportReport(
            resource_counts={"note": 2, "timelog": 1},
            output_path=output_path,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(data_ops, "export_bundle", fake_export_bundle)

    exit_code = cli.main(["data", "export", "all", "--output", str(bundle_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"Exported bundle to {bundle_path}" in captured.out
    assert "note: 2" in captured.out
    assert "timelog: 1" in captured.out


def test_main_data_import_bundle_uses_atomic_restore(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeAsyncSession()

    def fake_read_bundle(path: Path) -> data_ops.BundlePayload:
        assert path == Path("backup.zip")
        return data_ops.BundlePayload(
            manifest={"schema_version": 3},
            resources={"note": [{"id": "11111111-1111-1111-1111-111111111111"}]},
        )

    async def fake_import_bundle(
        session_obj: object,
        *,
        bundle_rows: dict[str, list[dict[str, object]]],
        replace_existing: bool,
    ) -> data_ops.BundleImportReport:
        assert session_obj is session
        assert replace_existing is True
        assert bundle_rows["note"][0]["id"] == "11111111-1111-1111-1111-111111111111"
        return data_ops.BundleImportReport(
            processed_count=1,
            created_count=1,
            updated_count=0,
            failed_count=0,
            failures=(),
            imported_resources=("note",),
        )

    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        _make_session_factory_getter(session),
    )
    monkeypatch.setattr(data_ops, "read_bundle", fake_read_bundle)
    monkeypatch.setattr(data_ops, "import_bundle", fake_import_bundle)

    exit_code = cli.main(
        [
            "data",
            "import",
            "bundle",
            "--file",
            "backup.zip",
            "--replace-existing",
            "--dry-run",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert session.rolled_back is True
    assert session.committed is False
    assert "Bundle resources: note" in captured.out
    assert "Dry run: bundle changes were rolled back." in captured.out


def test_main_data_batch_delete_reads_ids_from_jsonl_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeAsyncSession()
    ids_path = tmp_path / "event-ids.jsonl"
    ids_path.write_text('{"id":"11111111-1111-1111-1111-111111111111"}\n', encoding="utf-8")
    captured_ids: list[object] = []

    async def fake_batch_delete_resource(
        session_obj: object,
        *,
        resource: str,
        record_ids: list[object],
    ) -> data_ops.DataBatchDeleteReport:
        assert session_obj is session
        assert resource == "event"
        captured_ids.extend(record_ids)
        return data_ops.DataBatchDeleteReport(
            resource=resource,
            processed_count=len(record_ids),
            deleted_count=len(record_ids),
            failed_count=0,
            failures=(),
        )

    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        _make_session_factory_getter(session),
    )
    monkeypatch.setattr(data_ops, "batch_delete_resource", fake_batch_delete_resource)

    exit_code = cli.main(
        [
            "data",
            "batch-delete",
            "event",
            "--file",
            str(ids_path),
            "--format",
            "jsonl",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_ids == [UUID("11111111-1111-1111-1111-111111111111")]
    assert "Deleted rows: 1" in captured.out


def test_main_data_import_bundle_reports_invalid_zip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    broken_bundle = tmp_path / "broken.zip"
    broken_bundle.write_text("not a zip archive", encoding="utf-8")

    exit_code = cli.main(["data", "import", "bundle", "--file", str(broken_bundle)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Unable to read bundle archive" in captured.err


def test_main_data_import_records_lookup_failures_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeAsyncSession()
    input_path = tmp_path / "timelog.jsonl"
    input_path.write_text(
        '{"id":"11111111-1111-1111-1111-111111111111","title":"demo"}\n',
        encoding="utf-8",
    )

    async def fake_import_resource_snapshot(
        _session_obj: object,
        *,
        resource: str,
        rows: list[dict[str, object]],
    ) -> data_ops.DataImportReport:
        _ = (resource, rows)
        raise LookupError("Unknown person IDs for entity type timelog: missing-person")

    async def fake_run_post_import_hooks(_session_obj: object, *, resources: set[str]) -> None:
        _ = resources
        raise AssertionError("post-import hooks should not run after a stopping failure")

    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        _make_session_factory_getter(session),
    )
    monkeypatch.setattr(data_ops, "import_resource_snapshot", fake_import_resource_snapshot)
    monkeypatch.setattr(data_ops, "run_post_import_hooks", fake_run_post_import_hooks)

    exit_code = cli.main(
        [
            "data",
            "import",
            "timelog",
            "--file",
            str(input_path),
            "--format",
            "jsonl",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Resource: timelog" in captured.out
    assert "Failed rows: 1" in captured.out
    assert session.rolled_back is True


def test_main_data_import_upsert_requires_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "data",
            "import",
            "area",
            "--file",
            "areas.jsonl",
            "--mode",
            "upsert",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--mode upsert requires --key <field>." in captured.err


def test_main_data_import_rejects_key_without_upsert_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "data",
            "import",
            "area",
            "--file",
            "areas.jsonl",
            "--key",
            "name",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--key is only supported with --mode upsert." in captured.err


def test_main_data_import_bundle_rejects_mode_and_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "data",
            "import",
            "bundle",
            "--file",
            "lifeos-bundle.zip",
            "--mode",
            "upsert",
            "--key",
            "name",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--mode and --key apply to single-resource imports only." in captured.err


def test_main_data_import_upsert_resolves_natural_key_before_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeAsyncSession()
    input_path = tmp_path / "areas.jsonl"
    input_path.write_text('{"name":"Health"}\n', encoding="utf-8")

    resolved_rows: list[dict[str, object]] = []

    async def fake_resolve_upsert_row_id(
        _session_obj: object,
        *,
        resource: str,
        row: dict[str, object],
        key_field: str,
        index: int,
    ) -> dict[str, object]:
        assert resource == "area"
        assert key_field == "name"
        assert index == 1
        return {**row, "id": "11111111-1111-1111-1111-111111111111"}

    async def fake_import_resource_snapshot(
        _session_obj: object,
        *,
        resource: str,
        rows: list[dict[str, object]],
    ) -> data_ops.DataImportReport:
        resolved_rows.extend(rows)
        return data_ops.DataImportReport(
            resource=resource,
            processed_count=len(rows),
            created_count=1,
            updated_count=0,
            failed_count=0,
            failures=(),
        )

    async def fake_run_post_import_hooks(_session_obj: object, *, resources: set[str]) -> None:
        _ = resources

    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        _make_session_factory_getter(session),
    )
    monkeypatch.setattr(data_ops, "resolve_upsert_row_id", fake_resolve_upsert_row_id)
    monkeypatch.setattr(data_ops, "import_resource_snapshot", fake_import_resource_snapshot)
    monkeypatch.setattr(data_ops, "run_post_import_hooks", fake_run_post_import_hooks)

    exit_code = cli.main(
        [
            "data",
            "import",
            "area",
            "--file",
            str(input_path),
            "--format",
            "jsonl",
            "--mode",
            "upsert",
            "--key",
            "name",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Created rows: 1" in captured.out
    assert resolved_rows == [{"name": "Health", "id": "11111111-1111-1111-1111-111111111111"}]
    assert session.committed is True


def test_main_data_batch_update_records_lookup_failures_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeAsyncSession()
    patch_path = tmp_path / "person-patch.jsonl"
    patch_path.write_text(
        '{"id":"11111111-1111-1111-1111-111111111111","tag_ids":["22222222-2222-2222-2222-222222222222"]}\n',
        encoding="utf-8",
    )

    async def fake_batch_update_resource(
        _session_obj: object,
        *,
        resource: str,
        rows: list[dict[str, object]],
        continue_on_error: bool = False,
    ) -> data_ops.DataBatchUpdateReport:
        assert continue_on_error is False
        return data_ops.DataBatchUpdateReport(
            resource=resource,
            processed_count=len(rows),
            updated_count=0,
            failed_count=1,
            failures=(
                data_ops.DataOperationFailure(
                    index=1,
                    resource=resource,
                    message="Unknown tag IDs for entity type person: missing-tag",
                    payload=rows[0],
                    record_id=UUID("11111111-1111-1111-1111-111111111111"),
                ),
            ),
        )

    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        _make_session_factory_getter(session),
    )
    monkeypatch.setattr(data_ops, "batch_update_resource", fake_batch_update_resource)

    exit_code = cli.main(
        [
            "data",
            "batch-update",
            "person",
            "--file",
            str(patch_path),
            "--format",
            "jsonl",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Resource: person" in captured.out
    assert "Failed rows: 1" in captured.out
    assert session.rolled_back is True


def test_main_data_batch_delete_reads_ids_from_json_array(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeAsyncSession()
    ids_path = tmp_path / "event-ids.json"
    ids_path.write_text(
        ('["11111111-1111-1111-1111-111111111111", {"id":"22222222-2222-2222-2222-222222222222"}]'),
        encoding="utf-8",
    )
    captured_ids: list[object] = []

    async def fake_batch_delete_resource(
        session_obj: object,
        *,
        resource: str,
        record_ids: list[object],
    ) -> data_ops.DataBatchDeleteReport:
        assert session_obj is session
        assert resource == "event"
        captured_ids.extend(record_ids)
        return data_ops.DataBatchDeleteReport(
            resource=resource,
            processed_count=len(record_ids),
            deleted_count=len(record_ids),
            failed_count=0,
            failures=(),
        )

    monkeypatch.setattr(
        db_session,
        "get_async_session_factory",
        _make_session_factory_getter(session),
    )
    monkeypatch.setattr(data_ops, "batch_delete_resource", fake_batch_delete_resource)

    exit_code = cli.main(
        [
            "data",
            "batch-delete",
            "event",
            "--file",
            str(ids_path),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_ids == [
        UUID("11111111-1111-1111-1111-111111111111"),
        UUID("22222222-2222-2222-2222-222222222222"),
    ]
    assert "Deleted rows: 2" in captured.out


def test_main_data_batch_delete_rejects_invalid_json_item(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ids_path = tmp_path / "invalid-event-ids.json"
    ids_path.write_text('[{"name":"missing-id"}]\n', encoding="utf-8")

    exit_code = cli.main(
        [
            "data",
            "batch-delete",
            "event",
            "--file",
            str(ids_path),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Batch-delete JSON input must contain UUID strings or objects with `id`." in captured.err
