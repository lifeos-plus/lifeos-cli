"""Unified data import/export and batch operation helpers."""

from __future__ import annotations

import hashlib
from contextlib import aclosing
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lifeos_cli.application.datetime_utils import (
    format_utc_iso,
    normalize_storage_datetime,
    parse_iso_datetime_input,
)
from lifeos_cli.application.package_metadata import get_installed_package_version
from lifeos_cli.config import get_database_settings, get_preferences_settings
from lifeos_cli.db.base import Base
from lifeos_cli.db.models import (
    AggregatedTimelogStatsGroupByArea,
    Area,
    BodyMeasurement,
    DailyTimelogStatsGroupByArea,
    Event,
    EventOccurrenceException,
    Habit,
    HabitAction,
    Note,
    Person,
    Tag,
    Task,
    Timelog,
    Vision,
)
from lifeos_cli.db.models.association import (
    PERSON_TARGET_MODEL,
)
from lifeos_cli.db.models.menstrual import MenstrualDay, MenstrualFactor, menstrual_day_factors
from lifeos_cli.db.models.sleep_segment import SleepSegment
from lifeos_cli.db.models.tag_association import tag_associations
from lifeos_cli.db.services import (
    areas,
    body_measurements,
    events,
    habit_actions,
    habits,
    notes,
    person,
    tags,
    task_effort,
    tasks,
    timelog_stats,
    timelogs,
    visions,
)
from lifeos_cli.db.services import (
    menstrual as menstrual_services,
)
from lifeos_cli.db.services import (
    sleep as sleep_services,
)
from lifeos_cli.db.services.bundle_codec import (
    MAX_BUNDLE_ENTRY_BYTES,
    MAX_BUNDLE_TOTAL_BYTES,
    BundleArchiveReader,
    BundleCodecError,
    decode_jsonl,
    decode_jsonl_row,
    encode_jsonl_row,
    open_bundle_archive,
    open_bundle_atomic,
)
from lifeos_cli.db.services.bundle_tables import (
    BundleTableError,
    iter_export_table_rows,
    prepare_table_entry_rows,
    restore_table_rows,
    source_table_names,
    source_tables,
    validate_domain_row,
    validate_prepared_tables,
)
from lifeos_cli.db.services.entity_associations import (
    get_target_ids_for_sources,
    set_association_links,
)
from lifeos_cli.db.services.entity_person import sync_entity_person
from lifeos_cli.db.services.entity_tags import sync_entity_tags

SUPPORTED_DATA_RESOURCES = (
    "area",
    "body-measurement",
    "menstrual",
    "menstrual-factor",
    "person",
    "sleep",
    "tag",
    "vision",
    "task",
    "habit",
    "habit-action",
    "event",
    "timelog",
    "note",
)
BUNDLE_RESOURCE_ORDER = SUPPORTED_DATA_RESOURCES
BUNDLE_SCHEMA_VERSION = 4
LEGACY_BUNDLE_SCHEMA_VERSION = 3

# Resource keys used by bundles written before the person resource was
# standardized to singular naming. Old archives stay importable by mapping
# their entry names onto the current resource key; the new consumer surface
# only exposes the current key.
LEGACY_BUNDLE_RESOURCE_KEYS: dict[str, str] = {
    "person": "people",
}

# Single-field natural keys that are safe upsert matchers per resource. The
# field must be effectively unique among active records; resources without a
# safe key stay id-only for idempotent syncs.
NATURAL_KEY_FIELDS_BY_RESOURCE: dict[str, frozenset[str]] = {
    "area": frozenset({"name"}),
    "vision": frozenset({"name"}),
    "person": frozenset({"name"}),
    "habit": frozenset({"title"}),
    "body-measurement": frozenset({"measured_at"}),
    "menstrual": frozenset({"log_date"}),
    "menstrual-factor": frozenset({"name"}),
}


class DataOperationError(RuntimeError):
    """Raised when a data operation cannot continue."""


@dataclass(frozen=True)
class DataOperationFailure:
    """One failed row or identifier during a data operation."""

    index: int | None
    resource: str
    message: str
    payload: dict[str, Any] | None = None
    record_id: UUID | None = None


@dataclass(frozen=True)
class DataImportReport:
    """Summary for a data import operation."""

    resource: str
    processed_count: int
    created_count: int
    updated_count: int
    failed_count: int
    failures: tuple[DataOperationFailure, ...]


@dataclass(frozen=True)
class DataBatchUpdateReport:
    """Summary for a data batch update operation."""

    resource: str
    processed_count: int
    updated_count: int
    failed_count: int
    failures: tuple[DataOperationFailure, ...]


@dataclass(frozen=True)
class DataBatchDeleteReport:
    """Summary for a data batch delete operation."""

    resource: str
    processed_count: int
    deleted_count: int
    failed_count: int
    failures: tuple[DataOperationFailure, ...]


@dataclass(frozen=True)
class BundleExportReport:
    """Summary for a bundle export operation."""

    table_counts: dict[str, int]
    output_path: Path


@dataclass(frozen=True)
class BundleImportReport:
    """Summary for a bundle import operation."""

    processed_count: int
    created_count: int
    updated_count: int
    failed_count: int
    failures: tuple[DataOperationFailure, ...]
    imported_resources: tuple[str, ...]


@dataclass(frozen=True)
class PreparedBundleTables:
    """Typed and fully validated source-table rows ready for atomic restore."""

    rows: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class BundlePayload:
    """Validated manifest and data loaded from one bundle archive."""

    manifest: dict[str, Any]
    resources: dict[str, list[dict[str, Any]]]
    tables: PreparedBundleTables | None = None


@dataclass(frozen=True)
class DataResourceSpec:
    """Snapshot and batch metadata for one resource."""

    resource: str
    model: Any
    tag_entity_type: str | None = None
    person_entity_type: str | None = None
    export_excluded_fields: frozenset[str] = frozenset()


RESOURCE_SPECS: dict[str, DataResourceSpec] = {
    "area": DataResourceSpec(resource="area", model=Area),
    "body-measurement": DataResourceSpec(resource="body-measurement", model=BodyMeasurement),
    "menstrual": DataResourceSpec(resource="menstrual", model=MenstrualDay),
    "menstrual-factor": DataResourceSpec(resource="menstrual-factor", model=MenstrualFactor),
    "person": DataResourceSpec(
        resource="person",
        model=Person,
        tag_entity_type="person",
    ),
    "sleep": DataResourceSpec(resource="sleep", model=SleepSegment),
    "tag": DataResourceSpec(
        resource="tag",
        model=Tag,
        person_entity_type="tag",
    ),
    "vision": DataResourceSpec(
        resource="vision",
        model=Vision,
        person_entity_type="vision",
    ),
    "task": DataResourceSpec(
        resource="task",
        model=Task,
        person_entity_type="task",
        export_excluded_fields=frozenset({"actual_effort_self", "actual_effort_total"}),
    ),
    "habit": DataResourceSpec(resource="habit", model=Habit),
    "habit-action": DataResourceSpec(resource="habit-action", model=HabitAction),
    "event": DataResourceSpec(
        resource="event",
        model=Event,
        tag_entity_type="event",
        person_entity_type="event",
    ),
    "timelog": DataResourceSpec(
        resource="timelog",
        model=Timelog,
        tag_entity_type="timelog",
        person_entity_type="timelog",
    ),
    "note": DataResourceSpec(resource="note", model=Note, tag_entity_type="note"),
}

DELETE_ARG_NAMES: dict[str, str] = {
    "area": "area_ids",
    "body-measurement": "measurement_ids",
    "menstrual": "day_ids",
    "menstrual-factor": "factor_ids",
    "person": "person_ids",
    "sleep": "segment_ids",
    "tag": "tag_ids",
    "vision": "vision_ids",
    "task": "task_ids",
    "habit": "habit_ids",
    "event": "event_ids",
    "timelog": "timelog_ids",
    "note": "note_ids",
}


