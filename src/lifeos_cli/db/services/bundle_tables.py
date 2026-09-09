"""Lossless table snapshots used by database bundle backup and restore."""

from __future__ import annotations

import math
from collections.abc import AsyncGenerator, Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    Table,
    and_,
    insert,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import (
    normalize_storage_datetime,
    parse_iso_datetime_input,
)
from lifeos_cli.db.base import Base
from lifeos_cli.db.models.association import (
    ASSOCIATION_MODEL_MAP,
    ASSOCIATION_SOURCE_MODELS,
    ASSOCIATION_TARGET_MODELS,
    VALID_ASSOCIATION_LINK_TYPES,
)
from lifeos_cli.db.models.event_occurrence_exception import EVENT_OCCURRENCE_ACTIONS
from lifeos_cli.db.models.finance import FINANCE_RATE_SNAPSHOT_POLICIES
from lifeos_cli.db.models.menstrual import MENSTRUAL_FLOW_AMOUNTS
from lifeos_cli.db.models.tag import TAG_ENTITY_TYPES
from lifeos_cli.db.services.event_support import VALID_EVENT_STATUSES, VALID_EVENT_TYPES
from lifeos_cli.db.services.habit_support import (
    MAX_HABIT_DURATION_DAYS,
    VALID_HABIT_ACTION_STATUSES,
    VALID_HABIT_STATUSES,
)
from lifeos_cli.db.services.hierarchy import (
    HierarchyValidationError,
    validate_finance_node_hierarchy,
    validate_task_hierarchy,
)
from lifeos_cli.db.services.recurrence_core import (
    VALID_RECURRENCE_FREQUENCIES,
    VALID_WEEKDAY_NAMES,
)
from lifeos_cli.db.services.task_support import (
    VALID_PLANNING_CYCLE_TYPES,
    VALID_TASK_STATUSES,
)
from lifeos_cli.db.services.timelog_support import VALID_TIMELOG_TRACKING_METHODS
from lifeos_cli.db.services.visions import VALID_VISION_STATUSES

DERIVED_TABLE_NAMES = frozenset(
    {
        "aggregated_timelog_stats_groupby_area",
        "daily_timelog_stats_groupby_area",
    }
)


@dataclass(frozen=True)
class BundleTableSpec:
    """One immutable table contract for a versioned lossless bundle."""

    name: str
    columns: tuple[str, ...]


