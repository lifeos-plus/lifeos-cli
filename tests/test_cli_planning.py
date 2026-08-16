from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli import cli
from lifeos_cli.cli_support.resources.planning import handlers as planning_handlers
from lifeos_cli.db import session as db_session
from lifeos_cli.db.models import Task, Vision
from lifeos_cli.db.services import task_queries
from lifeos_cli.db.services import tasks as task_services
from tests.support import (
    make_session_scope,
    sqlite_session_factory,
    utc_datetime,
)

VISION_ONE = UUID("11111111-1111-1111-1111-111111111111")
VISION_TWO = UUID("22222222-2222-2222-2222-222222222222")
ROOT_A_ID = UUID("33333333-3333-3333-3333-333333333333")
CHILD_A_ID = UUID("44444444-4444-4444-4444-444444444444")
CONTEXT_X_ID = UUID("66666666-6666-6666-6666-666666666666")
CONTEXT_CHILD_ID = UUID("77777777-7777-7777-7777-777777777777")


def _stub_calendar_preferences(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        task_queries,
        "get_preferences_settings",
        lambda: SimpleNamespace(
            calendar_system="gregorian",
            calendar_first_day_of_week=1,
            calendar_seven_year_anchor_date="2025-07-26",
        ),
    )


async def _seed_planning_window(session: AsyncSession) -> UUID:
    vision = Vision(name="Planning")
    other_vision = Vision(name="Other")
    session.add_all([vision, other_vision])
    await session.flush()
    root_a = Task(
        vision_id=vision.id,
        content="Root A",
        planning_cycle_type="7years",
        planning_cycle_days=2555,
        planning_cycle_start_date=date(2025, 1, 1),
    )
    root_b = Task(
        vision_id=vision.id,
        content="Root B",
        status="done",
        planning_cycle_type="7years",
        planning_cycle_days=2555,
        planning_cycle_start_date=date(2025, 1, 1),
        display_order=1,
    )
    context_x = Task(
        vision_id=other_vision.id,
        content="Seven Year Vision",
        planning_cycle_type="year",
        planning_cycle_days=365,
        planning_cycle_start_date=date(2026, 7, 26),
    )
    session.add_all([root_a, root_b, context_x])
    await session.flush()
    session.add_all(
        [
            Task(
                vision_id=vision.id,
                content="Child A",
                status="in_progress",
                parent_task_id=root_a.id,
                planning_cycle_type="7years",
                planning_cycle_days=2555,
                planning_cycle_start_date=date(2025, 1, 1),
            ),
            Task(
                vision_id=vision.id,
                content="Context child",
                parent_task_id=context_x.id,
                planning_cycle_type="7years",
                planning_cycle_days=2555,
                planning_cycle_start_date=date(2025, 1, 1),
            ),
        ]
    )
    await session.commit()
    return vision.id


async def _run_with_session(
    scenario,
) -> object:
    async with sqlite_session_factory() as session_factory:
        async with session_factory() as session:
            return await scenario(session)


def test_get_planning_view_assembles_window_forest_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_calendar_preferences(monkeypatch)

    async def scenario(session: AsyncSession) -> task_services.PlanningView:
        await _seed_planning_window(session)
        return await task_queries.get_planning_view(
            session,
            cycle_type="7years",
            at_date=date(2026, 8, 11),
        )

    view = cast(task_services.PlanningView, asyncio.run(_run_with_session(scenario)))

    assert view.period_start == date(2025, 1, 1)
    assert view.period_end == date(2031, 12, 31)
    assert view.total_tasks == 4
    assert [root.content for root in view.roots] == ["Root A", "Root B", "Seven Year Vision"]
    assert [child.content for child in view.roots[0].subtasks] == ["Child A"]
    context_root = view.roots[2]
    assert context_root.id in view.context_root_ids
    assert context_root.depth == 0
    assert [child.content for child in context_root.subtasks] == ["Context child"]
    assert context_root.subtasks[0].depth == 1