def _normalize_json_datetime(value: str) -> datetime:
    parsed = parse_iso_datetime_input(value)
    return normalize_storage_datetime(parsed)


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return format_utc_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _parse_column_value(column: Any, value: Any) -> Any:
    if value is None:
        return None
    python_type = getattr(column.type, "python_type", None)
    if python_type is UUID:
        if not isinstance(value, (UUID, str)):
            raise DataOperationError(f"Value for `{column.name}` must be a UUID string.")
        return value if isinstance(value, UUID) else UUID(value)
    if python_type is datetime:
        if not isinstance(value, (datetime, str)):
            raise DataOperationError(
                f"Value for `{column.name}` must be an ISO-8601 datetime string."
            )
        return (
            normalize_storage_datetime(value)
            if isinstance(value, datetime)
            else _normalize_json_datetime(value)
        )
    if python_type is date:
        if isinstance(value, datetime) or not isinstance(value, (date, str)):
            raise DataOperationError(f"Value for `{column.name}` must be an ISO date string.")
        return value if isinstance(value, date) else date.fromisoformat(value)
    if python_type is bool:
        if type(value) is not bool:
            raise DataOperationError(f"Value for `{column.name}` must be a boolean.")
        return value
    if python_type is int:
        if type(value) is not int:
            raise DataOperationError(f"Value for `{column.name}` must be an integer.")
        return value
    if python_type is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DataOperationError(f"Value for `{column.name}` must be a number.")
        return float(value)
    if python_type is Decimal:
        try:
            decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise DataOperationError(f"Invalid decimal value for `{column.name}`.") from exc
        if not decimal_value.is_finite():
            raise DataOperationError(f"Decimal value for `{column.name}` must be finite.")
        return decimal_value
    if python_type is str:
        if not isinstance(value, str):
            raise DataOperationError(f"Value for `{column.name}` must be a string.")
        if column.type.length is not None and len(value) > column.type.length:
            raise DataOperationError(
                f"Value for `{column.name}` exceeds the maximum length of {column.type.length}."
            )
        return value
    return value


def _model_column_names(spec: DataResourceSpec) -> tuple[str, ...]:
    return tuple(
        column.name
        for column in spec.model.__table__.columns
        if column.name not in spec.export_excluded_fields
    )


def _serialize_model_row(spec: DataResourceSpec, row: Any) -> dict[str, Any]:
    payload = {
        column_name: _serialize_scalar(getattr(row, column_name))
        for column_name in _model_column_names(spec)
    }
    return payload


def _build_order_by_columns(spec: DataResourceSpec) -> tuple[Any, ...]:
    table = spec.model.__table__
    columns: list[Any] = []
    if "created_at" in table.c:
        columns.append(table.c.created_at.asc())
    columns.append(table.c.id.asc())
    return tuple(columns)


def _parse_uuid_array(value: Any, *, field_name: str) -> list[UUID]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DataOperationError(f"Expected `{field_name}` to be a JSON array.")
    return [item if isinstance(item, UUID) else UUID(str(item)) for item in value]


