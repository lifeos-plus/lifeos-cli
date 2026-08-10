"""Shared presentation view assembly for CLI and Web output adapters.

Domain read models in ``lifeos_cli.db.services`` stay transport-neutral.
Presentation helpers in this package assemble display-oriented views on top of
those read models so CLI text rendering and Web JSON payloads share one
conversion source instead of maintaining parallel field selections.
"""

from lifeos_cli.presentation.tasks import (
    TaskTreePresentationView,
    build_task_tree_presentation_view,
    task_tree_view_to_payload,
)

__all__ = [
    "TaskTreePresentationView",
    "build_task_tree_presentation_view",
    "task_tree_view_to_payload",
]
