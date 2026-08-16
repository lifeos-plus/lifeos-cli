from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.exc import OperationalError

from lifeos_cli import cli
from lifeos_cli.cli_support.resources.note import handlers as note_handlers
from lifeos_cli.config import clear_config_cache
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import notes as note_services
from lifeos_cli.db.services.batching import BatchDeleteResult
from lifeos_cli.db.services.notes import (
    NoteBatchUpdateResult,
    NoteNotFoundError,
)
from tests.config_support import install_test_config
from tests.support import make_record, make_session_scope, utc_datetime


@pytest.fixture(autouse=True)
def _use_stable_note_timezone(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_TIMEZONE", "UTC")
    yield
    clear_config_cache()


def test_main_note_add_creates_note(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    created: dict[str, str] = {}

    async def fake_create_note(session: object, *, content: str) -> object:
        created["content"] = content
        return make_record(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            content=content,
            created_at=utc_datetime(2026, 4, 9),
            deleted_at=None,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "create_note", fake_create_note)

    exit_code = cli.main(["note", "add", "a new note"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert created["content"] == "a new note"
    assert "Created note 11111111-1111-1111-1111-111111111111" in captured.out


def test_main_note_add_reads_multiline_content_from_stdin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    created: dict[str, str] = {}

    async def fake_create_note(session: object, *, content: str) -> object:
        created["content"] = content
        return make_record(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            content=content,
            created_at=utc_datetime(2026, 4, 9),
            deleted_at=None,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "create_note", fake_create_note)
    monkeypatch.setattr(note_handlers.sys, "stdin", io.StringIO("line one\nline two\n"))

    exit_code = cli.main(["note", "add", "--stdin"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert created["content"] == "line one\nline two"
    assert "Created note aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in captured.out


def test_main_note_add_reads_content_from_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    created: dict[str, str] = {}
    content_file = tmp_path / "note.md"
    content_file.write_text("first line\nsecond line\n", encoding="utf-8")

    async def fake_create_note(session: object, *, content: str) -> object:
        created["content"] = content
        return make_record(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            content=content,
            created_at=utc_datetime(2026, 4, 9),
            deleted_at=None,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "create_note", fake_create_note)

    exit_code = cli.main(["note", "add", "--file", str(content_file)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert created["content"] == "first line\nsecond line"
    assert "Created note bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" in captured.out


def test_main_note_add_requires_exactly_one_content_source(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(Path("/tmp") / "missing-config.toml"))

    exit_code = cli.main(["note", "add", "inline text", "--stdin"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "exactly one source" in captured.err


def test_main_note_show_prints_multiline_content(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_note(
        session: object,
        *,
        note_id: UUID,
    ) -> object:
        return make_record(
            id=note_id,
            content="first line\nsecond line",
            created_at=utc_datetime(2026, 4, 9, 3, 24, 11),
            updated_at=utc_datetime(2026, 4, 9, 3, 30, 0),
            deleted_at=None,
            tags=[],
            person=[],
            tasks=[],
            visions=[],
            events=[],
            timelogs=[],
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "get_note", fake_get_note)

    exit_code = cli.main(["note", "show", "11111111-1111-1111-1111-111111111111"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "content:\nfirst line\nsecond line" in captured.out
    assert "status: active" in captured.out


def test_main_note_show_prints_extended_relations(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_note(
        session: object,
        *,
        note_id: UUID,
    ) -> object:
        return make_record(
            id=note_id,
            content="linked note",
            created_at=utc_datetime(2026, 4, 9, 3, 24, 11),
            updated_at=utc_datetime(2026, 4, 9, 3, 30, 0),
            deleted_at=None,
            tags=[make_record(id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), name="research")],
            tasks=[
                make_record(
                    id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
                    content="Investigate note relations",
                )
            ],
            visions=[
                make_record(id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"), name="Graph notes")
            ],
            events=[
                make_record(id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"), title="Partner sync")
            ],
            person=[make_record(id=UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"), name="Alice")],
            timelogs=[
                make_record(
                    id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
                    title="Implementation session",
                )
            ],
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "get_note", fake_get_note)

    exit_code = cli.main(["note", "show", "11111111-1111-1111-1111-111111111111"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "tags: research" in captured.out
    assert (
        "tasks: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb | Investigate note relations" in captured.out
    )
    assert "visions: cccccccc-cccc-cccc-cccc-cccccccccccc | Graph notes" in captured.out
    assert "events: dddddddd-dddd-dddd-dddd-dddddddddddd | Partner sync" in captured.out
    assert "person: Alice" in captured.out
    assert "timelogs: ffffffff-ffff-ffff-ffff-ffffffffffff | Implementation session" in captured.out


def test_main_note_show_reports_missing_note(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_note(
        session: object,
        *,
        note_id: UUID,
    ) -> object | None:
        return None

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "get_note", fake_get_note)

    exit_code = cli.main(["note", "show", "11111111-1111-1111-1111-111111111111"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "was not found" in captured.err


def test_main_note_search_prints_matching_notes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_search_notes(
        session: object,
        *,
        query: str,
        limit: int,
        offset: int,
    ) -> list[object]:
        assert query == "meeting notes"
        assert limit == 100
        assert offset == 0
        return [
            make_record(
                id=UUID("44444444-4444-4444-4444-444444444444"),
                content="meeting notes for april planning",
                created_at=utc_datetime(2026, 4, 9, 4, 5, 6),
                updated_at=utc_datetime(2026, 4, 9, 4, 5, 6),
                deleted_at=None,
                tags=[],
                person=[],
                tasks=[],
                visions=[],
                events=[],
                timelogs=[],
                habit_actions=[],
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "search_notes", fake_search_notes)

    exit_code = cli.main(["note", "search", "meeting notes"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "note_id\tstatus\tcreated_at\tcontent",
        (
            "44444444-4444-4444-4444-444444444444\tactive\t2026-04-09T04:05:06+00:00\t"
            "meeting notes for april planning"
        ),
    ]


def test_main_note_batch_update_content_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_batch_update_note_content(
        session: object,
        *,
        note_ids: list[UUID],
        find_text: str,
        replace_text: str,
        case_sensitive: bool,
    ) -> NoteBatchUpdateResult:
        assert note_ids == [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        assert find_text == "draft"
        assert replace_text == "final"
        assert case_sensitive is False
        return NoteBatchUpdateResult(
            updated_count=1,
            unchanged_ids=(UUID("22222222-2222-2222-2222-222222222222"),),
            failed_ids=(),
            errors=(),
            replacement_count=3,
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "batch_update_note_content", fake_batch_update_note_content)

    exit_code = cli.main(
        [
            "note",
            "batch",
            "update-content",
            "--ids",
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "--find-text",
            "draft",
            "--replace-text",
            "final",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Updated notes: 1" in captured.out
    assert "Replacements applied: 3" in captured.out
    assert "Unchanged note IDs:" in captured.out


def test_main_note_batch_delete_reports_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_batch_delete_notes(
        session: object,
        *,
        note_ids: list[UUID],
    ) -> BatchDeleteResult:
        assert note_ids == [
            UUID("11111111-1111-1111-1111-111111111111"),
            UUID("22222222-2222-2222-2222-222222222222"),
        ]
        return BatchDeleteResult(
            deleted_count=1,
            failed_ids=(UUID("22222222-2222-2222-2222-222222222222"),),
            errors=("Note 22222222-2222-2222-2222-222222222222 was not found",),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "batch_delete_notes", fake_batch_delete_notes)

    exit_code = cli.main(
        [
            "note",
            "batch",
            "delete",
            "--ids",
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Deleted notes: 1" in captured.out
    assert "Failed note IDs:" in captured.err
    assert "was not found" in captured.err


def test_main_note_list_prints_formatted_notes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_notes(
        session: object,
        *,
        limit: int,
        offset: int,
    ) -> list[object]:
        assert limit == 100
        assert offset == 0
        return [
            make_record(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                content="first note",
                created_at=utc_datetime(2026, 4, 9, 1, 2, 3),
                updated_at=utc_datetime(2026, 4, 9, 1, 2, 3),
                deleted_at=None,
                tags=[],
                person=[],
                tasks=[],
                visions=[],
                events=[],
                timelogs=[],
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "list_notes", fake_list_notes)

    exit_code = cli.main(["note", "list"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "note_id\tstatus\tcreated_at\tcontent",
        "22222222-2222-2222-2222-222222222222\tactive\t2026-04-09T01:02:03+00:00\tfirst note",
    ]


def test_main_note_list_can_include_relationship_counts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_list_notes(
        session: object,
        *,
        limit: int,
        offset: int,
    ) -> list[object]:
        assert limit == 100
        assert offset == 0
        return [
            make_record(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                content="first note",
                created_at=utc_datetime(2026, 4, 9, 1, 2, 3),
                updated_at=utc_datetime(2026, 4, 9, 1, 2, 3),
                deleted_at=None,
                tags=[object()],
                person=[],
                tasks=[object()],
                visions=[],
                events=[],
                timelogs=[],
            )
        ]

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "list_notes", fake_list_notes)

    exit_code = cli.main(["note", "list", "--with-counts"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines() == [
        "note_id\tstatus\tcreated_at\ttask_count\tvision_count\tevent_count\tperson_count\ttimelog_count\thabit_action_count\ttag_count\tcontent",
        (
            "22222222-2222-2222-2222-222222222222\tactive\t2026-04-09T01:02:03+00:00\t"
            "1\t0\t0\t0\t0\t0\t1\tfirst note"
        ),
    ]


def test_main_note_delete_reports_missing_note(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_delete_note(
        session: object,
        *,
        note_id: UUID,
    ) -> None:
        raise NoteNotFoundError(f"Note {note_id} was not found")

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "delete_note", fake_delete_note)

    exit_code = cli.main(["note", "delete", "33333333-3333-3333-3333-333333333333"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Note 33333333-3333-3333-3333-333333333333 was not found" in captured.err


def test_main_note_add_prints_actionable_database_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clear_config_cache()
    monkeypatch.setenv("LIFEOS_CONFIG_FILE", str(tmp_path / "missing-config.toml"))
    monkeypatch.delenv("LIFEOS_DATABASE_URL", raising=False)

    exit_code = cli.main(["note", "add", "a new note"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Run `lifeos init`" in captured.err


def test_main_note_add_prints_actionable_authentication_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_test_config(monkeypatch=monkeypatch, tmp_path=tmp_path, include_database=True)

    async def fake_create_note(session: object, *, content: str) -> object:
        raise OperationalError(
            statement=None,
            params=None,
            orig=RuntimeError("password authentication failed"),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(note_services, "create_note", fake_create_note)

    exit_code = cli.main(["note", "add", "a new note"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Authentication failed." in captured.err
    clear_config_cache()
