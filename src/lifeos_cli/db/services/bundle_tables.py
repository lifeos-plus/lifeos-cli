"""Lossless table snapshots used by database bundle backup and restore."""

from __future__ import annotations

from collections.abc import Mapping
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

DERIVED_TABLE_NAMES = frozenset(
    {
        "aggregated_timelog_stats_groupby_area",
        "daily_timelog_stats_groupby_area",
    }
)


class BundleTableError(RuntimeError):
    """Raised when a lossless table snapshot is invalid."""


def source_tables() -> tuple[Table, ...]:
    """Return all authoritative tables in foreign-key-safe order."""
    return tuple(
        table for table in Base.metadata.sorted_tables if table.name not in DERIVED_TABLE_NAMES
    )


def source_table_names() -> tuple[str, ...]:
    """Return the canonical ordered source-table names."""
    return tuple(table.name for table in source_tables())


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


async def export_table_rows(session: AsyncSession, table: Table) -> list[dict[str, Any]]:
    """Export every row, including soft-deleted rows, deterministically."""
    primary_key = list(table.primary_key.columns)
    statement = select(table)
    if primary_key:
        statement = statement.order_by(*primary_key)
    mappings = (await session.execute(statement)).mappings().all()
    return [
        {column.name: _serialize_value(mapping[column.name]) for column in table.columns}
        for mapping in mappings
    ]


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
            return value
        if isinstance(column_type, Numeric):
            if isinstance(value, bool):
                raise ValueError("must be a decimal number")
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                raise ValueError("must be finite")
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
            if column_type.length is not None and len(value) > column_type.length:
                raise ValueError(f"exceeds the maximum length of {column_type.length}")
            return value
        if isinstance(column_type, JSON):
            return value
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BundleTableError(f"{label} {exc}.") from exc
    return value


def prepare_table_rows(
    raw_tables: Mapping[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Strictly parse a complete source-table snapshot before any database writes."""
    expected_names = set(source_table_names())
    actual_names = set(raw_tables)
    missing = sorted(expected_names - actual_names)
    unknown = sorted(actual_names - expected_names)
    if missing:
        raise BundleTableError("Bundle is missing source tables: " + ", ".join(missing))
    if unknown:
        raise BundleTableError("Bundle contains unknown source tables: " + ", ".join(unknown))

    prepared: dict[str, list[dict[str, Any]]] = {}
    for table in source_tables():
        expected_columns = {column.name for column in table.columns}
        parsed_rows: list[dict[str, Any]] = []
        seen_primary_keys: set[tuple[Any, ...]] = set()
        for row_number, raw_row in enumerate(raw_tables[table.name], start=1):
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
                column.name: _parse_value(
                    table, column, raw_row[column.name], row_number=row_number
                )
                for column in table.columns
            }
            validate_domain_row(table.name, parsed, row_number=row_number)
            key = tuple(parsed[column.name] for column in table.primary_key.columns)
            if not key or any(value is None for value in key):
                raise BundleTableError(f"{table.name} row {row_number} has a null primary key.")
            if key in seen_primary_keys:
                raise BundleTableError(f"{table.name} contains duplicate primary key {key!r}.")
            seen_primary_keys.add(key)
            parsed_rows.append(parsed)
        prepared[table.name] = _sort_self_references(table, parsed_rows)
    _validate_snapshot_foreign_keys(prepared)
    return prepared


def validate_domain_row(
    table_name: str,
    row: Mapping[str, Any],
    *,
    row_number: int,
) -> None:
    """Enforce service-level invariants for rows that bypass domain mutations."""

    def fail(message: str) -> None:
        raise BundleTableError(f"{table_name} row {row_number}: {message}")

    def require_choice(field: str, choices: set[str]) -> None:
        value = row.get(field)
        if value is not None and value not in choices:
            fail(f"{field} must be one of {', '.join(sorted(choices))}; got {value!r}.")

    try:
        if table_name == "habits":
            duration = row.get("duration_days")
            if duration is not None and not 1 <= duration <= 10000:
                fail("duration_days must be between 1 and 10000.")
            require_choice("status", {"active", "completed", "expired", "paused"})
            require_choice("cadence_frequency", {"daily", "monthly", "weekly", "yearly"})
            target = row.get("target_per_cycle")
            if target is not None and target <= 0:
                fail("target_per_cycle must be greater than zero.")
            frequency = row.get("cadence_frequency")
            weekdays = row.get("cadence_weekdays")
            monthdays = row.get("cadence_monthdays")
            if weekdays is not None and (
                not isinstance(weekdays, list)
                or any(
                    day
                    not in {
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    }
                    for day in weekdays
                )
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
            require_choice("status", {"done", "miss", "pending", "skip"})
        elif table_name == "tasks":
            require_choice("status", {"cancelled", "done", "in_progress", "paused", "todo"})
            require_choice("planning_cycle_type", {"7years", "day", "month", "week", "year"})
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
        elif table_name == "visions":
            require_choice("status", {"active", "archived", "fruit"})
            for field in ("stage", "experience_points"):
                value = row.get(field)
                if value is not None and value < 0:
                    fail(f"{field} must be zero or greater.")
            rate = row.get("experience_rate_per_hour")
            if rate is not None and rate <= 0:
                fail("experience_rate_per_hour must be greater than zero.")
        elif table_name == "events":
            require_choice("status", {"cancelled", "completed", "planned"})
            require_choice("event_type", {"appointment", "deadline", "timeblock"})
            require_choice("recurrence_frequency", {"daily", "monthly", "weekly", "yearly"})
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
            for field in ("recurrence_interval", "recurrence_count"):
                value = row.get(field)
                if value is not None and value <= 0:
                    fail(f"{field} must be greater than zero.")
        elif table_name == "timelogs":
            require_choice("tracking_method", {"automatic", "imported", "manual"})
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
        for column in table.columns
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
            for column in table.columns:
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
        "area": "areas",
        "event": "events",
        "habit_action": "habit_actions",
        "note": "notes",
        "person": "people",
        "tag": "tags",
        "task": "tasks",
        "timelog": "timelogs",
        "timelog_template": "timelog_templates",
        "vision": "visions",
    }
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
