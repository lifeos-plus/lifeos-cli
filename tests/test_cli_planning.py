from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli import cli
from lifeos_cli.application.preferences import CalendarPreferences
from lifeos_cli.cli_support.resources.planning import handlers as planning_handlers
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import planning_views
from tests.support import make_session_scope, utc_datetime

VISION_ONE = UUID("11111111-1111-1111-1111-111111111111")
VISION_TWO = UUID("22222222-2222-2222-2222-222222222222")
ROOT_A_ID = UUID("33333333-3333-3333-3333-333333333333")
CHILD_A_ID = UUID("44444444-4444-4444-4444-444444444444")
ROOT_B_ID = UUID("55555555-5555-5555-5555-555555555555")
CONTEXT_X_ID = UUID("66666666-6666-6666-6666-666666666666")
CONTEXT_CHILD_ID = UUID("77777777-7777-7777-7777-777777777777")


def _flat_task(
    *,
    task_id: UUID,
    vision_id: UUID,
    parent_task_id: UUID | None,
    content: str,
    status: str = "todo",
    display_order: int = 0,
) -> planning_views.PlanningTaskFlat:
    return planning_views.PlanningTaskFlat(
        id=task_id,
        vision_id=vision_id,
        parent_task_id=parent_task_id,
        content=content,
        status=status,
        estimated_effort=None,
        planning_cycle_type="7years",
        planning_cycle_start_date=date(2025, 1, 1),
        planning_cycle_days=2555,
        display_order=display_order,
        created_at=utc_datetime(2026, 1, 1),
    )


def test_build_planning_forest_nests_in_window_tasks_and_collapses_context_parents() -> None:
    tasks = (
        _flat_task(task_id=ROOT_A_ID, vision_id=VISION_ONE, parent_task_id=None, content="Root A"),
        _flat_task(
            task_id=CHILD_A_ID,
            vision_id=VISION_ONE,
            parent_task_id=ROOT_A_ID,
            content="Child A",
        ),
        _flat_task(task_id=ROOT_B_ID, vision_id=VISION_TWO, parent_task_id=None, content="Root B"),
        _flat_task(
            task_id=CONTEXT_CHILD_ID,
            vision_id=VISION_TWO,
            parent_task_id=CONTEXT_X_ID,
            content="Context child",
        ),
    )
    context_parents = (
        _flat_task(task_id=CONTEXT_X_ID, vision_id=VISION_TWO, parent_task_id=None, content="X"),
    )

    roots = planning_views.build_planning_forest(tasks, context_parents=context_parents)

    assert [root.content for root in roots] == ["Root A", "Root B", "X"]
    root_a = roots[0]
    assert root_a.is_context is False
    assert [child.content for child in root_a.children] == ["Child A"]
    assert root_a.children[0].depth == 1
    context_root = roots[2]
    assert context_root.is_context is True
    assert context_root.depth == 0
    assert [child.content for child in context_root.children] == ["Context child"]
    assert context_root.children[0].depth == 1


def test_build_planning_forest_limits_depth_and_surfaces_isolated_roots() -> None:
    tasks = (
        _flat_task(task_id=ROOT_A_ID, vision_id=VISION_ONE, parent_task_id=None, content="Root A"),
        _flat_task(
            task_id=CHILD_A_ID,
            vision_id=VISION_ONE,
            parent_task_id=ROOT_A_ID,
            content="Child A",
        ),
        _flat_task(
            task_id=CONTEXT_CHILD_ID,
            vision_id=VISION_TWO,
            parent_task_id=CONTEXT_X_ID,
            content="Context child",
        ),
    )

    roots_without_context = planning_views.build_planning_forest(tasks, max_depth=0)
    roots_with_context = planning_views.build_planning_forest(
        tasks,
        context_parents=(
            _flat_task(
                task_id=CONTEXT_X_ID,
                vision_id=VISION_TWO,
                parent_task_id=None,
                content="X",
            ),
        ),
        max_depth=0,
    )

    assert [root.content for root in roots_without_context] == ["Root A", "Context child"]
    assert roots_without_context[0].children == ()
    assert [root.content for root in roots_with_context] == ["Root A", "X"]
    assert roots_with_context[1].is_context is True
    assert roots_with_context[1].children == ()


