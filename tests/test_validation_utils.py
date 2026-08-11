"""Tests for the shared choice-validation helper and domain wrappers."""

from __future__ import annotations

from datetime import date

import pytest

from lifeos_cli.db.services.entity_associations import (
    AssociationValidationError,
    validate_association_link_type,
    validate_association_model,
)
from lifeos_cli.db.services.event_support import (
    EventValidationError,
    validate_event_scope,
    validate_event_status,
    validate_event_type,
)
from lifeos_cli.db.services.habit_support import (
    HabitValidationError,
    validate_habit_action_status,
    validate_habit_status,
)
from lifeos_cli.db.services.recurrence_core import (
    RecurrenceValidationError,
    normalize_recurrence_frequency,
    normalize_weekday_names,
)
from lifeos_cli.db.services.tags import (
    InvalidTagEntityTypeError,
    validate_tag_entity_type,
)
from lifeos_cli.db.services.task_support import (
    InvalidPlanningCycleError,
    TaskValidationError,
    validate_planning_cycle,
    validate_task_status,
)
from lifeos_cli.db.services.timelog_support import (
    TimelogValidationError,
    validate_tracking_method,
)
from lifeos_cli.db.services.validation_utils import DomainValidationError, validate_choice
from lifeos_cli.db.services.visions import (
    VisionValidationError,
    validate_vision_status,
)


def test_validate_choice_normalizes_and_returns_value() -> None:
    assert (
        validate_choice(
            "  Active ",
            {"active", "archived"},
            error_cls=ValueError,
            label="status",
        )
        == "active"
    )


def test_validate_choice_raises_with_sorted_allowlist() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid status 'bogus'. Expected one of: active, archived",
    ):
        validate_choice(
            "bogus",
            {"archived", "active"},
            error_cls=ValueError,
            label="status",
        )


def test_validate_choice_raises_with_custom_verb() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported entity type 'bogus'. Expected one of: note, task",
    ):
        validate_choice(
            "bogus",
            {"task", "note"},
            error_cls=ValueError,
            label="entity type",
            error_verb="Unsupported",
        )


def test_validate_choice_honors_display_order() -> None:
    with pytest.raises(
        ValueError,
        match="Invalid weekday 'bogus'. Expected one of: monday, tuesday, sunday",
    ):
        validate_choice(
            "bogus",
            {"monday", "tuesday", "sunday"},
            error_cls=ValueError,
            label="weekday",
            display_order=("monday", "tuesday", "sunday"),
        )


@pytest.mark.parametrize(
    ("validator", "error_cls", "label"),
    [
        (validate_habit_status, HabitValidationError, "habit status"),
        (validate_habit_action_status, HabitValidationError, "habit-action status"),
        (validate_event_scope, EventValidationError, "event scope"),
        (validate_event_status, EventValidationError, "event status"),
        (validate_event_type, EventValidationError, "event type"),
        (validate_task_status, TaskValidationError, "task status"),
        (validate_vision_status, VisionValidationError, "vision status"),
        (validate_tracking_method, TimelogValidationError, "tracking method"),
        (validate_tag_entity_type, InvalidTagEntityTypeError, "tag entity type"),
        (validate_association_model, AssociationValidationError, "association model"),
        (
            validate_association_link_type,
            AssociationValidationError,
            "association link type",
        ),
    ],
)
def test_domain_wrappers_raise_domain_errors(
    validator: object,
    error_cls: type[Exception],
    label: str,
) -> None:
    with pytest.raises(error_cls, match=label):
        validator("not-a-valid-choice")  # type: ignore[operator]


@pytest.mark.parametrize(
    "error_cls",
    [
        HabitValidationError,
        EventValidationError,
        TaskValidationError,
        VisionValidationError,
        TimelogValidationError,
        InvalidTagEntityTypeError,
        AssociationValidationError,
        InvalidPlanningCycleError,
        RecurrenceValidationError,
    ],
)
def test_domain_errors_share_common_base(error_cls: type[Exception]) -> None:
    assert issubclass(error_cls, DomainValidationError)
    assert issubclass(error_cls, ValueError)


def test_validate_planning_cycle_uses_shared_choice_validation() -> None:
    with pytest.raises(
        InvalidPlanningCycleError,
        match="Invalid planning cycle type 'bogus'. Expected one of: "
        "7years, day, month, week, year",
    ):
        validate_planning_cycle(
            planning_cycle_type="bogus",
            planning_cycle_days=1,
            planning_cycle_start_date=date(2026, 1, 1),
        )


def test_recurrence_frequency_keeps_canonical_display_order() -> None:
    with pytest.raises(
        RecurrenceValidationError,
        match="Invalid recurrence frequency 'bogus'. Expected one of: "
        "daily, weekly, monthly, yearly",
    ):
        normalize_recurrence_frequency("bogus")


def test_recurrence_weekday_validation_preserves_weekday_order() -> None:
    with pytest.raises(
        RecurrenceValidationError,
        match="Invalid weekday 'bogus'. Expected one of: "
        "monday, tuesday, wednesday, thursday, friday, saturday, sunday",
    ):
        normalize_weekday_names(["bogus"])


def test_recurrence_weekday_validation_skips_blank_entries() -> None:
    assert normalize_weekday_names(["monday", "", "  ", "friday"]) == ("monday", "friday")