def _parse_event_occurrence_exceptions(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DataOperationError("Expected `occurrence_exceptions` to be a JSON array.")
    parsed: list[dict[str, Any]] = []
    expected_fields = {"id", "action", "instance_start", "created_at", "updated_at", "deleted_at"}
    seen_ids: set[UUID] = set()
    seen_active_instances: set[datetime] = set()
    for item_number, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise DataOperationError("Each event occurrence exception must be a JSON object.")
        actual_fields = set(item)
        if actual_fields != expected_fields:
            missing = sorted(expected_fields - actual_fields)
            unknown = sorted(actual_fields - expected_fields)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if unknown:
                details.append("unknown " + ", ".join(unknown))
            raise DataOperationError(
                f"Event occurrence exception {item_number} has an invalid shape "
                f"({'; '.join(details)})."
            )
        for field in ("id", "action", "instance_start", "created_at", "updated_at"):
            if not isinstance(item[field], str):
                raise DataOperationError(
                    f"Event occurrence exception {item_number} field `{field}` must be a string."
                )
        if item["deleted_at"] is not None and not isinstance(item["deleted_at"], str):
            raise DataOperationError(
                f"Event occurrence exception {item_number} field `deleted_at` "
                "must be a string or null."
            )
        if item["action"] != "skip":
            raise DataOperationError(
                f"Event occurrence exception {item_number} action must be `skip`."
            )
        exception_id = UUID(item["id"])
        instance_start = _normalize_json_datetime(item["instance_start"])
        deleted_at = (
            None if item["deleted_at"] is None else _normalize_json_datetime(item["deleted_at"])
        )
        if exception_id in seen_ids:
            raise DataOperationError("Event occurrence exception ids must be unique per event.")
        if deleted_at is None and instance_start in seen_active_instances:
            raise DataOperationError(
                "Active event occurrence instance timestamps must be unique per event."
            )
        seen_ids.add(exception_id)
        if deleted_at is None:
            seen_active_instances.add(instance_start)
        parsed.append(
            {
                "id": exception_id,
                "action": item["action"],
                "instance_start": instance_start,
                "created_at": _normalize_json_datetime(item["created_at"]),
                "updated_at": _normalize_json_datetime(item["updated_at"]),
                "deleted_at": deleted_at,
            }
        )
    return parsed


@dataclass(frozen=True)
class PreparedSnapshotRow:
    """Prepared snapshot payload with direct fields and relation extras."""

    resource: str
    index: int
    row_id: UUID
    direct_values: dict[str, Any]
    factor_names: list[str] | None = None
    tag_ids: list[UUID] | None = None
    person_ids: list[UUID] | None = None
    note_task_ids: list[UUID] | None = None
    note_vision_ids: list[UUID] | None = None
    note_event_ids: list[UUID] | None = None
    note_timelog_ids: list[UUID] | None = None
    note_habit_action_ids: list[UUID] | None = None
    occurrence_exceptions: list[dict[str, Any]] | None = None


def _parse_string_array(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DataOperationError(f"Expected `{field_name}` to be a JSON array.")
    if any(not isinstance(item, str) for item in value):
        raise DataOperationError(f"Every `{field_name}` value must be a string.")
    return list(value)


def prepare_snapshot_row(resource: str, index: int, payload: dict[str, Any]) -> PreparedSnapshotRow:
    """Normalize one imported snapshot row for persistence."""
    if resource not in RESOURCE_SPECS:
        raise DataOperationError(f"Unsupported data resource {resource!r}.")
    spec = RESOURCE_SPECS[resource]
    table = spec.model.__table__
    allowed_fields = set(_model_column_names(spec))
    if spec.tag_entity_type:
        allowed_fields.add("tag_ids")
    if spec.person_entity_type or resource == "note":
        allowed_fields.add("person_ids")
    if resource == "note":
        allowed_fields.update(
            {
                "task_ids",
                "vision_ids",
                "event_ids",
                "timelog_ids",
                "habit_action_ids",
            }
        )
    if resource == "event":
        allowed_fields.add("occurrence_exceptions")
    if resource == "menstrual":
        allowed_fields.add("factor_names")
    unknown_fields = sorted(set(payload) - allowed_fields)
    if unknown_fields:
        raise DataOperationError(
            f"{resource} row {index} contains unknown fields: {', '.join(unknown_fields)}."
        )
    direct_values: dict[str, Any] = {}
    for column_name in _model_column_names(spec):
        if column_name not in payload:
            continue
        column = table.c[column_name]
        direct_values[column_name] = _parse_column_value(column, payload[column_name])
    try:
        validate_domain_row(table.name, direct_values, row_number=index)
    except BundleTableError as exc:
        raise DataOperationError(str(exc)) from exc
    if "id" not in direct_values:
        raise DataOperationError("Each imported row must include `id`.")
    row_id = direct_values["id"]
    if not isinstance(row_id, UUID):
        raise DataOperationError("Each imported row `id` must be a UUID.")
    tag_ids = (
        _parse_uuid_array(payload["tag_ids"], field_name="tag_ids")
        if spec.tag_entity_type and "tag_ids" in payload
        else None
    )
    person_ids = (
        _parse_uuid_array(payload["person_ids"], field_name="person_ids")
        if (spec.person_entity_type and "person_ids" in payload)
        or (resource == "note" and "person_ids" in payload)
        else None
    )
    note_task_ids = (
        _parse_uuid_array(payload["task_ids"], field_name="task_ids")
        if resource == "note" and "task_ids" in payload
        else None
    )
    note_vision_ids = (
        _parse_uuid_array(payload["vision_ids"], field_name="vision_ids")
        if resource == "note" and "vision_ids" in payload
        else None
    )
    note_event_ids = (
        _parse_uuid_array(payload["event_ids"], field_name="event_ids")
        if resource == "note" and "event_ids" in payload
        else None
    )
    note_timelog_ids = (
        _parse_uuid_array(payload["timelog_ids"], field_name="timelog_ids")
        if resource == "note" and "timelog_ids" in payload
        else None
    )
    note_habit_action_ids = (
        _parse_uuid_array(payload["habit_action_ids"], field_name="habit_action_ids")
        if resource == "note" and "habit_action_ids" in payload
        else None
    )
    occurrence_exceptions = (
        _parse_event_occurrence_exceptions(payload["occurrence_exceptions"])
        if resource == "event" and "occurrence_exceptions" in payload
        else None
    )
    factor_names = (
        _parse_string_array(payload["factor_names"], field_name="factor_names")
        if resource == "menstrual" and "factor_names" in payload
        else None
    )
    return PreparedSnapshotRow(
        resource=resource,
        index=index,
        row_id=row_id,
        direct_values=direct_values,
        factor_names=factor_names,
        tag_ids=tag_ids,
        person_ids=person_ids,
        note_task_ids=note_task_ids,
        note_vision_ids=note_vision_ids,
        note_event_ids=note_event_ids,
        note_timelog_ids=note_timelog_ids,
        note_habit_action_ids=note_habit_action_ids,
        occurrence_exceptions=occurrence_exceptions,
    )


def validate_upsert_key(resource: str, key_field: str) -> None:
    """Validate that one resource supports natural-key upsert for a field."""
    allowed_fields = NATURAL_KEY_FIELDS_BY_RESOURCE.get(resource, frozenset())
    if key_field not in allowed_fields:
        allowed_text = ", ".join(sorted(allowed_fields)) or "none"
        raise DataOperationError(
            f"Natural-key upsert is not supported for {resource!r} field "
            f"{key_field!r}; supported keys: {allowed_text}."
        )


async def find_upsert_match_id(
    session: AsyncSession,
    *,
    resource: str,
    row: dict[str, Any],
    key_field: str,
    index: int,
) -> UUID | None:
    """Return the sole active row matching one import natural key, if present."""
    validate_upsert_key(resource, key_field)
    raw_key_value = row.get(key_field)
    if raw_key_value is None or str(raw_key_value).strip() == "":
        raise DataOperationError(f"Row {index} is missing a value for upsert key `{key_field}`.")
    spec = RESOURCE_SPECS[resource]
    table = spec.model.__table__
    column = table.c[key_field]
    key_value = _parse_column_value(column, raw_key_value)
    filters = [column == key_value]
    if "deleted_at" in table.c:
        filters.append(table.c.deleted_at.is_(None))
    matches = (await session.execute(select(table.c.id).where(*filters))).scalars().all()
    if len(matches) > 1:
        raise DataOperationError(
            f"Row {index} upsert key `{key_field}` is ambiguous: "
            f"{len(matches)} active records match."
        )
    return matches[0] if matches else None


async def resolve_upsert_row_id(
    session: AsyncSession,
    *,
    resource: str,
    row: dict[str, Any],
    key_field: str,
    index: int,
) -> dict[str, Any]:
    """Resolve one import row's id from its natural key.

    Returns the row with the matching active record's id injected when one
    exists, a fresh UUID when no match exists and the row has no id, or the
    row unchanged when a match exists and the row already carries the same id.
    """
    match_id = await find_upsert_match_id(
        session,
        resource=resource,
        row=row,
        key_field=key_field,
        index=index,
    )
    if match_id is not None:
        return {**row, "id": str(match_id)}
    if "id" not in row or row["id"] is None or str(row["id"]).strip() == "":
        return {**row, "id": str(uuid4())}
    return row


async def _load_related_ids_for_entities(
    session: AsyncSession,
    *,
    association_table: Any,
    related_id_column: Any,
    entity_type: str,
    entity_ids: list[UUID],
) -> dict[UUID, list[UUID]]:
    if not entity_ids:
        return {}
    stmt = select(association_table.c.entity_id, related_id_column).where(
        association_table.c.entity_type == entity_type,
        association_table.c.entity_id.in_(entity_ids),
    )
    rows = (await session.execute(stmt)).all()
    mapping: dict[UUID, list[UUID]] = {entity_id: [] for entity_id in entity_ids}
    for entity_id, related_id in rows:
        mapping[entity_id].append(related_id)
    return mapping


async def _load_event_occurrence_exceptions(
    session: AsyncSession,
    *,
    event_ids: list[UUID],
) -> dict[UUID, list[dict[str, Any]]]:
    if not event_ids:
        return {}
    stmt = (
        select(EventOccurrenceException)
        .where(EventOccurrenceException.master_event_id.in_(event_ids))
        .order_by(EventOccurrenceException.instance_start.asc(), EventOccurrenceException.id.asc())
    )
    rows = list((await session.execute(stmt)).scalars())
    mapping: dict[UUID, list[dict[str, Any]]] = {event_id: [] for event_id in event_ids}
    for row in rows:
        mapping[row.master_event_id].append(
            {
                "id": str(row.id),
                "action": row.action,
                "instance_start": row.instance_start.isoformat(),
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
                "deleted_at": None if row.deleted_at is None else row.deleted_at.isoformat(),
            }
        )
    return mapping


async def _load_menstrual_factor_names(
    session: AsyncSession,
    *,
    day_ids: list[UUID],
) -> dict[UUID, list[str]]:
    """Load active factor names per menstrual day in stable name order."""
    if not day_ids:
        return {}
    stmt = (
        select(menstrual_day_factors.c.menstrual_day_id, MenstrualFactor.name)
        .join(MenstrualFactor, MenstrualFactor.id == menstrual_day_factors.c.factor_id)
        .where(
            menstrual_day_factors.c.menstrual_day_id.in_(day_ids),
            MenstrualFactor.deleted_at.is_(None),
        )
        .order_by(MenstrualFactor.name.asc())
    )
    rows = (await session.execute(stmt)).all()
    mapping: dict[UUID, list[str]] = {day_id: [] for day_id in day_ids}
    for day_id, name in rows:
        mapping[day_id].append(name)
    return mapping


async def export_resource_snapshot(
    session: AsyncSession,
    *,
    resource: str,
) -> list[dict[str, Any]]:
    """Export one resource into canonical snapshot rows."""
    if resource not in RESOURCE_SPECS:
        raise DataOperationError(f"Unsupported data resource {resource!r}.")
    spec = RESOURCE_SPECS[resource]
    stmt = select(spec.model)
    if "deleted_at" in spec.model.__table__.c:
        stmt = stmt.where(spec.model.deleted_at.is_(None))
    stmt = stmt.order_by(*_build_order_by_columns(spec))
    rows = list((await session.execute(stmt)).scalars())
    payloads = [_serialize_model_row(spec, row) for row in rows]

    entity_ids = [UUID(payload["id"]) for payload in payloads]
    tag_map = (
        await _load_related_ids_for_entities(
            session,
            association_table=tag_associations,
            related_id_column=tag_associations.c.tag_id,
            entity_type=spec.tag_entity_type,
            entity_ids=entity_ids,
        )
        if spec.tag_entity_type
        else {}
    )
    person_map = (
        await get_target_ids_for_sources(
            session,
            source_model=spec.person_entity_type,
            source_ids=entity_ids,
            target_model=PERSON_TARGET_MODEL,
        )
        if spec.person_entity_type
        else {}
    )
    occurrence_map = (
        await _load_event_occurrence_exceptions(session, event_ids=entity_ids)
        if resource == "event"
        else {}
    )
    note_task_map = (
        await get_target_ids_for_sources(
            session,
            source_model="note",
            source_ids=entity_ids,
            target_model="task",
            link_type="relates_to",
        )
        if resource == "note"
        else {}
    )
    note_vision_map = (
        await get_target_ids_for_sources(
            session,
            source_model="note",
            source_ids=entity_ids,
            target_model="vision",
            link_type="relates_to",
        )
        if resource == "note"
        else {}
    )
    note_event_map = (
        await get_target_ids_for_sources(
            session,
            source_model="note",
            source_ids=entity_ids,
            target_model="event",
            link_type="relates_to",
        )
        if resource == "note"
        else {}
    )
    note_person_map = (
        await get_target_ids_for_sources(
            session,
            source_model="note",
            source_ids=entity_ids,
            target_model="person",
        )
        if resource == "note"
        else {}
    )
    note_timelog_map = (
        await get_target_ids_for_sources(
            session,
            source_model="note",
            source_ids=entity_ids,
            target_model="timelog",
            link_type="captured_from",
        )
        if resource == "note"
        else {}
    )
    note_habit_action_map = (
        await get_target_ids_for_sources(
            session,
            source_model="note",
            source_ids=entity_ids,
            target_model="habit_action",
            link_type="captured_from",
        )
        if resource == "note"
        else {}
    )
    menstrual_factor_map = (
        await _load_menstrual_factor_names(session, day_ids=entity_ids)
        if resource == "menstrual"
        else {}
    )

    for payload in payloads:
        entity_id = UUID(str(payload["id"]))
        if resource == "menstrual":
            payload["factor_names"] = menstrual_factor_map.get(entity_id, [])
        if spec.tag_entity_type:
            payload["tag_ids"] = [str(tag_id) for tag_id in tag_map.get(entity_id, [])]
        if spec.person_entity_type:
            payload["person_ids"] = [str(person_id) for person_id in person_map.get(entity_id, [])]
        if resource == "event":
            payload["occurrence_exceptions"] = occurrence_map.get(entity_id, [])
        if resource == "note":
            payload["tag_ids"] = [str(tag_id) for tag_id in tag_map.get(entity_id, [])]
            payload["person_ids"] = [
                str(person_id) for person_id in note_person_map.get(entity_id, [])
            ]
            payload["task_ids"] = [str(task_id) for task_id in note_task_map.get(entity_id, [])]
            payload["vision_ids"] = [
                str(vision_id) for vision_id in note_vision_map.get(entity_id, [])
            ]
            payload["event_ids"] = [str(event_id) for event_id in note_event_map.get(entity_id, [])]
            payload["timelog_ids"] = [
                str(timelog_id) for timelog_id in note_timelog_map.get(entity_id, [])
            ]
            payload["habit_action_ids"] = [
                str(action_id) for action_id in note_habit_action_map.get(entity_id, [])
            ]
    return payloads


async def _apply_snapshot_base_row(
    session: AsyncSession,
    *,
    prepared_row: PreparedSnapshotRow,
) -> str:
    spec = RESOURCE_SPECS[prepared_row.resource]
    update_stmt = (
        update(spec.model)
        .where(spec.model.id == prepared_row.row_id)
        .values(**prepared_row.direct_values)
    )
    result = await session.execute(update_stmt)
    updated_count = int(getattr(result, "rowcount", 0) or 0)
    if updated_count > 0:
        return "updated"
    await session.execute(insert(spec.model).values(**prepared_row.direct_values))
    return "created"


async def _sync_snapshot_relations(
    session: AsyncSession,
    *,
    prepared_row: PreparedSnapshotRow,
) -> None:
    spec = RESOURCE_SPECS[prepared_row.resource]
    if prepared_row.resource == "menstrual" and prepared_row.factor_names is not None:
        await _sync_menstrual_factors(
            session,
            day_id=prepared_row.row_id,
            factor_names=prepared_row.factor_names,
        )
    if spec.tag_entity_type is not None and prepared_row.tag_ids is not None:
        await sync_entity_tags(
            session,
            entity_id=prepared_row.row_id,
            entity_type=spec.tag_entity_type,
            desired_tag_ids=prepared_row.tag_ids,
        )
    if spec.person_entity_type is not None and prepared_row.person_ids is not None:
        await sync_entity_person(
            session,
            entity_id=prepared_row.row_id,
            entity_type=spec.person_entity_type,
            desired_person_ids=prepared_row.person_ids,
        )
    if prepared_row.resource == "note":
        if prepared_row.tag_ids is not None:
            await sync_entity_tags(
                session,
                entity_id=prepared_row.row_id,
                entity_type="note",
                desired_tag_ids=prepared_row.tag_ids,
            )
        if prepared_row.person_ids is not None:
            await set_association_links(
                session,
                source_model="note",
                source_id=prepared_row.row_id,
                target_model="person",
                target_ids=prepared_row.person_ids,
                link_type="is_about",
            )
        if prepared_row.note_task_ids is not None:
            await set_association_links(
                session,
                source_model="note",
                source_id=prepared_row.row_id,
                target_model="task",
                target_ids=prepared_row.note_task_ids,
                link_type="relates_to",
            )
        if prepared_row.note_vision_ids is not None:
            await set_association_links(
                session,
                source_model="note",
                source_id=prepared_row.row_id,
                target_model="vision",
                target_ids=prepared_row.note_vision_ids,
                link_type="relates_to",
            )
        if prepared_row.note_event_ids is not None:
            await set_association_links(
                session,
                source_model="note",
                source_id=prepared_row.row_id,
                target_model="event",
                target_ids=prepared_row.note_event_ids,
                link_type="relates_to",
            )
        if prepared_row.note_timelog_ids is not None:
            await set_association_links(
                session,
                source_model="note",
                source_id=prepared_row.row_id,
                target_model="timelog",
                target_ids=prepared_row.note_timelog_ids,
                link_type="captured_from",
            )
        if prepared_row.note_habit_action_ids is not None:
            await set_association_links(
                session,
                source_model="note",
                source_id=prepared_row.row_id,
                target_model="habit_action",
                target_ids=prepared_row.note_habit_action_ids,
                link_type="captured_from",
            )
    if prepared_row.resource == "event" and prepared_row.occurrence_exceptions is not None:
        await session.execute(
            delete(EventOccurrenceException).where(
                EventOccurrenceException.master_event_id == prepared_row.row_id
            )
        )
        if prepared_row.occurrence_exceptions:
            await session.execute(
                insert(EventOccurrenceException),
                [
                    {
                        **exception_payload,
                        "master_event_id": prepared_row.row_id,
                    }
                    for exception_payload in prepared_row.occurrence_exceptions
                ],
            )


async def _sync_menstrual_factors(
    session: AsyncSession,
    *,
    day_id: UUID,
    factor_names: list[str],
) -> None:
    """Replace a menstrual day's factor links by active factor name."""
    names = list(dict.fromkeys(factor_names))
    factor_rows = list(
        (
            await session.execute(
                select(MenstrualFactor.id, MenstrualFactor.name).where(
                    MenstrualFactor.name.in_(names),
                    MenstrualFactor.deleted_at.is_(None),
                )
            )
        ).all()
    )
    factor_id_by_name = {name: factor_id for factor_id, name in factor_rows}
    missing = [name for name in names if name not in factor_id_by_name]
    if missing:
        raise DataOperationError(
            "Menstrual factor names must already exist for imported rows: " + ", ".join(missing)
        )
    factor_ids = [factor_id_by_name[name] for name in names]
    await session.execute(
        delete(menstrual_day_factors).where(menstrual_day_factors.c.menstrual_day_id == day_id)
    )
    if factor_ids:
        await session.execute(
            insert(menstrual_day_factors),
            [{"menstrual_day_id": day_id, "factor_id": factor_id} for factor_id in factor_ids],
        )


async def _import_prepared_base_rows(
    session: AsyncSession,
    *,
    prepared_rows: list[PreparedSnapshotRow],
) -> tuple[int, int]:
    created_count = 0
    updated_count = 0
    for prepared_row in prepared_rows:
        outcome = await _apply_snapshot_base_row(session, prepared_row=prepared_row)
        if outcome == "created":
            created_count += 1
        else:
            updated_count += 1
    return created_count, updated_count


async def _sync_prepared_rows_relations(
    session: AsyncSession,
    *,
    prepared_rows: list[PreparedSnapshotRow],
) -> None:
    for prepared_row in prepared_rows:
        await _sync_snapshot_relations(session, prepared_row=prepared_row)


async def import_resource_snapshot(
    session: AsyncSession,
    *,
    resource: str,
    rows: list[dict[str, Any]],
) -> DataImportReport:
    """Import canonical snapshot rows for one resource."""
    prepared_rows = [
        prepare_snapshot_row(resource, index + 1, row) for index, row in enumerate(rows)
    ]
    created_count, updated_count = await _import_prepared_base_rows(
        session,
        prepared_rows=prepared_rows,
    )
    await _sync_prepared_rows_relations(session, prepared_rows=prepared_rows)
    return DataImportReport(
        resource=resource,
        processed_count=len(rows),
        created_count=created_count,
        updated_count=updated_count,
        failed_count=0,
        failures=(),
    )


def _normalize_patch_payload(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    if resource not in RESOURCE_SPECS:
        raise DataOperationError(f"Unsupported data resource {resource!r}.")
    spec = RESOURCE_SPECS[resource]
    table = spec.model.__table__
    normalized: dict[str, Any] = {}
    for field, value in payload.items():
        if field in table.c:
            normalized[field] = _parse_column_value(table.c[field], value)
            continue
        if field == "tag_ids":
            normalized[field] = (
                None if value is None else _parse_uuid_array(value, field_name=field)
            )
            continue
        if field == "person_ids":
            normalized[field] = (
                None if value is None else _parse_uuid_array(value, field_name=field)
            )
            continue
        if field in {"task_ids", "vision_ids", "event_ids"} and resource == "note":
            normalized[field] = (
                None if value is None else _parse_uuid_array(value, field_name=field)
            )
            continue
        if field in {"timelog_ids", "habit_action_ids"} and resource == "note":
            normalized[field] = (
                None if value is None else _parse_uuid_array(value, field_name=field)
            )
            continue
        normalized[field] = value
    return normalized


def _null_means_clear(
    payload: dict[str, Any],
    *,
    field: str,
    target_field: str | None = None,
    clear_flag: str,
) -> dict[str, Any]:
    if field not in payload:
        return {}
    if payload[field] is None:
        return {clear_flag: True}
    return {target_field or field: payload[field]}


def _batch_update_area_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"area_id": UUID(str(payload["id"]))}
    if "name" in payload:
        kwargs["name"] = payload["name"]
    kwargs.update(_null_means_clear(payload, field="description", clear_flag="clear_description"))
    if "color" in payload:
        kwargs["color"] = payload["color"]
    kwargs.update(_null_means_clear(payload, field="icon", clear_flag="clear_icon"))
    if "is_active" in payload:
        kwargs["is_active"] = payload["is_active"]
    if "display_order" in payload:
        kwargs["display_order"] = payload["display_order"]
    return kwargs


def _batch_update_person_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"person_id": UUID(str(payload["id"]))}
    if "name" in payload:
        kwargs["name"] = payload["name"]
    kwargs.update(_null_means_clear(payload, field="description", clear_flag="clear_description"))
    kwargs.update(_null_means_clear(payload, field="nicknames", clear_flag="clear_nicknames"))
    kwargs.update(_null_means_clear(payload, field="birth_date", clear_flag="clear_birth_date"))
    kwargs.update(_null_means_clear(payload, field="location", clear_flag="clear_location"))
    kwargs.update(_null_means_clear(payload, field="tag_ids", clear_flag="clear_tags"))
    return kwargs


def _batch_update_tag_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"tag_id": UUID(str(payload["id"]))}
    for field in ("name", "entity_type", "category"):
        if field in payload:
            kwargs[field] = payload[field]
    kwargs.update(_null_means_clear(payload, field="description", clear_flag="clear_description"))
    kwargs.update(_null_means_clear(payload, field="color", clear_flag="clear_color"))
    kwargs.update(_null_means_clear(payload, field="person_ids", clear_flag="clear_person"))
    return kwargs