BUNDLE_V4_TABLE_SPECS = (
    BundleTableSpec(
        "areas",
        (
            "name",
            "description",
            "color",
            "icon",
            "is_active",
            "display_order",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "associations",
        (
            "source_model",
            "source_id",
            "target_model",
            "target_id",
            "link_type",
            "id",
            "created_at",
            "updated_at",
        ),
    ),
    BundleTableSpec(
        "body_measurements",
        (
            "measured_at",
            "weight_kg",
            "body_fat_percentage",
            "visceral_fat",
            "fat_mass_kg",
            "muscle_percentage",
            "muscle_mass_kg",
            "body_water_kg",
            "protein_kg",
            "bone_mass_kg",
            "skeletal_muscle_kg",
            "notes",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_assets",
        (
            "code",
            "name",
            "decimal_places",
            "display_order",
            "is_default",
            "metadata",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_rate_snapshots",
        (
            "captured_at",
            "source",
            "note",
            "metadata",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_trees",
        (
            "name",
            "primary_currency",
            "display_order",
            "is_default",
            "metadata",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "menstrual_days",
        (
            "log_date",
            "in_period",
            "flow_amount",
            "symptoms",
            "mood_changes",
            "protection_used",
            "spotting",
            "notes",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "menstrual_factors",
        ("name", "id", "created_at", "updated_at", "deleted_at"),
    ),
    BundleTableSpec(
        "notes",
        ("content", "id", "created_at", "updated_at", "deleted_at"),
    ),
    BundleTableSpec(
        "people",
        (
            "name",
            "description",
            "nicknames",
            "birth_date",
            "location",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "sleep_segments",
        (
            "sleep_date",
            "start_at",
            "end_at",
            "duration_minutes",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "tags",
        (
            "name",
            "entity_type",
            "category",
            "description",
            "color",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_rate_snapshot_entries",
        (
            "rate_snapshot_id",
            "base_currency",
            "quote_currency",
            "rate",
            "source",
            "captured_at",
            "is_derived",
            "metadata",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_snapshots",
        (
            "tree_id",
            "rate_snapshot_id",
            "title",
            "snapshot_ts",
            "period_start",
            "period_end",
            "primary_currency",
            "rate_snapshot_policy",
            "total_positive",
            "total_negative",
            "net_amount",
            "exchange_rates",
            "summary",
            "note",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_tree_nodes",
        (
            "tree_id",
            "parent_id",
            "name",
            "currency_code",
            "path",
            "depth",
            "display_order",
            "children_count",
            "metadata",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec("menstrual_day_factors", ("menstrual_day_id", "factor_id")),
    BundleTableSpec("tag_associations", ("entity_id", "entity_type", "tag_id")),
    BundleTableSpec(
        "timelog_templates",
        (
            "title",
            "title_normalized",
            "area_id",
            "default_duration_minutes",
            "position",
            "usage_count",
            "last_used_at",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "visions",
        (
            "name",
            "description",
            "status",
            "stage",
            "experience_points",
            "experience_rate_per_hour",
            "area_id",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "finance_snapshot_entries",
        (
            "snapshot_id",
            "node_id",
            "amount",
            "currency_code",
            "amount_converted",
            "note",
            "is_auto_generated",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "tasks",
        (
            "vision_id",
            "parent_task_id",
            "content",
            "description",
            "status",
            "priority",
            "display_order",
            "estimated_effort",
            "planning_cycle_type",
            "planning_cycle_days",
            "planning_cycle_start_date",
            "actual_effort_self",
            "actual_effort_total",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "events",
        (
            "title",
            "description",
            "start_time",
            "end_time",
            "priority",
            "status",
            "event_type",
            "is_all_day",
            "recurrence_frequency",
            "recurrence_interval",
            "recurrence_count",
            "recurrence_until",
            "recurrence_rule",
            "area_id",
            "task_id",
            "recurrence_parent_event_id",
            "recurrence_instance_start",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "habits",
        (
            "title",
            "description",
            "start_date",
            "duration_days",
            "cadence_frequency",
            "cadence_weekdays",
            "cadence_monthdays",
            "target_per_cycle",
            "status",
            "status_changed_date",
            "task_id",
            "area_id",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "timelogs",
        (
            "title",
            "start_time",
            "end_time",
            "tracking_method",
            "location",
            "energy_level",
            "notes",
            "area_id",
            "task_id",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "event_occurrence_exceptions",
        (
            "master_event_id",
            "action",
            "instance_start",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
    BundleTableSpec(
        "habit_actions",
        (
            "habit_id",
            "action_date",
            "status",
            "id",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    ),
)
_BUNDLE_V4_SPEC_BY_NAME = {spec.name: spec for spec in BUNDLE_V4_TABLE_SPECS}


class BundleTableError(RuntimeError):
    """Raised when a lossless table snapshot is invalid."""


def source_tables() -> tuple[Table, ...]:
    """Return schema-v4 authoritative tables in its frozen foreign-key-safe order."""
    return tuple(Base.metadata.tables[spec.name] for spec in BUNDLE_V4_TABLE_SPECS)


def source_table_names() -> tuple[str, ...]:
    """Return the frozen schema-v4 source-table names."""
    return tuple(spec.name for spec in BUNDLE_V4_TABLE_SPECS)


def source_table_column_names(table_name: str) -> tuple[str, ...]:
    """Return the frozen schema-v4 columns for one source table."""
    return _BUNDLE_V4_SPEC_BY_NAME[table_name].columns


def _serialize_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return normalize_storage_datetime(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


async def iter_export_table_rows(
    session: AsyncSession,
    table: Table,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream every row, including soft-deleted rows, deterministically."""
    primary_key = list(table.primary_key.columns)
    columns = [table.c[name] for name in source_table_column_names(table.name)]
    statement = select(*columns)
    if primary_key:
        statement = statement.order_by(*primary_key)
    result = await session.stream(statement)
    row_number = 0
    try:
        async for mapping in result.mappings():
            row_number += 1
            serialized = {column.name: _serialize_value(mapping[column.name]) for column in columns}
            _prepare_table_row(table, serialized, row_number=row_number)
            yield serialized
    finally:
        await result.close()


def _validate_json_value(value: Any) -> None:
    if value is None or type(value) in {bool, int}:
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("contains a non-finite JSON number")
        return
    if isinstance(value, str):
        if "\x00" in value:
            raise ValueError("contains a null character unsupported by PostgreSQL JSON")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("contains a non-string JSON object key")
            _validate_json_value(key)
            _validate_json_value(item)
        return
    raise ValueError(f"contains unsupported JSON value {type(value).__name__}")


def _parse_value(table: Table, column: Any, value: Any, *, row_number: int) -> Any:
    label = f"{table.name} row {row_number} field {column.name!r}"
    if value is None:
        if not column.nullable and not column.primary_key:
            raise BundleTableError(f"{label} cannot be null.")
        return None

    column_type = column.type
    try:
        python_type = column_type.python_type
        if isinstance(column_type, Boolean):
            if type(value) is not bool:
                raise ValueError("must be a boolean")
            return value
        if isinstance(column_type, Integer):
            if type(value) is not int:
                raise ValueError("must be an integer")
            if not -(2**31) <= value < 2**31:
                raise ValueError("is outside the PostgreSQL INTEGER range")
            return value
        if isinstance(column_type, Numeric):
            if isinstance(value, bool):
                raise ValueError("must be a decimal number")
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                raise ValueError("must be finite")
            precision = column_type.precision
            scale = column_type.scale
            if precision is not None and scale is not None:
                quantum = Decimal(1).scaleb(-scale)
                if parsed != parsed.quantize(quantum):
                    raise ValueError(f"exceeds the numeric scale of {scale}")
                if abs(parsed) >= Decimal(10) ** (precision - scale):
                    raise ValueError(f"exceeds the numeric precision of {precision}")
            return parsed
        if isinstance(column_type, DateTime) or python_type is datetime:
            if not isinstance(value, str):
                raise ValueError("must be an ISO-8601 datetime string")
            return normalize_storage_datetime(parse_iso_datetime_input(value))
        if isinstance(column_type, Date) or python_type is date:
            if not isinstance(value, str):
                raise ValueError("must be an ISO date string")
            return date.fromisoformat(value)
        if python_type is UUID:
            if not isinstance(value, str):
                raise ValueError("must be a UUID string")
            return UUID(value)
        if isinstance(column_type, String):
            if not isinstance(value, str):
                raise ValueError("must be a string")
            if "\x00" in value:
                raise ValueError("contains a null character unsupported by PostgreSQL")
            if column_type.length is not None and len(value) > column_type.length:
                raise ValueError(f"exceeds the maximum length of {column_type.length}")
            return value
        if isinstance(column_type, JSON):
            _validate_json_value(value)
            return value
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BundleTableError(f"{label} {exc}.") from exc
    return value


def prepare_table_entry_rows(
    table: Table,
    raw_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse and validate one versioned table entry without retaining raw rows."""
    parsed_rows: list[dict[str, Any]] = []
    seen_primary_keys: set[tuple[Any, ...]] = set()
    for row_number, raw_row in enumerate(raw_rows, start=1):
        parsed = _prepare_table_row(table, raw_row, row_number=row_number)
        key = tuple(parsed[column.name] for column in table.primary_key.columns)
        if not key or any(value is None for value in key):
            raise BundleTableError(f"{table.name} row {row_number} has a null primary key.")
        if key in seen_primary_keys:
            raise BundleTableError(f"{table.name} contains duplicate primary key {key!r}.")
        seen_primary_keys.add(key)
        parsed_rows.append(parsed)
    return _sort_self_references(table, parsed_rows)


def _prepare_table_row(
    table: Table,
    raw_row: Mapping[str, Any],
    *,
    row_number: int,
) -> dict[str, Any]:
    expected_column_names = source_table_column_names(table.name)
    expected_columns = set(expected_column_names)
    actual_columns = set(raw_row)
    if actual_columns != expected_columns:
        missing_columns = sorted(expected_columns - actual_columns)
        unknown_columns = sorted(actual_columns - expected_columns)
        details = []
        if missing_columns:
            details.append("missing " + ", ".join(missing_columns))
        if unknown_columns:
            details.append("unknown " + ", ".join(unknown_columns))
        raise BundleTableError(
            f"{table.name} row {row_number} has an invalid shape ({'; '.join(details)})."
        )
    parsed = {
        column.name: _parse_value(table, column, raw_row[column.name], row_number=row_number)
        for column in (table.c[name] for name in expected_column_names)
    }
    validate_domain_row(table.name, parsed, row_number=row_number)
    return parsed


def validate_prepared_tables(prepared: Mapping[str, list[dict[str, Any]]]) -> None:
    """Validate cross-table references after every entry passes local checks."""
    _validate_snapshot_foreign_keys(prepared)
    try:
        validate_task_hierarchy(prepared["tasks"])
        validate_finance_node_hierarchy(prepared["finance_tree_nodes"])
    except HierarchyValidationError as exc:
        raise BundleTableError(str(exc)) from exc


def validate_domain_row(
    table_name: str,
    row: Mapping[str, Any],
    *,
    row_number: int,
) -> None:
    """Enforce service-level invariants for rows that bypass domain mutations."""

    def fail(message: str) -> None:
        raise BundleTableError(f"{table_name} row {row_number}: {message}")

    def require_choice(field: str, choices: Collection[str]) -> None:
        value = row.get(field)
        if value is not None and value not in choices:
            fail(f"{field} must be one of {', '.join(sorted(choices))}; got {value!r}.")

    def require_string_list(
        field: str,
        *,
        maximum_items: int | None = None,
        maximum_length: int | None = None,
    ) -> None:
        value = row.get(field)
        if value is None:
            return
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            fail(f"{field} must be an array of strings.")
        if maximum_items is not None and len(value) > maximum_items:
            fail(f"{field} must contain at most {maximum_items} values.")
        if maximum_length is not None and any(len(item) > maximum_length for item in value):
            fail(f"{field} values must be at most {maximum_length} characters.")

    try:
        if table_name == "habits":
            duration = row.get("duration_days")
            if duration is not None and not 1 <= duration <= MAX_HABIT_DURATION_DAYS:
                fail(f"duration_days must be between 1 and {MAX_HABIT_DURATION_DAYS}.")
            require_choice("status", VALID_HABIT_STATUSES)
            require_choice("cadence_frequency", VALID_RECURRENCE_FREQUENCIES)
            target = row.get("target_per_cycle")
            if target is not None and target <= 0:
                fail("target_per_cycle must be greater than zero.")
            frequency = row.get("cadence_frequency")
            weekdays = row.get("cadence_weekdays")
            monthdays = row.get("cadence_monthdays")
            if weekdays is not None and (
                not isinstance(weekdays, list)
                or any(day not in VALID_WEEKDAY_NAMES for day in weekdays)
            ):
                fail("cadence_weekdays must contain valid weekday names.")
            if monthdays is not None and (
                not isinstance(monthdays, list)
                or any(type(day) is not int or not 1 <= day <= 31 for day in monthdays)
            ):
                fail("cadence_monthdays must contain integers between 1 and 31.")
            if frequency == "daily" and (weekdays is not None or monthdays is not None):
                fail("daily cadence cannot have weekday or monthday restrictions.")
            if frequency != "monthly" and monthdays is not None:
                fail("cadence_monthdays requires monthly cadence.")
            if frequency == "daily" and target is not None and target != 1:
                fail("daily cadence requires target_per_cycle to equal 1.")
            if frequency == "weekly" and target is not None:
                capacity = len(weekdays) if weekdays else 7
                if target > capacity:
                    fail("target_per_cycle exceeds the weekly cadence capacity.")
            if frequency == "monthly" and monthdays and target is not None:
                if target > len(monthdays):
                    fail("target_per_cycle exceeds the monthly cadence capacity.")
        elif table_name == "habit_actions":
            require_choice("status", VALID_HABIT_ACTION_STATUSES)
        elif table_name == "associations":
            require_choice("source_model", ASSOCIATION_SOURCE_MODELS)
            require_choice("target_model", ASSOCIATION_TARGET_MODELS)
            require_choice("link_type", VALID_ASSOCIATION_LINK_TYPES)
        elif table_name == "tasks":
            require_choice("status", VALID_TASK_STATUSES)
            require_choice("planning_cycle_type", VALID_PLANNING_CYCLE_TYPES)
            planning = (
                row.get("planning_cycle_type"),
                row.get("planning_cycle_days"),
                row.get("planning_cycle_start_date"),
            )
            if not (
                all(value is None for value in planning)
                or all(value is not None for value in planning)
            ):
                fail("planning cycle fields must be all null or all populated.")
            if planning[1] is not None and planning[1] <= 0:
                fail("planning_cycle_days must be greater than zero.")
            for field in ("actual_effort_self", "actual_effort_total", "estimated_effort"):
                value = row.get(field)
                if value is not None and value < 0:
                    fail(f"{field} must be zero or greater.")
        elif table_name == "visions":
            require_choice("status", VALID_VISION_STATUSES)
            for field in ("stage", "experience_points"):
                value = row.get(field)
                if value is not None and value < 0:
                    fail(f"{field} must be zero or greater.")
            rate = row.get("experience_rate_per_hour")
            if rate is not None and rate <= 0:
                fail("experience_rate_per_hour must be greater than zero.")
        elif table_name == "events":
            require_choice("status", VALID_EVENT_STATUSES)
            require_choice("event_type", VALID_EVENT_TYPES)
            require_choice("recurrence_frequency", VALID_RECURRENCE_FREQUENCIES)
            priority = row.get("priority")
            if priority is not None and not 0 <= priority <= 5:
                fail("priority must be between 0 and 5.")
            if (
                row.get("end_time") is not None
                and row.get("start_time") is not None
                and row["end_time"] < row["start_time"]
            ):
                fail("end_time must be on or after start_time.")
            frequency = row.get("recurrence_frequency")
            recurrence_values = (
                row.get("recurrence_interval"),
                row.get("recurrence_count"),
                row.get("recurrence_until"),
                row.get("recurrence_rule"),
            )
            if frequency is None and any(value is not None for value in recurrence_values):
                fail("recurrence details require recurrence_frequency.")
            if frequency is not None and row.get("recurrence_interval") is None:
                fail("recurrence_interval is required for recurring events.")
            if row.get("recurrence_rule") is not None and not isinstance(
                row["recurrence_rule"], dict
            ):
                fail("recurrence_rule must be a JSON object.")
            for field in ("recurrence_interval", "recurrence_count"):
                value = row.get(field)
                if value is not None and value <= 0:
                    fail(f"{field} must be greater than zero.")
            recurrence_until = row.get("recurrence_until")
            if (
                recurrence_until is not None
                and row.get("start_time") is not None
                and recurrence_until < row["start_time"]
            ):
                fail("recurrence_until must be on or after start_time.")
        elif table_name == "event_occurrence_exceptions":
            require_choice("action", EVENT_OCCURRENCE_ACTIONS)
        elif table_name == "timelogs":
            require_choice("tracking_method", VALID_TIMELOG_TRACKING_METHODS)
            if row.get("end_time") is not None and row.get("start_time") is not None:
                if row["end_time"] < row["start_time"]:
                    fail("end_time must be on or after start_time.")
            energy = row.get("energy_level")
            if energy is not None and not 1 <= energy <= 5:
                fail("energy_level must be between 1 and 5.")
        elif table_name == "sleep_segments":
            if row.get("start_at") is not None and row.get("end_at") is not None:
                actual_minutes = int((row["end_at"] - row["start_at"]).total_seconds() // 60)
                if not 1 <= actual_minutes <= 48 * 60:
                    fail("sleep interval must be between 1 minute and 48 hours.")
                if row.get("duration_minutes") != actual_minutes:
                    fail("duration_minutes does not match the stored interval.")
        elif table_name == "timelog_templates":
            duration = row.get("default_duration_minutes")
            if duration is not None and not 1 <= duration <= 1440:
                fail("default_duration_minutes must be between 1 and 1440.")
            for field in ("position", "usage_count"):
                value = row.get(field)
                if value is not None and value < 0:
                    fail(f"{field} must be zero or greater.")
        elif table_name == "finance_assets":
            decimal_places = row.get("decimal_places")
            if decimal_places is not None and not 0 <= decimal_places <= 8:
                fail("decimal_places must be between 0 and 8.")
        elif table_name == "finance_rate_snapshot_entries":
            rate = row.get("rate")
            if rate is not None and rate <= 0:
                fail("rate must be greater than zero.")
        elif table_name == "finance_snapshots":
            require_choice("rate_snapshot_policy", FINANCE_RATE_SNAPSHOT_POLICIES)
        elif table_name == "finance_tree_nodes":
            for field in ("depth", "children_count"):
                value = row.get(field)
                if value is not None and value < 0:
                    fail(f"{field} must be zero or greater.")
        elif table_name == "menstrual_days":
            require_choice("flow_amount", MENSTRUAL_FLOW_AMOUNTS)
            if row.get("flow_amount") is not None and row.get("in_period") is not True:
                fail("flow_amount requires in_period to be true.")
            require_string_list("symptoms", maximum_items=20, maximum_length=50)
        elif table_name == "people":
            require_string_list("nicknames")
        elif table_name == "tags":
            require_choice("entity_type", TAG_ENTITY_TYPES)
        elif table_name == "tag_associations":
            require_choice("entity_type", TAG_ENTITY_TYPES)
        elif table_name == "body_measurements":
            weight = row.get("weight_kg")
            if weight is not None and not Decimal("0") < weight <= Decimal("1000"):
                fail("weight_kg must be greater than zero and at most 1000.")
            for field in ("body_fat_percentage", "muscle_percentage", "visceral_fat"):
                value = row.get(field)
                if value is not None and not Decimal("0") <= value <= Decimal("100"):
                    fail(f"{field} must be between 0 and 100.")
            for field in (
                "fat_mass_kg",
                "muscle_mass_kg",
                "body_water_kg",
                "protein_kg",
                "bone_mass_kg",
                "skeletal_muscle_kg",
            ):
                value = row.get(field)
                if value is not None and not Decimal("0") <= value <= Decimal("1000"):
                    fail(f"{field} must be between 0 and 1000.")
    except TypeError as exc:
        fail(f"contains values with incompatible types ({exc}).")


def _sort_self_references(table: Table, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    self_foreign_keys = [
        foreign_key
        for column in (table.c[name] for name in source_table_column_names(table.name))
        for foreign_key in column.foreign_keys
        if foreign_key.column.table is table
    ]
    if not self_foreign_keys or len(table.primary_key.columns) != 1:
        return rows
    primary_key = list(table.primary_key.columns)[0].name
    pending = list(rows)
    pending_ids = {row[primary_key] for row in pending}
    emitted: set[Any] = set()
    ordered: list[dict[str, Any]] = []
    while pending:
        ready = [
            row
            for row in pending
            if all(
                row[foreign_key.parent.name] is None
                or row[foreign_key.parent.name] not in pending_ids
                or row[foreign_key.parent.name] in emitted
                for foreign_key in self_foreign_keys
            )
        ]
        if not ready:
            raise BundleTableError(f"{table.name} contains a circular self-reference.")
        for row in ready:
            ordered.append(row)
            emitted.add(row[primary_key])
            pending.remove(row)
    return ordered


def _validate_snapshot_foreign_keys(prepared: Mapping[str, list[dict[str, Any]]]) -> None:
    key_sets: dict[tuple[str, str], set[Any]] = {}
    for table in source_tables():
        for column in table.primary_key.columns:
            key_sets[(table.name, column.name)] = {row[column.name] for row in prepared[table.name]}
    for table in source_tables():
        for row_number, row in enumerate(prepared[table.name], start=1):
            for column in (table.c[name] for name in source_table_column_names(table.name)):
                for foreign_key in column.foreign_keys:
                    target_table = foreign_key.column.table.name
                    if target_table in DERIVED_TABLE_NAMES:
                        continue
                    value = row[column.name]
                    if (
                        value is not None
                        and value not in key_sets[(target_table, foreign_key.column.name)]
                    ):
                        raise BundleTableError(
                            f"{table.name} row {row_number} field {column.name!r} references "
                            f"missing {target_table}.{foreign_key.column.name}."
                        )

    entity_tables = {
        entity_type: model.__table__.name for entity_type, model in ASSOCIATION_MODEL_MAP.items()
    }
    entity_tables["area"] = "areas"
    entity_ids = {
        entity_type: {row["id"] for row in prepared[table_name]}
        for entity_type, table_name in entity_tables.items()
    }
    for row_number, row in enumerate(prepared["associations"], start=1):
        source_ids = entity_ids.get(row["source_model"])
        target_ids = entity_ids.get(row["target_model"])
        if source_ids is None or row["source_id"] not in source_ids:
            raise BundleTableError(
                f"associations row {row_number} has a missing or invalid source endpoint."
            )
        if target_ids is None or row["target_id"] not in target_ids:
            raise BundleTableError(
                f"associations row {row_number} has a missing or invalid target endpoint."
            )
    for row_number, row in enumerate(prepared["tag_associations"], start=1):
        target_ids = entity_ids.get(row["entity_type"])
        if target_ids is None or row["entity_id"] not in target_ids:
            raise BundleTableError(
                f"tag_associations row {row_number} has a missing or invalid entity endpoint."
            )

    active_defaults = [
        row for row in prepared["finance_trees"] if row["is_default"] and row["deleted_at"] is None
    ]
    if len(active_defaults) > 1:
        raise BundleTableError("finance_trees contains more than one active default tree.")


def _key_predicate(table: Table, row: Mapping[str, Any]) -> Any:
    return and_(*(column == row[column.name] for column in table.primary_key.columns))


async def restore_table_rows(
    session: AsyncSession,
    prepared: Mapping[str, list[dict[str, Any]]],
    *,
    replace_existing: bool,
) -> tuple[int, int]:
    """Insert or primary-key-upsert a prepared, complete source snapshot."""
    created = 0
    updated = 0
    for table in source_tables():
        if (
            not replace_existing
            and table.name == "finance_trees"
            and any(row["is_default"] and row["deleted_at"] is None for row in prepared[table.name])
        ):
            await session.execute(
                update(table)
                .where(table.c.is_default.is_(True), table.c.deleted_at.is_(None))
                .values(is_default=False)
            )
        for row in prepared[table.name]:
            if replace_existing:
                await session.execute(insert(table).values(**row))
                created += 1
                continue
            exists = (
                await session.execute(
                    select(*table.primary_key.columns).where(_key_predicate(table, row))
                )
            ).first()
            if exists is None:
                await session.execute(insert(table).values(**row))
                created += 1
            else:
                await session.execute(update(table).where(_key_predicate(table, row)).values(**row))
                updated += 1
    return created, updated
