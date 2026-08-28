from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from lifeos_cli import cli
from lifeos_cli.cli_support.resources.schedule import handlers as schedule_handlers
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import schedules
from tests.support import make_session_scope, utc_datetime


@pytest.fixture(autouse=True)
def stub_schedule_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_reconcile_planning_habit_action_lifecycle(
        session: object,
        *,
        reference_date: date,
        start_date: date,
        end_date: date,
    ) -> int:
        return 0

    monkeypatch.setattr(
        schedule_handlers.planning_lifecycle_services,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile_planning_habit_action_lifecycle,
    )


def test_main_schedule_show_prints_grouped_sections(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> object:
        assert str(target_date) == "2026-04-10"
        assert hide_overdue_unfinished is False
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(
                schedules.ScheduleTaskItem(
                    id=UUID("11111111-1111-1111-1111-111111111111"),
                    content="Draft release checklist",
                    status="todo",
                    planning_cycle_type="week",
                    planning_cycle_days=7,
                    planning_cycle_start_date=target_date,
                    planning_cycle_end_date=target_date,
                ),
            ),
            habit_actions=(
                schedules.ScheduleHabitActionItem(
                    id=UUID("22222222-2222-2222-2222-222222222222"),
                    habit_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
                    habit_title="Daily Review",
                    action_date=target_date,
                    status="todo",
                    notes=None,
                ),
            ),
            events=(
                schedules.ScheduleEventItem(
                    id=UUID("33333333-3333-3333-3333-333333333333"),
                    title="Doctor appointment",
                    status="planned",
                    event_type="appointment",
                    start_time=utc_datetime(2026, 4, 10, 13, 0),
                    end_time=utc_datetime(2026, 4, 10, 14, 0),
                    task_id=None,
                ),
                schedules.ScheduleEventItem(
                    id=UUID("44444444-4444-4444-4444-444444444444"),
                    title="Tax deadline",
                    status="planned",
                    event_type="deadline",
                    start_time=utc_datetime(2026, 4, 10, 23, 59, 59),
                    end_time=None,
                    task_id=None,
                ),
            ),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)

    exit_code = cli.main(["schedule", "show", "--date", "2026-04-10"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "date: 2026-04-10" in captured.out
    assert "tasks:" in captured.out
    assert (
        "  task_id\tstatus\tplanning_cycle_type\tplanning_cycle_start_date\t"
        "planning_cycle_end_date\tcontent" in captured.out
    )
    assert "habit_actions:" in captured.out
    assert "  habit_action_id\tstatus\taction_date\thabit_title" in captured.out
    assert "todo\t2026-04-10\tDaily Review" in captured.out
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" not in captured.out
    assert "events:" in captured.out
    assert "  event_id\tevent_type\tstart_time\tend_time\ttitle" in captured.out
    assert "33333333-3333-3333-3333-333333333333\tappointment" in captured.out
    deadline_line = next(
        line for line in captured.out.splitlines() if "44444444-4444-4444-4444-444444444444" in line
    )
    deadline_columns = deadline_line.split("\t")
    assert deadline_columns[1] == "deadline"
    assert deadline_columns[2] == deadline_columns[3]
    assert deadline_columns[-1] == "Tax deadline"
    assert "33333333-3333-3333-3333-333333333333\tplanned" not in captured.out
    assert "appointments:" not in captured.out
    assert "timeblocks:" not in captured.out
    assert "deadlines:" not in captured.out
    assert "Draft release checklist" in captured.out
    assert "Daily Review" in captured.out
    assert "Doctor appointment" in captured.out


def test_main_schedule_show_passes_hide_overdue_unfinished(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> object:
        assert str(target_date) == "2026-04-10"
        assert hide_overdue_unfinished is True
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)

    exit_code = cli.main(["schedule", "show", "--date", "2026-04-10", "--hide-overdue-unfinished"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "date: 2026-04-10" in captured.out


def test_main_schedule_show_defaults_to_operational_date(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> object:
        assert target_date == date(2026, 4, 22)
        assert hide_overdue_unfinished is False
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)
    monkeypatch.setattr(schedule_handlers, "get_operational_date", lambda: date(2026, 4, 22))

    exit_code = cli.main(["schedule", "show"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "date: 2026-04-22" in captured.out


def test_main_schedule_show_reconciles_habit_action_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_lifecycle: dict[str, date] = {}

    async def fake_reconcile_planning_habit_action_lifecycle(
        session: object,
        *,
        reference_date: date,
        start_date: date,
        end_date: date,
    ) -> int:
        captured_lifecycle.update(
            reference_date=reference_date,
            start_date=start_date,
            end_date=end_date,
        )
        return 3

    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> object:
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)
    monkeypatch.setattr(
        schedule_handlers.planning_lifecycle_services,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile_planning_habit_action_lifecycle,
    )

    exit_code = cli.main(["schedule", "show", "--date", "2026-04-10"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_lifecycle == {
        "reference_date": date(2026, 4, 10),
        "start_date": date.min,
        "end_date": date(2026, 4, 10),
    }
    assert "date: 2026-04-10" in captured.out


def test_main_schedule_list_rejects_inverted_date_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "schedule",
            "list",
            "--start-date",
            "2026-04-11",
            "--end-date",
            "2026-04-10",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "The --end-date value must be on or after --start-date." in captured.err


def test_main_schedule_list_treats_repeated_dates_as_discrete_days(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    requested_dates: list[date] = []

    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> schedules.ScheduleDay:
        requested_dates.append(target_date)
        assert hide_overdue_unfinished is False
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)

    exit_code = cli.main(["schedule", "list", "--date", "2026-04-11", "--date", "2026-04-10"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert requested_dates == [date(2026, 4, 11), date(2026, 4, 10)]
    assert "date: 2026-04-11" in captured.out
    assert "date: 2026-04-10" in captured.out


def test_main_schedule_list_deduplicates_repeated_dates(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    requested_dates: list[date] = []

    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> schedules.ScheduleDay:
        requested_dates.append(target_date)
        assert hide_overdue_unfinished is False
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)

    exit_code = cli.main(["schedule", "list", "--date", "2026-04-10", "--date", "2026-04-10"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert requested_dates == [date(2026, 4, 10)]
    assert captured.out.count("date: 2026-04-10") == 1


def test_main_schedule_list_reconciles_lifecycle_against_latest_requested_date(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_lifecycle: dict[str, date] = {}

    async def fake_reconcile_planning_habit_action_lifecycle(
        session: object,
        *,
        reference_date: date,
        start_date: date,
        end_date: date,
    ) -> int:
        captured_lifecycle.update(
            reference_date=reference_date,
            start_date=start_date,
            end_date=end_date,
        )
        return 2

    async def fake_get_schedule_for_date(
        session: object,
        *,
        target_date: date,
        hide_overdue_unfinished: bool,
    ) -> schedules.ScheduleDay:
        return schedules.ScheduleDay(
            local_date=target_date,
            tasks=(),
            habit_actions=(),
            events=(),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "get_schedule_for_date", fake_get_schedule_for_date)
    monkeypatch.setattr(
        schedule_handlers.planning_lifecycle_services,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile_planning_habit_action_lifecycle,
    )

    exit_code = cli.main(["schedule", "list", "--date", "2026-04-09", "--date", "2026-04-11"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_lifecycle == {
        "reference_date": date(2026, 4, 11),
        "start_date": date.min,
        "end_date": date(2026, 4, 11),
    }
    assert "date: 2026-04-09" in captured.out
    assert "date: 2026-04-11" in captured.out


def test_main_schedule_list_accepts_explicit_date_range(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_lifecycle: dict[str, date] = {}

    async def fake_reconcile_planning_habit_action_lifecycle(
        session: object,
        *,
        reference_date: date,
        start_date: date,
        end_date: date,
    ) -> int:
        captured_lifecycle.update(
            reference_date=reference_date,
            start_date=start_date,
            end_date=end_date,
        )
        return 1

    async def fake_list_schedule_in_range(
        session: object,
        *,
        start_date: date,
        end_date: date,
        hide_overdue_unfinished: bool,
    ) -> tuple[schedules.ScheduleDay, ...]:
        assert start_date == date(2026, 4, 10)
        assert end_date == date(2026, 4, 11)
        assert hide_overdue_unfinished is True
        return (
            schedules.ScheduleDay(
                local_date=start_date,
                tasks=(),
                habit_actions=(),
                events=(),
            ),
            schedules.ScheduleDay(
                local_date=end_date,
                tasks=(),
                habit_actions=(),
                events=(),
            ),
        )

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(schedules, "list_schedule_in_range", fake_list_schedule_in_range)
    monkeypatch.setattr(
        schedule_handlers.planning_lifecycle_services,
        "reconcile_planning_habit_action_lifecycle",
        fake_reconcile_planning_habit_action_lifecycle,
    )

    exit_code = cli.main(
        [
            "schedule",
            "list",
            "--start-date",
            "2026-04-10",
            "--end-date",
            "2026-04-11",
            "--hide-overdue-unfinished",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_lifecycle == {
        "reference_date": date(2026, 4, 11),
        "start_date": date.min,
        "end_date": date(2026, 4, 11),
    }
    assert "date: 2026-04-10" in captured.out
    assert "date: 2026-04-11" in captured.out


def test_main_schedule_list_rejects_mixed_date_range_styles(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "schedule",
            "list",
            "--date",
            "2026-04-10",
            "--start-date",
            "2026-04-10",
            "--end-date",
            "2026-04-11",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --date or --start-date/--end-date, not both." in captured.err


def test_main_schedule_list_rejects_incomplete_explicit_date_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(
        [
            "schedule",
            "list",
            "--start-date",
            "2026-04-10",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "start_date and end_date must be provided together." in captured.err