def _batch_update_vision_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"vision_id": UUID(str(payload["id"]))}
    for field in ("name", "status"):
        if field in payload:
            kwargs[field] = payload[field]
    kwargs.update(_null_means_clear(payload, field="description", clear_flag="clear_description"))
    kwargs.update(_null_means_clear(payload, field="area_id", clear_flag="clear_area"))
    kwargs.update(
        _null_means_clear(
            payload,
            field="experience_rate_per_hour",
            clear_flag="clear_experience_rate",
        )
    )
    kwargs.update(_null_means_clear(payload, field="person_ids", clear_flag="clear_person"))
    return kwargs


def _batch_update_task_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"task_id": UUID(str(payload["id"]))}
    for field in ("content", "status", "priority", "display_order"):
        if field in payload:
            kwargs[field] = payload[field]
    kwargs.update(_null_means_clear(payload, field="description", clear_flag="clear_description"))
    kwargs.update(_null_means_clear(payload, field="parent_task_id", clear_flag="clear_parent"))
    kwargs.update(
        _null_means_clear(
            payload,
            field="estimated_effort",
            clear_flag="clear_estimated_effort",
        )
    )
    if "planning_cycle_type" in payload and payload["planning_cycle_type"] is None:
        kwargs["clear_planning_cycle"] = True
    else:
        for field in ("planning_cycle_type", "planning_cycle_days", "planning_cycle_start_date"):
            if field in payload:
                kwargs[field] = payload[field]
    kwargs.update(_null_means_clear(payload, field="person_ids", clear_flag="clear_person"))
    return kwargs