def test_get_planning_view_computes_period_and_wires_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flat_tasks = (
        _flat_task(task_id=ROOT_A_ID, vision_id=VISION_ONE, parent_task_id=None, content="Root A"),
        _flat_task(
            task_id=CHILD_A_ID,
            vision_id=VISION_ONE,
            parent_task_id=ROOT_A_ID,
            content="Child A",
        ),
    )

    async def fake_list_tasks(_session: object, **kwargs: object) -> list[object]:
        assert kwargs["planning_cycle_type"] == "7years"
        assert kwargs["planning_cycle_start_date"] == date(2025, 1, 1)
        assert kwargs["vision_in"] == str(VISION_ONE)
        assert kwargs["status_in"] == "todo,in_progress"
        return list(flat_tasks)

    async def fake_load_context(
        _session: object,
        tasks: object,
        *,
        vision_in: object,
    ) -> tuple[()]:
        del tasks, vision_in
        return ()

    monkeypatch.setattr(planning_views.task_queries, "list_tasks", fake_list_tasks)
    monkeypatch.setattr(planning_views, "_load_context_parents", fake_load_context)
    monkeypatch.setattr(planning_views, "get_calendar_preferences", _stub_preferences)

    view = asyncio.run(
        planning_views.get_planning_view(
            cast(AsyncSession, object()),
            cycle_type="7years",
            at_date=date(2026, 8, 11),
            vision_in=str(VISION_ONE),
            status_in="todo,in_progress",
        )
    )

    assert view.period_start == date(2025, 1, 1)
    assert view.period_end == date(2031, 12, 31)
    assert view.total_tasks == 2
    assert [root.content for root in view.roots] == ["Root A"]


def test_get_planning_view_defaults_at_to_today(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    async def fake_list_tasks(_session: object, **kwargs: object) -> list[object]:
        captured_kwargs.update(kwargs)
        return []

    async def fake_load_context(
        _session: object,
        tasks: object,
        *,
        vision_in: object,
    ) -> tuple[()]:
        del tasks, vision_in
        return ()

    class _FakeDate:
        @staticmethod
        def today() -> date:
            return date(2026, 8, 11)

        @staticmethod
        def fromisoformat(value: str) -> date:
            return date.fromisoformat(value)

    monkeypatch.setattr(planning_views, "get_calendar_preferences", _stub_preferences)
    monkeypatch.setattr(planning_views, "date", _FakeDate)
    monkeypatch.setattr(planning_views.task_queries, "list_tasks", fake_list_tasks)
    monkeypatch.setattr(planning_views, "_load_context_parents", fake_load_context)

    view = asyncio.run(
        planning_views.get_planning_view(
            cast(AsyncSession, object()),
            cycle_type="7years",
        )
    )

    assert captured_kwargs["planning_cycle_start_date"] == date(2025, 1, 1)
    assert view.period_start == date(2025, 1, 1)
    assert view.period_end == date(2031, 12, 31)


def test_get_planning_view_rejects_both_anchor_forms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(planning_views, "get_calendar_preferences", _stub_preferences)

    with pytest.raises(ValueError, match="Use either --at or --start"):
        asyncio.run(
            planning_views.get_planning_view(
                cast(AsyncSession, object()),
                cycle_type="week",
                at_date=date(2026, 8, 11),
                start_date=date(2026, 8, 11),
            )
        )


class _FakeSession:
    """Minimal session stub returning one scalars result."""

    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    async def execute(self, _stmt: object) -> object:
        return SimpleNamespace(scalars=lambda: self._rows)


def test_load_context_parents_filters_by_vision() -> None:
    tasks = (
        _flat_task(
            task_id=CONTEXT_CHILD_ID,
            vision_id=VISION_ONE,
            parent_task_id=CONTEXT_X_ID,
            content="Context child",
        ),
    )
    session = _FakeSession(
        [
            _flat_task(
                task_id=CONTEXT_X_ID,
                vision_id=VISION_ONE,
                parent_task_id=None,
                content="X",
            ),
            _flat_task(
                task_id=ROOT_B_ID,
                vision_id=VISION_TWO,
                parent_task_id=None,
                content="Other vision",
            ),
        ]
    )

    parents = asyncio.run(
        planning_views._load_context_parents(
            cast(AsyncSession, session),
            tasks,
            vision_in=str(VISION_ONE),
        )
    )

    assert [parent.id for parent in parents] == [CONTEXT_X_ID]


def _stub_preferences() -> CalendarPreferences:
    return CalendarPreferences(
        system="gregorian",
        first_day_of_week=1,
        seven_year_anchor_date=date(2025, 7, 26),
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
    is_context: bool = False,
    children: tuple[planning_views.PlanningTaskNode, ...] = (),
) -> planning_views.PlanningTaskNode:
    return planning_views.PlanningTaskNode(
        id=task_id,
        vision_id=vision_id,
        parent_task_id=parent_task_id,
        content=content,
        status=status,
        estimated_effort=estimated_effort,
        planning_cycle_type="7years",
        planning_cycle_start_date=date(2025, 1, 1),
        planning_cycle_days=2555,
        depth=depth,
        is_context=is_context,
        children=children,
    )


def _sample_view() -> planning_views.PlanningView:
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
        is_context=True,
        children=(context_child,),
    )
    return planning_views.PlanningView(
        cycle_type="7years",
        period_start=date(2025, 1, 1),
        period_end=date(2031, 12, 31),
        roots=(root_a, context_x),
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
        planning_handlers.planning_views,
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
        planning_handlers.planning_views,
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
        planning_handlers.planning_views,
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
