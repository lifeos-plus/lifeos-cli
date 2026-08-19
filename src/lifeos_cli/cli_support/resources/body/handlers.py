"""Body measurement command handlers."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

from lifeos_cli.application.time_preferences import to_storage_timezone
from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.cli_support.json_output import print_json_items, print_json_payload
from lifeos_cli.cli_support.output_utils import (
    format_timestamp,
    print_summary_rows,
)
from lifeos_cli.cli_support.time_args import DateArgumentError, resolve_date_selection_arguments
from lifeos_cli.db import session as db_session
from lifeos_cli.db.base import utc_now
from lifeos_cli.db.models.body_measurement import BodyMeasurement
from lifeos_cli.db.services import body_measurements as body_services

BODY_SUMMARY_COLUMNS = (
    "measurement_id",
    "measured_at",
    "weight",
    "body_fat_percentage",
    "visceral_fat",
    "notes",
)


def _compute_bmi_payload(
    measurement: BodyMeasurement,
    height_cm: float | None,
) -> float | None:
    bmi = body_services.compute_bmi(measurement.weight_kg, height_cm)
    return float(bmi) if bmi is not None else None


_METRIC_ARG_FIELDS = {
    "body_fat": "body_fat_percentage",
    "visceral_fat": "visceral_fat",
    "fat_mass": "fat_mass_kg",
    "muscle_percentage": "muscle_percentage",
    "muscle_mass": "muscle_mass_kg",
    "body_water": "body_water_kg",
    "protein": "protein_kg",
    "bone_mass": "bone_mass_kg",
    "skeletal_muscle": "skeletal_muscle_kg",
}


def _display_unit(args: argparse.Namespace | None = None) -> str:
    if args is not None and getattr(args, "unit", None) is not None:
        unit_value = args.unit
        if isinstance(unit_value, str):
            return unit_value
    return body_services.preferred_weight_unit()


def _measurement_payload(
    measurement: BodyMeasurement,
    *,
    display_unit: str,
) -> dict[str, Any]:
    height_cm = body_services.get_preferences_settings().body_height_cm
    payload: dict[str, Any] = {
        "id": str(measurement.id),
        "measured_at": format_timestamp(measurement.measured_at),
        "weight_kg": float(measurement.weight_kg),
        "display_unit": display_unit,
        "weight_display": (
            f"{body_services.from_kg(measurement.weight_kg, display_unit)} {display_unit}"
        ),
        "bmi": _compute_bmi_payload(measurement, height_cm),
        "notes": measurement.notes,
        "created_at": format_timestamp(measurement.created_at),
        "updated_at": format_timestamp(measurement.updated_at),
    }
    for metric_field in _METRIC_ARG_FIELDS.values():
        value = getattr(measurement, metric_field)
        payload[metric_field] = float(value) if value is not None else None
    return payload


def _format_body_summary(
    measurement: BodyMeasurement,
    *,
    display_unit: str,
) -> str:
    body_fat = getattr(measurement, "body_fat_percentage", None)
    visceral = getattr(measurement, "visceral_fat", None)
    return (
        f"{measurement.id}\t{format_timestamp(measurement.measured_at)}\t"
        f"{body_services.from_kg(measurement.weight_kg, display_unit)} {display_unit}\t"
        f"{body_fat if body_fat is not None else '-'}\t"
        f"{visceral if visceral is not None else '-'}\t"
        f"{measurement.notes or '-'}"
    )


def _resolve_date_range(args: argparse.Namespace) -> tuple[date | None, date | None]:
    try:
        resolved = resolve_date_selection_arguments(
            date_values=args.date_values,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except DateArgumentError as exc:
        raise DateArgumentError(str(exc)) from exc
    return resolved.start_date, resolved.end_date


def _metric_values(args: argparse.Namespace) -> dict[str, float]:
    return {
        field: float(getattr(args, arg))
        for arg, field in _METRIC_ARG_FIELDS.items()
        if getattr(args, arg) is not None
    }


def _clear_fields(args: argparse.Namespace) -> frozenset[str]:
    cleared: set[str] = set()
    for arg, field in _METRIC_ARG_FIELDS.items():
        if getattr(args, f"clear_{arg}", False):
            cleared.add(field)
    if getattr(args, "clear_notes", False):
        cleared.add("notes")
    return frozenset(cleared)


async def handle_body_add_async(args: argparse.Namespace) -> int:
    """Create one body measurement record."""
    measured_at = args.measured_at or utc_now()
    metric_values = _metric_values(args)
    payload = body_services.BodyMeasurementCreate(
        measured_at=to_storage_timezone(measured_at),
        weight=args.weight,
        unit=_display_unit(args),
        notes=args.notes,
        body_fat_percentage=metric_values.get("body_fat_percentage"),
        visceral_fat=metric_values.get("visceral_fat"),
        fat_mass_kg=metric_values.get("fat_mass_kg"),
        muscle_percentage=metric_values.get("muscle_percentage"),
        muscle_mass_kg=metric_values.get("muscle_mass_kg"),
        body_water_kg=metric_values.get("body_water_kg"),
        protein_kg=metric_values.get("protein_kg"),
        bone_mass_kg=metric_values.get("bone_mass_kg"),
        skeletal_muscle_kg=metric_values.get("skeletal_muscle_kg"),
    )
    try:
        async with db_session.session_scope() as session:
            measurement = await body_services.create_body_measurement(
                session,
                payload=payload,
            )
    except body_services.BodyMeasurementValidationError as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Created body measurement {measurement.id}")
    return 0


async def handle_body_list_async(args: argparse.Namespace) -> int:
    """List body measurements."""
    try:
        start_date, end_date = _resolve_date_range(args)
    except DateArgumentError as exc:
        return cli_handler_utils.print_cli_error(exc)
    async with db_session.session_scope() as session:
        measurements = await body_services.list_body_measurements(
            session,
            start_date=start_date,
            end_date=end_date,
            limit=args.limit,
            offset=args.offset,
        )
    display_unit = _display_unit()
    if args.json:
        print_json_items(
            [
                _measurement_payload(measurement, display_unit=display_unit)
                for measurement in measurements
            ]
        )
        return 0
    print_summary_rows(
        items=measurements,
        columns=BODY_SUMMARY_COLUMNS,
        row_formatter=lambda item: _format_body_summary(item, display_unit=display_unit),
        empty_message="No body measurements found.",
    )
    return 0


async def handle_body_show_async(args: argparse.Namespace) -> int:
    """Show one body measurement with derived BMI."""
    async with db_session.session_scope() as session:
        measurement = await body_services.get_body_measurement(
            session,
            measurement_id=args.measurement_id,
        )
        if measurement is None:
            return cli_handler_utils.print_missing_record_error(
                "Body measurement",
                args.measurement_id,
            )
    display_unit = _display_unit()
    if args.json:
        print_json_payload(_measurement_payload(measurement, display_unit=display_unit))
        return 0
    print(f"body_measurement_id: {measurement.id}")
    print(f"measured_at: {format_timestamp(measurement.measured_at)}")
    print(
        f"weight: {body_services.from_kg(measurement.weight_kg, display_unit)} {display_unit} "
        f"({float(measurement.weight_kg)} kg)"
    )
    for metric_field in _METRIC_ARG_FIELDS.values():
        value = getattr(measurement, metric_field)
        print(f"{metric_field}: {float(value) if value is not None else '-'}")
    bmi = body_services.compute_bmi(
        measurement.weight_kg,
        body_services.get_preferences_settings().body_height_cm,
    )
    print(f"bmi: {float(bmi) if bmi is not None else '-'}")
    print(f"notes: {measurement.notes or '-'}")
    print(f"created_at: {format_timestamp(measurement.created_at)}")
    print(f"updated_at: {format_timestamp(measurement.updated_at)}")
    return 0


async def handle_body_update_async(args: argparse.Namespace) -> int:
    """Update one body measurement record."""
    metric_values = _metric_values(args)
    payload = body_services.BodyMeasurementUpdate(
        measured_at=to_storage_timezone(args.measured_at) if args.measured_at else None,
        weight=args.weight,
        unit=_display_unit(args),
        notes=args.notes,
        clear_fields=_clear_fields(args),
        body_fat_percentage=metric_values.get("body_fat_percentage"),
        visceral_fat=metric_values.get("visceral_fat"),
        fat_mass_kg=metric_values.get("fat_mass_kg"),
        muscle_percentage=metric_values.get("muscle_percentage"),
        muscle_mass_kg=metric_values.get("muscle_mass_kg"),
        body_water_kg=metric_values.get("body_water_kg"),
        protein_kg=metric_values.get("protein_kg"),
        bone_mass_kg=metric_values.get("bone_mass_kg"),
        skeletal_muscle_kg=metric_values.get("skeletal_muscle_kg"),
    )
    try:
        async with db_session.session_scope() as session:
            measurement = await body_services.update_body_measurement(
                session,
                measurement_id=args.measurement_id,
                payload=payload,
            )
    except (
        body_services.BodyMeasurementNotFoundError,
        body_services.BodyMeasurementValidationError,
    ) as exc:
        return cli_handler_utils.print_cli_error(exc)
    print(f"Updated body measurement {measurement.id}")
    return 0


async def handle_body_delete_async(args: argparse.Namespace) -> int:
    """Soft-delete one or more body measurements."""
    failed_ids: list[object] = []
    errors: list[str] = []
    for measurement_id in args.measurement_ids:
        try:
            async with db_session.session_scope() as session:
                await body_services.delete_body_measurement(
                    session,
                    measurement_id=measurement_id,
                )
        except body_services.BodyMeasurementNotFoundError as exc:
            failed_ids.append(measurement_id)
            errors.append(str(exc))
    for measurement_id in args.measurement_ids:
        if measurement_id not in failed_ids:
            print(f"Soft-deleted body measurement {measurement_id}")
    for error in errors:
        print(f"Error: {error}", file=sys.stderr)
    return 1 if failed_ids else 0