def _batch_update_habit_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"habit_id": UUID(str(payload["id"]))}
    for field in (
        "title",
        "start_date",
        "duration_days",
        "end_date",
        "repeat_count",
        "cadence_frequency",
        "cadence_weekdays",
        "cadence_monthdays",
        "target_per_cycle",
        "status",
    ):
        if field in payload:
            kwargs[field] = payload[field]
    kwargs.update(_null_means_clear(payload, field="description", clear_flag="clear_description"))
    kwargs.update(_null_means_clear(payload, field="task_id", clear_flag="clear_task"))
    if "cadence_weekdays" in payload and payload["cadence_weekdays"] is None:
        kwargs["clear_weekdays"] = True
    if "cadence_monthdays" in payload and payload["cadence_monthdays"] is None:
        kwargs["clear_monthdays"] = True
    return kwargs


def _batch_update_habit_action_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"action_id": UUID(str(payload["id"]))}
    if "status" in payload:
        kwargs["status"] = payload["status"]
    kwargs.update(_null_means_clear(payload, field="notes", clear_flag="clear_notes"))
    return kwargs


def _batch_update_event_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    change_kwargs: dict[str, Any] = {}
    for field in (
        "title",
        "start_time",
        "priority",
        "status",
        "is_all_day",
        "recurrence_frequency",
        "recurrence_interval",
        "recurrence_count",
        "recurrence_until",
        "recurrence_rule",
    ):
        if field in payload and payload[field] is not None:
            change_kwargs[field] = payload[field]
    change_kwargs.update(
        _null_means_clear(payload, field="description", clear_flag="clear_description")
    )
    change_kwargs.update(_null_means_clear(payload, field="end_time", clear_flag="clear_end_time"))
    change_kwargs.update(_null_means_clear(payload, field="area_id", clear_flag="clear_area"))
    change_kwargs.update(_null_means_clear(payload, field="task_id", clear_flag="clear_task"))
    change_kwargs.update(_null_means_clear(payload, field="tag_ids", clear_flag="clear_tags"))
    change_kwargs.update(_null_means_clear(payload, field="person_ids", clear_flag="clear_person"))
    if "recurrence_frequency" in payload and payload["recurrence_frequency"] is None:
        change_kwargs["clear_recurrence"] = True
    if "recurrence_rule" in payload and payload["recurrence_rule"] is None:
        change_kwargs["clear_recurrence_rule"] = True
    return {
        "event_id": UUID(str(payload["id"])),
        "changes": events.EventUpdateInput(**change_kwargs),
    }


