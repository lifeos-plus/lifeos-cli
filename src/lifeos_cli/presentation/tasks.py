"""Shared task-tree presentation assembly for CLI and Web output adapters.

The CLI task-tree rendering and the Web task-tree payload previously selected
the same task fields, assembled the same nested structure, and resolved the
same relation counts on their own. This module owns that conversion once:
``build_task_tree_presentation_view`` assembles the nested presentation view
from the task read model, and ``task_tree_view_to_payload`` renders the
Web-compatible JSON payload from that view. Each consumer keeps a thin
adapter on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from lifeos_cli.db.services.read_models import PersonSummaryView
from lifeos_cli.db.services.task_queries import TaskWithSubtasks


@dataclass(frozen=True)
class TaskTreePresentationView:
    """Presentation view for one task-tree node shared by CLI and Web output."""

    id: UUID
    vision_id: UUID
    parent_task_id: UUID | None
    content: str
    description: str | None
    status: str
    priority: int
    display_order: int
    estimated_effort: int | None
    planning_cycle_type: str | None
    planning_cycle_days: int | None
    planning_cycle_start_date: date | None
    actual_effort_self: int
    actual_effort_total: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    people: tuple[PersonSummaryView, ...]
    subtasks: tuple[TaskTreePresentationView, ...]
    completion_percentage: float
    depth: int
    notes_count: int
    timelogs_count: int


def build_task_tree_presentation_view(
    node: TaskWithSubtasks,
    *,
    notes_count_by_task: dict[UUID, int] | None = None,
    timelogs_count_by_task: dict[UUID, int] | None = None,
) -> TaskTreePresentationView:
    """Recursively assemble the shared presentation view for a task subtree."""
    notes_count = notes_count_by_task or {}
    timelogs_count = timelogs_count_by_task or {}
    return TaskTreePresentationView(
        id=node.id,
        vision_id=node.vision_id,
        parent_task_id=node.parent_task_id,
        content=node.content,
        description=node.description,
        status=node.status,
        priority=node.priority,
        display_order=node.display_order,
        estimated_effort=node.estimated_effort,
        planning_cycle_type=node.planning_cycle_type,
        planning_cycle_days=node.planning_cycle_days,
        planning_cycle_start_date=node.planning_cycle_start_date,
        actual_effort_self=node.actual_effort_self,
        actual_effort_total=node.actual_effort_total,
        created_at=node.created_at,
        updated_at=node.updated_at,
        deleted_at=node.deleted_at,
        people=node.people,
        subtasks=tuple(
            build_task_tree_presentation_view(
                subtask,
                notes_count_by_task=notes_count_by_task,
                timelogs_count_by_task=timelogs_count_by_task,
            )
            for subtask in node.subtasks
        ),
        completion_percentage=node.completion_percentage,
        depth=node.depth,
        notes_count=notes_count.get(node.id, 0),
        timelogs_count=timelogs_count.get(node.id, 0),
    )


def task_tree_view_to_payload(view: TaskTreePresentationView) -> dict[str, object]:
    """Render one task-tree presentation node as the Web payload shape."""
    return {
        "id": str(view.id),
        "vision_id": str(view.vision_id),
        "parent_task_id": str(view.parent_task_id) if view.parent_task_id else None,
        "content": view.content,
        "description": view.description,
        "status": view.status,
        "priority": view.priority,
        "display_order": view.display_order,
        "estimated_effort": view.estimated_effort,
        "planning_cycle_type": view.planning_cycle_type,
        "planning_cycle_days": view.planning_cycle_days,
        "planning_cycle_start_date": (
            view.planning_cycle_start_date.isoformat() if view.planning_cycle_start_date else None
        ),
        "actual_effort_self": view.actual_effort_self,
        "actual_effort_total": view.actual_effort_total,
        "notes_count": view.notes_count,
        "timelogs_count": view.timelogs_count,
        "created_at": view.created_at.isoformat(),
        "updated_at": view.updated_at.isoformat(),
        "people": [{"id": str(person.id), "name": person.name} for person in view.people],
        "subtasks": [task_tree_view_to_payload(subtask) for subtask in view.subtasks],
        "completion_percentage": view.completion_percentage,
        "depth": view.depth,
    }
