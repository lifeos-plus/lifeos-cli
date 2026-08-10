"""Tests for the shared task presentation view assembly (issue #263).

These tests lock the CLI text output and the Web task-tree payload contract
so the shared presentation view can be refactored without drifting either
consumer's user-visible behavior.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, cast
from uuid import UUID

import pytest

from lifeos_cli.cli_support.resources.task.handlers import (
    _format_task_detail,
    _format_task_tree,
)
from lifeos_cli.db.services.read_models import PersonSummaryView, TaskView
from lifeos_cli.db.services.task_queries import TaskWithSubtasks
from lifeos_cli.presentation.tasks import (
    build_task_tree_presentation_view,
    task_tree_view_to_payload,
)
from tests.config_support import install_test_config

ROOT_ID = UUID("11111111-1111-1111-1111-111111111111")
VISION_ID = UUID("22222222-2222-2222-2222-222222222222")
CHILD_ID = UUID("33333333-3333-3333-3333-333333333333")
PERSON_ID = UUID("44444444-4444-4444-4444-444444444444")
TIMESTAMP = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)
UPDATED_AT = datetime(2026, 6, 1, 13, 5, tzinfo=timezone.utc)


def build_task_view() -> TaskView:
    """Build one flat task read model with representative field values."""
    return TaskView(
        id=ROOT_ID,
        vision_id=VISION_ID,
        parent_task_id=None,
        content="Root task",
        description="Root description",
        status="todo",
        priority=2,
        display_order=1,
        estimated_effort=None,
        planning_cycle_type="day",
        planning_cycle_days=1,
        planning_cycle_start_date=date(2026, 6, 30),
        actual_effort_self=10,
        actual_effort_total=15,
        created_at=TIMESTAMP,
        updated_at=UPDATED_AT,
        deleted_at=None,
        people=(PersonSummaryView(id=PERSON_ID, name="Alice"),),
    )


def build_child_node() -> TaskWithSubtasks:
    """Build one nested task read model used as a subtree child."""
    return TaskWithSubtasks(
        task=cast(Any, object()),
        id=CHILD_ID,
        vision_id=VISION_ID,
        parent_task_id=ROOT_ID,
        content="Child task",
        description=None,
        status="in_progress",
        priority=1,
        display_order=1,
        estimated_effort=30,
        planning_cycle_type=None,
        planning_cycle_days=None,
        planning_cycle_start_date=None,
        actual_effort_self=0,
        actual_effort_total=0,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
        deleted_at=None,
        people=(),
        subtasks=(),
        completion_percentage=1.0,
        depth=1,
    )


def build_tree_node() -> TaskWithSubtasks:
    """Build a task-tree read model with one nested child."""
    return TaskWithSubtasks(
        task=cast(Any, object()),
        id=ROOT_ID,
        vision_id=VISION_ID,
        parent_task_id=None,
        content="Root task",
        description="Root description",
        status="todo",
        priority=2,
        display_order=1,
        estimated_effort=None,
        planning_cycle_type="day",
        planning_cycle_days=1,
        planning_cycle_start_date=date(2026, 6, 30),
        actual_effort_self=10,
        actual_effort_total=15,
        created_at=TIMESTAMP,
        updated_at=UPDATED_AT,
        deleted_at=None,
        people=(PersonSummaryView(id=PERSON_ID, name="Alice"),),
        subtasks=(build_child_node(),),
        completion_percentage=0.5,
        depth=0,
    )


def test_task_tree_presentation_view_recurses_with_counts() -> None:
    view = build_task_tree_presentation_view(
        build_tree_node(),
        notes_count_by_task={ROOT_ID: 4},
        timelogs_count_by_task={CHILD_ID: 3},
    )

    assert view.completion_percentage == 0.5
    assert view.depth == 0
    assert view.notes_count == 4
    assert view.timelogs_count == 0
    child = view.subtasks[0]
    assert child.id == CHILD_ID
    assert child.parent_task_id == ROOT_ID
    assert child.completion_percentage == 1.0
    assert child.depth == 1
    assert child.notes_count == 0
    assert child.timelogs_count == 3


def test_cli_task_detail_output_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    install_test_config(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        include_preferences=True,
        timezone="UTC",
    )

    assert _format_task_detail(build_task_view()) == (
        f"id: {ROOT_ID}\n"
        f"vision_id: {VISION_ID}\n"
        "parent_task_id: -\n"
        "content: Root task\n"
        "description: Root description\n"
        "status: todo\n"
        "priority: 2\n"
        "display_order: 1\n"
        "estimated_effort: -\n"
        "planning_cycle_type: day\n"
        "planning_cycle_days: 1\n"
        "planning_cycle_start_date: 2026-06-30\n"
        "people: Alice\n"
        "actual_effort_self: 10\n"
        "actual_effort_total: 15\n"
        "created_at: 2026-06-01T13:00:00+00:00\n"
        "updated_at: 2026-06-01T13:05:00+00:00\n"
        "deleted_at: -"
    )


def test_cli_task_tree_output_contract() -> None:
    assert _format_task_tree(build_tree_node()) == (
        f"{ROOT_ID}\ttodo\t0.50\tRoot task\n  {CHILD_ID}\tin_progress\t1.00\tChild task"
    )


def test_web_task_tree_payload_contract_unchanged() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.response_schemas.tasks import TaskTreeResponse
    from lifeos_web.routers.tasks import _task_tree_payload

    payload = _task_tree_payload(
        build_tree_node(),
        notes_count_by_task={ROOT_ID: 4},
        timelogs_count_by_task={CHILD_ID: 3},
    )

    assert payload == {
        "id": str(ROOT_ID),
        "vision_id": str(VISION_ID),
        "parent_task_id": None,
        "content": "Root task",
        "description": "Root description",
        "status": "todo",
        "priority": 2,
        "display_order": 1,
        "estimated_effort": None,
        "planning_cycle_type": "day",
        "planning_cycle_days": 1,
        "planning_cycle_start_date": "2026-06-30",
        "actual_effort_self": 10,
        "actual_effort_total": 15,
        "notes_count": 4,
        "timelogs_count": 0,
        "created_at": "2026-06-01T13:00:00+00:00",
        "updated_at": "2026-06-01T13:05:00+00:00",
        "people": [{"id": str(PERSON_ID), "name": "Alice"}],
        "subtasks": [
            {
                "id": str(CHILD_ID),
                "vision_id": str(VISION_ID),
                "parent_task_id": str(ROOT_ID),
                "content": "Child task",
                "description": None,
                "status": "in_progress",
                "priority": 1,
                "display_order": 1,
                "estimated_effort": 30,
                "planning_cycle_type": None,
                "planning_cycle_days": None,
                "planning_cycle_start_date": None,
                "actual_effort_self": 0,
                "actual_effort_total": 0,
                "notes_count": 0,
                "timelogs_count": 3,
                "created_at": "2026-06-01T13:00:00+00:00",
                "updated_at": "2026-06-01T13:00:00+00:00",
                "people": [],
                "subtasks": [],
                "completion_percentage": 1.0,
                "depth": 1,
            }
        ],
        "completion_percentage": 0.5,
        "depth": 0,
    }
    assert "deleted_at" not in payload
    assert "actual_effort" not in payload
    TaskTreeResponse.model_validate(payload)


def test_task_tree_view_to_payload_is_the_web_payload_source() -> None:
    pytest.importorskip("fastapi")
    from lifeos_web.routers.tasks import _task_tree_payload

    node = build_tree_node()
    notes_count_by_task = {ROOT_ID: 4}
    timelogs_count_by_task = {CHILD_ID: 3}
    shared_payload = task_tree_view_to_payload(
        build_task_tree_presentation_view(
            node,
            notes_count_by_task=notes_count_by_task,
            timelogs_count_by_task=timelogs_count_by_task,
        )
    )
    assert shared_payload == _task_tree_payload(
        node,
        notes_count_by_task=notes_count_by_task,
        timelogs_count_by_task=timelogs_count_by_task,
    )