def _batch_update_timelog_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    change_kwargs: dict[str, Any] = {}
    for field in ("title", "start_time", "end_time", "tracking_method"):
        if field in payload:
            change_kwargs[field] = payload[field]
    change_kwargs.update(_null_means_clear(payload, field="location", clear_flag="clear_location"))
    change_kwargs.update(
        _null_means_clear(payload, field="energy_level", clear_flag="clear_energy_level")
    )
    change_kwargs.update(_null_means_clear(payload, field="notes", clear_flag="clear_notes"))
    change_kwargs.update(_null_means_clear(payload, field="area_id", clear_flag="clear_area"))
    change_kwargs.update(_null_means_clear(payload, field="task_id", clear_flag="clear_task"))
    change_kwargs.update(_null_means_clear(payload, field="tag_ids", clear_flag="clear_tags"))
    change_kwargs.update(_null_means_clear(payload, field="person_ids", clear_flag="clear_person"))
    return {
        "timelog_id": UUID(str(payload["id"])),
        "changes": timelogs.TimelogUpdateInput(**change_kwargs),
    }


def _batch_update_note_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"note_id": UUID(str(payload["id"]))}
    if "content" in payload:
        if payload["content"] is None:
            raise DataOperationError("Note batch update does not allow null `content`.")
        kwargs["content"] = payload["content"]
    kwargs.update(_null_means_clear(payload, field="tag_ids", clear_flag="clear_tags"))
    kwargs.update(_null_means_clear(payload, field="person_ids", clear_flag="clear_person"))
    if "task_ids" in payload:
        kwargs.update(_null_means_clear(payload, field="task_ids", clear_flag="clear_tasks"))
    kwargs.update(_null_means_clear(payload, field="vision_ids", clear_flag="clear_visions"))
    kwargs.update(_null_means_clear(payload, field="event_ids", clear_flag="clear_events"))
    kwargs.update(_null_means_clear(payload, field="timelog_ids", clear_flag="clear_timelogs"))
    kwargs.update(
        _null_means_clear(
            payload,
            field="habit_action_ids",
            clear_flag="clear_habit_actions",
        )
    )
    if len(kwargs) == 1:
        raise DataOperationError(
            "Note batch update requires at least one of `content`, `tag_ids`, `person_ids`, "
            "`task_ids`, `vision_ids`, `event_ids`, `timelog_ids`, or `habit_action_ids`."
        )
    return kwargs


BODY_MEASUREMENT_METRIC_FIELDS = (
    "body_fat_percentage",
    "visceral_fat",
    "fat_mass_kg",
    "muscle_percentage",
    "muscle_mass_kg",
    "body_water_kg",
    "protein_kg",
    "bone_mass_kg",
    "skeletal_muscle_kg",
)


def _batch_update_body_measurement_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Map canonical body-measurement patch rows onto the domain update input.

    Canonical rows carry storage-unit values (``weight_kg``), so ``weight``
    is always applied as kilograms regardless of any ``unit`` field.
    """
    update_kwargs: dict[str, Any] = {}
    if "measured_at" in payload:
        update_kwargs["measured_at"] = payload["measured_at"]
    if "weight_kg" in payload:
        update_kwargs["weight"] = payload["weight_kg"]
        update_kwargs["unit"] = "kg"
    clear_fields: set[str] = set()
    for field in BODY_MEASUREMENT_METRIC_FIELDS:
        if field in payload:
            if payload[field] is None:
                clear_fields.add(field)
            else:
                update_kwargs[field] = payload[field]
    if "notes" in payload:
        if payload["notes"] is None:
            clear_fields.add("notes")
        else:
            update_kwargs["notes"] = payload["notes"]
    return {
        "measurement_id": UUID(str(payload["id"])),
        "payload": body_measurements.BodyMeasurementUpdate(
            **update_kwargs,
            clear_fields=frozenset(clear_fields),
        ),
    }


def _batch_update_menstrual_day_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Map canonical menstrual-day patch rows onto the domain update input."""
    kwargs: dict[str, Any] = {"day_id": UUID(str(payload["id"]))}
    for field in ("log_date", "in_period", "mood_changes", "protection_used", "spotting"):
        if field in payload and payload[field] is not None:
            kwargs[field] = payload[field]
    if "flow_amount" in payload:
        if payload["flow_amount"] is None:
            kwargs["clear_flow"] = True
        else:
            kwargs["flow_amount"] = payload["flow_amount"]
    if "symptoms" in payload:
        if payload["symptoms"] is None:
            kwargs["clear_symptoms"] = True
        else:
            kwargs["symptoms"] = payload["symptoms"]
    if "notes" in payload:
        if payload["notes"] is None:
            kwargs["clear_notes"] = True
        else:
            kwargs["notes"] = payload["notes"]
    if "factor_names" in payload:
        if payload["factor_names"] is None:
            kwargs["clear_factors"] = True
        else:
            kwargs["factor_names"] = payload["factor_names"]
    return kwargs