def test_get_planning_view_limits_tree_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_calendar_preferences(monkeypatch)

    async def scenario(session: AsyncSession) -> task_services.PlanningView:
        await _seed_planning_window(session)
        return await task_queries.get_planning_view(
            session,
            cycle_type="7years",
            at_date=date(2026, 8, 11),
            max_depth=0,
        )

    view = cast(task_services.PlanningView, asyncio.run(_run_with_session(scenario)))

    assert [root.content for root in view.roots] == ["Root A", "Root B", "Seven Year Vision"]
    assert view.roots[0].subtasks == ()
    assert view.roots[2].subtasks == ()


def test_get_planning_view_applies_status_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_calendar_preferences(monkeypatch)

    async def scenario(session: AsyncSession) -> task_services.PlanningView:
        await _seed_planning_window(session)
        return await task_queries.get_planning_view(
            session,
            cycle_type="7years",
            at_date=date(2026, 8, 11),
            status_in="todo",
        )

    view = cast(task_services.PlanningView, asyncio.run(_run_with_session(scenario)))

    assert view.total_tasks == 2
    assert [root.content for root in view.roots] == ["Root A", "Seven Year Vision"]
    assert view.roots[0].subtasks == ()
    assert [child.content for child in view.roots[1].subtasks] == ["Context child"]


def test_get_planning_view_context_parents_respect_vision_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_calendar_preferences(monkeypatch)

    async def scenario(session: AsyncSession) -> task_services.PlanningView:
        vision_id = await _seed_planning_window(session)
        return await task_queries.get_planning_view(
            session,
            cycle_type="7years",
            at_date=date(2026, 8, 11),
            vision_in=str(vision_id),
        )

    view = cast(task_services.PlanningView, asyncio.run(_run_with_session(scenario)))

    assert view.context_root_ids == ()
    assert any(root.content == "Context child" for root in view.roots)