def _batch_update_menstrual_factor_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a canonical menstrual-factor patch row onto the domain update input."""
    if "name" not in payload or payload["name"] is None:
        raise DataOperationError("Menstrual-factor batch update requires a non-null `name`.")
    return {
        "factor_id": UUID(str(payload["id"])),
        "name": payload["name"],
    }


def _batch_update_sleep_segment_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    """Map canonical sleep-segment patch rows onto the domain update input."""
    kwargs: dict[str, Any] = {"segment_id": UUID(str(payload["id"]))}
    for field in ("start_at", "end_at"):
        if field in payload and payload[field] is not None:
            kwargs[field] = payload[field]
    return kwargs


UPDATE_KWARGS_BUILDERS: dict[str, Any] = {
    "area": _batch_update_area_kwargs,
    "body-measurement": _batch_update_body_measurement_kwargs,
    "menstrual": _batch_update_menstrual_day_kwargs,
    "menstrual-factor": _batch_update_menstrual_factor_kwargs,
    "person": _batch_update_person_kwargs,
    "sleep": _batch_update_sleep_segment_kwargs,
    "tag": _batch_update_tag_kwargs,
    "vision": _batch_update_vision_kwargs,
    "task": _batch_update_task_kwargs,
    "habit": _batch_update_habit_kwargs,
    "habit-action": _batch_update_habit_action_kwargs,
    "event": _batch_update_event_kwargs,
    "timelog": _batch_update_timelog_kwargs,
    "note": _batch_update_note_kwargs,
}

UPDATE_OPERATIONS: dict[str, Any] = {
    "area": areas.update_area,
    "body-measurement": body_measurements.update_body_measurement,
    "menstrual": menstrual_services.update_menstrual_day,
    "menstrual-factor": menstrual_services.update_menstrual_factor,
    "person": person.update_person,
    "sleep": sleep_services.update_sleep_segment,
    "tag": tags.update_tag,
    "vision": visions.update_vision,
    "task": tasks.update_task,
    "habit": habits.update_habit,
    "habit-action": habit_actions.update_habit_action,
    "event": events.update_event,
    "timelog": timelogs.update_timelog,
    "note": notes.update_note,
}

DELETE_OPERATIONS: dict[str, Any] = {
    "area": areas.batch_delete_areas,
    "body-measurement": body_measurements.batch_delete_body_measurements,
    "menstrual": menstrual_services.batch_delete_menstrual_days,
    "menstrual-factor": menstrual_services.batch_delete_menstrual_factors,
    "person": person.batch_delete_person,
    "sleep": sleep_services.batch_delete_sleep_segments,
    "tag": tags.batch_delete_tags,
    "vision": visions.batch_delete_visions,
    "task": tasks.batch_delete_tasks,
    "habit": habits.batch_delete_habits,
    "event": events.batch_delete_events,
    "timelog": timelogs.batch_delete_timelogs,
    "note": notes.batch_delete_notes,
}


async def batch_update_resource(
    session: AsyncSession,
    *,
    resource: str,
    rows: list[dict[str, Any]],
    continue_on_error: bool = False,
) -> DataBatchUpdateReport:
    """Apply batch updates for one resource using domain services."""
    if resource not in UPDATE_OPERATIONS:
        raise DataOperationError(f"Resource {resource!r} does not support batch update.")
    failures: list[DataOperationFailure] = []
    processed_count = 0
    updated_count = 0
    build_kwargs = UPDATE_KWARGS_BUILDERS[resource]
    operation = UPDATE_OPERATIONS[resource]

    for index, row in enumerate(rows, start=1):
        processed_count = index
        try:
            async with session.begin_nested():
                kwargs = build_kwargs(_normalize_patch_payload(resource, row))
                await operation(session, **kwargs)
            updated_count += 1
        except (DataOperationError, LookupError, ValueError, IntegrityError) as exc:
            failures.append(
                DataOperationFailure(
                    index=index,
                    resource=resource,
                    message=str(exc),
                    payload=row,
                    record_id=(UUID(str(row["id"])) if "id" in row else None),
                )
            )
            if not continue_on_error:
                break

    return DataBatchUpdateReport(
        resource=resource,
        processed_count=processed_count,
        updated_count=updated_count,
        failed_count=len(failures),
        failures=tuple(failures),
    )


async def _batch_delete_habit_actions(
    session: AsyncSession,
    *,
    action_ids: list[UUID],
) -> DataBatchDeleteReport:
    deleted_count = 0
    failures: list[DataOperationFailure] = []
    for index, action_id in enumerate(dict.fromkeys(action_ids), start=1):
        action = await habit_actions.get_habit_action_model(
            session,
            action_id=action_id,
        )
        if action is None:
            failures.append(
                DataOperationFailure(
                    index=index,
                    resource="habit-action",
                    message=f"Habit action {action_id} was not found",
                    record_id=action_id,
                )
            )
            continue
        action.soft_delete()
        deleted_count += 1
    await session.flush()
    return DataBatchDeleteReport(
        resource="habit-action",
        processed_count=len(action_ids),
        deleted_count=deleted_count,
        failed_count=len(failures),
        failures=tuple(failures),
    )


async def batch_delete_resource(
    session: AsyncSession,
    *,
    resource: str,
    record_ids: list[UUID],
) -> DataBatchDeleteReport:
    """Soft-delete multiple resource rows by identifier."""
    if resource == "habit-action":
        return await _batch_delete_habit_actions(session, action_ids=record_ids)
    if resource not in DELETE_OPERATIONS:
        raise DataOperationError(f"Resource {resource!r} does not support batch delete.")
    result = await DELETE_OPERATIONS[resource](session, **{DELETE_ARG_NAMES[resource]: record_ids})
    deleted_count = int(
        getattr(result, "deleted_count", None) or getattr(result, "restored_count", None) or 0
    )
    failures = tuple(
        DataOperationFailure(
            index=None,
            resource=resource,
            message=message,
            record_id=record_id,
        )
        for record_id, message in zip(result.failed_ids, result.errors, strict=False)
    )
    return DataBatchDeleteReport(
        resource=resource,
        processed_count=len(record_ids),
        deleted_count=deleted_count,
        failed_count=len(failures),
        failures=failures,
    )


async def _recompute_task_effort(session: AsyncSession) -> None:
    """Rebuild task effort from authoritative timelog rows."""
    task_ids = list(
        (
            await session.execute(
                select(Task.id).where(Task.deleted_at.is_(None)).order_by(Task.created_at.asc())
            )
        ).scalars()
    )
    for task_id in task_ids:
        await task_effort.recompute_task_self_minutes(session, task_id)
    for task_id in reversed(task_ids):
        await task_effort.recompute_totals_upwards(session, task_id)


async def _rebuild_timelog_stats(session: AsyncSession) -> None:
    """Replace every derived timelog aggregate from authoritative rows."""
    await session.execute(delete(AggregatedTimelogStatsGroupByArea))
    await session.execute(delete(DailyTimelogStatsGroupByArea))
    timelog_range = await timelog_stats.load_rebuildable_timelog_date_range(session)
    if timelog_range is None:
        return
    local_dates = timelog_stats.iter_date_range(*timelog_range)
    await timelog_stats.recompute_daily_timelog_stats_groupby_area_for_dates(
        session,
        local_dates=local_dates,
    )
    await timelog_stats.recompute_aggregated_timelog_stats_groupby_area_for_dates(
        session,
        local_dates=local_dates,
    )


async def run_post_import_hooks(session: AsyncSession, *, resources: set[str]) -> None:
    """Run derived-data maintenance after snapshot imports."""
    if {"task", "timelog"} & resources:
        await _recompute_task_effort(session)
    if "timelog" in resources:
        await _rebuild_timelog_stats(session)


def _bundle_manifest(
    table_counts: dict[str, int],
    entry_metadata: dict[str, dict[str, str | int]],
) -> dict[str, Any]:
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "exported_at": datetime.now().astimezone().isoformat(),
        "app_version": get_installed_package_version(),
        "database_schema": get_database_settings().database_schema,
        "timezone": get_preferences_settings().timezone,
        "source_tables": list(table_counts.keys()),
        "table_counts": table_counts,
        "derived_tables": [
            "aggregated_timelog_stats_groupby_area",
            "daily_timelog_stats_groupby_area",
        ],
        "entries": entry_metadata,
    }


async def _start_bundle_export_snapshot(session: AsyncSession) -> None:
    """Use one stable PostgreSQL snapshot for the bundle's many SELECTs."""
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if session.in_transaction():
        connection = await session.connection()
        isolation_level = (await connection.get_isolation_level()).upper()
        if isolation_level not in {"REPEATABLE READ", "SERIALIZABLE"}:
            raise DataOperationError(
                "PostgreSQL bundle export requires a fresh session or an existing "
                "REPEATABLE READ/SERIALIZABLE transaction."
            )
        return
    await session.connection(execution_options={"isolation_level": "REPEATABLE READ"})


async def export_bundle(
    session: AsyncSession,
    *,
    output_path: Path,
) -> BundleExportReport:
    """Export one lossless, versioned source-table snapshot atomically."""
    await _start_bundle_export_snapshot(session)
    table_counts: dict[str, int] = {}
    entry_metadata: dict[str, dict[str, str | int]] = {}
    expanded_size = 0
    with open_bundle_atomic(output_path) as writer:
        for table in source_tables():
            entry_name = f"tables/{table.name}.jsonl"
            digest = hashlib.sha256()
            row_count = 0
            entry_size = 0
            with writer.open_entry(entry_name) as entry:
                async with aclosing(iter_export_table_rows(session, table)) as rows:
                    async for row in rows:
                        encoded_row = encode_jsonl_row(row)
                        entry_size += len(encoded_row)
                        expanded_size += len(encoded_row)
                        if entry_size > MAX_BUNDLE_ENTRY_BYTES:
                            raise DataOperationError(
                                f"Bundle entry {entry_name} exceeds the supported expanded size."
                            )
                        if expanded_size > MAX_BUNDLE_TOTAL_BYTES:
                            raise DataOperationError("Bundle exceeds the supported expanded size.")
                        entry.write(encoded_row)
                        digest.update(encoded_row)
                        row_count += 1
            table_counts[table.name] = row_count
            entry_metadata[entry_name] = {
                "sha256": digest.hexdigest(),
                "row_count": row_count,
            }

        manifest_size = writer.write_manifest(_bundle_manifest(table_counts, entry_metadata))
        if expanded_size + manifest_size > MAX_BUNDLE_TOTAL_BYTES:
            raise DataOperationError("Bundle exceeds the supported expanded size.")
    return BundleExportReport(table_counts=table_counts, output_path=output_path)


def read_bundle(path: Path) -> BundlePayload:
    """Read and validate a bundle zip file."""
    try:
        with open_bundle_archive(path) as decoded:
            return _read_open_bundle(decoded)
    except BundleCodecError as exc:
        raise DataOperationError(str(exc)) from exc


def _prepare_v4_table_entry(
    decoded: BundleArchiveReader,
    *,
    table: Table,
    metadata: object,
) -> list[dict[str, Any]]:
    """Incrementally verify, decode, and prepare one table entry."""
    entry_name = f"tables/{table.name}.jsonl"
    if not isinstance(metadata, dict):
        raise DataOperationError(f"Invalid manifest metadata for {entry_name}.")
    checksum = metadata.get("sha256")
    row_count = metadata.get("row_count")
    if not isinstance(checksum, str):
        raise DataOperationError(f"Invalid checksum metadata for bundle entry {entry_name}.")
    if type(row_count) is not int or row_count < 0:
        raise DataOperationError(f"Invalid row count metadata for bundle entry {entry_name}.")

    digest = hashlib.sha256()
    actual_row_count = 0
    with decoded.open_entry(entry_name) as entry:

        def iter_rows():
            nonlocal actual_row_count
            for line_number, line in enumerate(entry, start=1):
                digest.update(line)
                if line.strip():
                    actual_row_count += 1
                    yield decode_jsonl_row(
                        line,
                        entry_name=entry_name,
                        line_number=line_number,
                    )

        try:
            prepared_rows = prepare_table_entry_rows(table, iter_rows())
        except BundleTableError as exc:
            raise DataOperationError(f"Invalid source-table snapshot: {exc}") from exc
    if checksum != digest.hexdigest():
        raise DataOperationError(f"Checksum mismatch for bundle entry {entry_name}.")
    if row_count != actual_row_count:
        raise DataOperationError(f"Row count mismatch for bundle entry {entry_name}.")
    return prepared_rows


def _read_open_bundle(
    decoded: BundleArchiveReader,
) -> BundlePayload:
    """Validate and decode an already-open bundle archive."""
    resources: dict[str, list[dict[str, Any]]] = {}
    manifest = decoded.manifest
    archive_entries = set(decoded.entry_names)
    schema_version = manifest.get("schema_version")
    if schema_version == LEGACY_BUNDLE_SCHEMA_VERSION:
        for resource in BUNDLE_RESOURCE_ORDER:
            entry_name = f"{resource}.jsonl"
            legacy_key = LEGACY_BUNDLE_RESOURCE_KEYS.get(resource)
            legacy_entry_name = f"{legacy_key}.jsonl" if legacy_key else None
            if entry_name not in archive_entries and legacy_entry_name in archive_entries:
                entry_name = legacy_entry_name
            content = decoded.read_entry(entry_name) if entry_name in archive_entries else b""
            try:
                resources[resource] = decode_jsonl(content, entry_name=entry_name)
            except BundleCodecError as exc:
                raise DataOperationError(str(exc)) from exc
        return BundlePayload(manifest=manifest, resources=resources)
    if schema_version != BUNDLE_SCHEMA_VERSION:
        raise DataOperationError(
            "Unsupported bundle schema version "
            f"{schema_version!r}. Expected {BUNDLE_SCHEMA_VERSION}. "
            "Older bundle schemas are not supported after habit-action notes moved "
            "to linked notes."
        )

    expected_entries = {f"tables/{table_name}.jsonl" for table_name in source_table_names()}
    manifest_entries = manifest.get("entries")
    if not isinstance(manifest_entries, dict):
        raise DataOperationError("Bundle manifest entries must be a JSON object.")
    tracked_entries = set(manifest_entries)
    if archive_entries != expected_entries or tracked_entries != expected_entries:
        missing = sorted(expected_entries - archive_entries)
        unexpected = sorted(archive_entries - expected_entries)
        untracked = sorted(archive_entries - tracked_entries)
        missing_from_archive = sorted(tracked_entries - archive_entries)
        details = []
        if missing:
            details.append("missing required archive entries: " + ", ".join(missing))
        if unexpected:
            details.append("unexpected archive entries: " + ", ".join(unexpected))
        if untracked:
            details.append("untracked archive entries: " + ", ".join(untracked))
        if missing_from_archive:
            details.append("manifest-only entries: " + ", ".join(missing_from_archive))
        unlisted = sorted(expected_entries - tracked_entries)
        if unlisted:
            details.append("entries absent from manifest: " + ", ".join(unlisted))
        raise DataOperationError(
            "Bundle entry set is incomplete or invalid (" + "; ".join(details) + ")."
        )
    if manifest.get("source_tables") != list(source_table_names()):
        raise DataOperationError("Bundle manifest has an invalid source_tables list.")
    table_counts = manifest.get("table_counts")
    if not isinstance(table_counts, dict):
        raise DataOperationError("Bundle manifest table_counts are required.")

    tables: dict[str, list[dict[str, Any]]] = {}
    for table in source_tables():
        entry_name = f"tables/{table.name}.jsonl"
        tables[table.name] = _prepare_v4_table_entry(
            decoded,
            table=table,
            metadata=manifest_entries[entry_name],
        )
    if table_counts != {table_name: len(rows) for table_name, rows in tables.items()}:
        raise DataOperationError("Bundle manifest table_counts do not match archive entries.")
    try:
        validate_prepared_tables(tables)
    except BundleTableError as exc:
        raise DataOperationError(f"Invalid source-table snapshot: {exc}") from exc
    return BundlePayload(
        manifest=manifest,
        resources=resources,
        tables=PreparedBundleTables(rows=tables),
    )


async def truncate_supported_data(session: AsyncSession) -> None:
    """Remove all supported data rows before importing a replacement bundle."""
    settings = get_database_settings()
    table_names = [
        (
            f'"{settings.database_schema}"."{table.name}"'
            if settings.database_schema is not None
            else f'"{table.name}"'
        )
        for table in Base.metadata.sorted_tables
    ]
    if not table_names:
        return
    policy = settings.backend_policy
    if policy is not None and policy.replace_existing_strategy == "truncate_cascade":
        await session.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} CASCADE"))
        return
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(delete(table))


async def import_bundle(
    session: AsyncSession,
    *,
    bundle: BundlePayload,
    replace_existing: bool = False,
) -> BundleImportReport:
    """Import a full bundle atomically."""
    schema_version = bundle.manifest.get("schema_version")
    if schema_version == LEGACY_BUNDLE_SCHEMA_VERSION and replace_existing:
        raise DataOperationError(
            "Legacy schema-v3 bundles are partial exports and cannot safely replace a database; "
            "import without --replace-existing or re-export with the current LifeOS version."
        )
    if schema_version == BUNDLE_SCHEMA_VERSION:
        if bundle.tables is None or bundle.resources:
            raise DataOperationError("Schema-v4 bundles require only a validated table snapshot.")
        prepared_tables = bundle.tables.rows
        if replace_existing:
            await truncate_supported_data(session)
        created_count, updated_count = await restore_table_rows(
            session,
            prepared_tables,
            replace_existing=replace_existing,
        )
        await run_post_import_hooks(session, resources={"task", "timelog"})
        return BundleImportReport(
            processed_count=created_count + updated_count,
            created_count=created_count,
            updated_count=updated_count,
            failed_count=0,
            failures=(),
            imported_resources=tuple(source_table_names()),
        )
    if schema_version != LEGACY_BUNDLE_SCHEMA_VERSION or bundle.tables is not None:
        raise DataOperationError(f"Unsupported or inconsistent bundle schema {schema_version!r}.")

    created_count = 0
    updated_count = 0
    imported_resources: list[str] = []
    prepared_by_resource: dict[str, list[PreparedSnapshotRow]] = {}

    for resource in BUNDLE_RESOURCE_ORDER:
        rows = bundle.resources.get(resource, [])
        if not rows:
            continue
        prepared_rows = [
            prepare_snapshot_row(resource, index + 1, row) for index, row in enumerate(rows)
        ]
        prepared_by_resource[resource] = prepared_rows
        created_delta, updated_delta = await _import_prepared_base_rows(
            session,
            prepared_rows=prepared_rows,
        )
        created_count += created_delta
        updated_count += updated_delta
        imported_resources.append(resource)

    for resource in imported_resources:
        await _sync_prepared_rows_relations(
            session,
            prepared_rows=prepared_by_resource[resource],
        )

    await run_post_import_hooks(session, resources=set(imported_resources))
    processed_count = created_count + updated_count
    return BundleImportReport(
        processed_count=processed_count,
        created_count=created_count,
        updated_count=updated_count,
        failed_count=0,
        failures=(),
        imported_resources=tuple(imported_resources),
    )