def test_get_planning_view_defaults_at_to_today(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_calendar_preferences(monkeypatch)
    monkeypatch.setattr(task_queries, "get_operational_date", lambda: date(2026, 8, 11))

    async def scenario(session: AsyncSession) -> task_services.PlanningView:
        return await task_queries.get_planning_view(session, cycle_type="7years")

    view = cast(task_services.PlanningView, asyncio.run(_run_with_session(scenario)))

    assert view.period_start == date(2025, 1, 1)
    assert view.period_end == date(2031, 12, 31)
    assert view.roots == ()


def test_get_planning_view_rejects_both_anchor_forms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_calendar_preferences(monkeypatch)

    with pytest.raises(ValueError, match="Use either --at or --start"):
        asyncio.run(
            task_queries.get_planning_view(
                cast(AsyncSession, object()),
                cycle_type="week",
                at_date=date(2026, 8, 11),
                start_date=date(2026, 8, 11),
            )
        )


def _node(
    *,
    task_id: UUID,
    vision_id: UUID,
    parent_task_id: UUID | None,
    content: str,
    status: str = "todo",
    estimated_effort: int | None = None,
    depth: int = 0,
    children: tuple[task_services.TaskWithSubtasks, ...] = (),
) -> task_services.TaskWithSubtasks:
    return task_services.TaskWithSubtasks(
        task=cast(Task, SimpleNamespace(id=task_id)),
        id=task_id,
        vision_id=vision_id,
        parent_task_id=parent_task_id,
        content=content,
        description=None,
        status=status,
        priority=0,
        display_order=0,
        estimated_effort=estimated_effort,
        planning_cycle_type="7years",
        planning_cycle_days=2555,
        planning_cycle_start_date=date(2025, 1, 1),
        actual_effort_self=0,
        actual_effort_total=0,
        created_at=utc_datetime(2026, 1, 1),
        updated_at=utc_datetime(2026, 1, 1),
        deleted_at=None,
        person=(),
        subtasks=children,
        completion_percentage=0.0,
        depth=depth,
    )


def _sample_view() -> task_services.PlanningView:
    child = _node(
        task_id=CHILD_A_ID,
        vision_id=VISION_ONE,
        parent_task_id=ROOT_A_ID,
        content="Child A",
        status="in_progress",
        depth=1,
    )
    root_a = _node(
        task_id=ROOT_A_ID,
        vision_id=VISION_ONE,
        parent_task_id=None,
        content="Root A",
        estimated_effort=120,
        children=(child,),
    )
    context_child = _node(
        task_id=CONTEXT_CHILD_ID,
        vision_id=VISION_TWO,
        parent_task_id=CONTEXT_X_ID,
        content="Context child",
        depth=1,
    )
    context_x = _node(
        task_id=CONTEXT_X_ID,
        vision_id=VISION_TWO,
        parent_task_id=None,
        content="Seven Year Vision",
        status="done",
        children=(context_child,),
    )
    return task_services.PlanningView(
        cycle_type="7years",
        period_start=date(2025, 1, 1),
        period_end=date(2031, 12, 31),
        roots=(root_a, context_x),
        context_root_ids=(CONTEXT_X_ID,),
        total_tasks=3,
    )


def test_main_planning_show_prints_cross_vision_tree(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_get_planning_view(_session: object, **kwargs: object) -> object:
        assert kwargs["cycle_type"] == "7years"
        assert kwargs["at_date"] == date(2026, 8, 11)
        assert kwargs["start_date"] is None
        assert kwargs["vision_in"] == str(VISION_ONE)
        assert kwargs["status_in"] == "todo,in_progress"
        assert kwargs["max_depth"] == 2
        assert kwargs["limit"] == 50
        return _sample_view()

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        planning_handlers.task_services,
        "get_planning_view",
        fake_get_planning_view,
    )

    exit_code = cli.main(
        [
            "planning",
            "show",
            "--cycle-type",
            "7years",
            "--at",
            "2026-08-11",
            "--depth",
            "2",
            "--status",
            "todo,in_progress",
            "--vision",
            str(VISION_ONE),
            "--limit",
            "50",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.splitlines()[:4] == [
        "planning_view: 7years",
        "period_start: 2025-01-01",
        "period_end: 2031-12-31",
        "total_tasks: 3",
    ]
    assert captured.out.splitlines()[4] == (
        "status\tvision_id\tcontent\tplanning_cycle_window\testimated_effort"
    )
    assert captured.out.splitlines()[5] == (
        f"todo\t{VISION_ONE}\tRoot A\t2025-01-01..2031-12-30\t120"
    )
    assert captured.out.splitlines()[6] == (
        f"  in_progress\t{VISION_ONE}\tChild A\t2025-01-01..2031-12-30\t-"
    )
    assert captured.out.splitlines()[7] == (
        f"done\t{VISION_TWO}\t(context) Seven Year Vision\t2025-01-01..2031-12-30\t-"
    )
    assert captured.out.splitlines()[8] == (
        f"  todo\t{VISION_TWO}\tContext child\t2025-01-01..2031-12-30\t-"
    )


def test_main_planning_show_passes_through_default_anchor(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_kwargs: dict[str, object] = {}

    async def fake_get_planning_view(_session: object, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _sample_view()

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        planning_handlers.task_services,
        "get_planning_view",
        fake_get_planning_view,
    )

    exit_code = cli.main(["planning", "show", "--cycle-type", "7years"])
    capsys.readouterr()

    assert exit_code == 0
    assert captured_kwargs["at_date"] is None
    assert captured_kwargs["start_date"] is None


def test_main_planning_show_passes_start_anchor_through(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_kwargs: dict[str, object] = {}

    async def fake_get_planning_view(_session: object, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _sample_view()

    monkeypatch.setattr(db_session, "session_scope", make_session_scope())
    monkeypatch.setattr(
        planning_handlers.task_services,
        "get_planning_view",
        fake_get_planning_view,
    )

    exit_code = cli.main(["planning", "show", "--cycle-type", "year", "--start", "2026-07-26"])
    capsys.readouterr()

    assert exit_code == 0
    assert captured_kwargs["cycle_type"] == "year"
    assert captured_kwargs["start_date"] == date(2026, 7, 26)
    assert captured_kwargs["at_date"] is None


def test_main_planning_show_rejects_conflicting_anchor_flags(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(db_session, "session_scope", make_session_scope())

    exit_code = cli.main(
        [
            "planning",
            "show",
            "--cycle-type",
            "7years",
            "--at",
            "2026-08-11",
            "--start",
            "2025-01-01",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Use either --at or --start, not both." in captured.err


def test_main_planning_show_rejects_negative_depth(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(db_session, "session_scope", make_session_scope())

    exit_code = cli.main(["planning", "show", "--cycle-type", "week", "--depth", "-1"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "--depth must be a non-negative integer." in captured.err
