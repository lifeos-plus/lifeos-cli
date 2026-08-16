"""CLI handlers for the data resource."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from lifeos_cli.cli_support import handler_utils as cli_handler_utils
from lifeos_cli.db import session as db_session
from lifeos_cli.db.services import data_ops


def _maybe_record_id(payload: dict[str, Any]) -> UUID | None:
    raw_value = payload.get("id")
    if raw_value is None:
        return None
    try:
        return UUID(str(raw_value))
    except (TypeError, ValueError):
        return None


def _read_text(path: str | None, *, stdin: bool) -> str:
    if stdin:
        return sys.stdin.read()
    if path is None:
        raise data_ops.DataOperationError("Use --file or --stdin to supply input data.")
    return Path(path).read_text(encoding="utf-8")


def _read_rows(path: str | None, *, stdin: bool, input_format: str) -> list[dict[str, Any]]:
    raw_text = _read_text(path, stdin=stdin)
    try:
        if input_format == "jsonl":
            rows = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
        elif input_format == "json":
            loaded = json.loads(raw_text)
            if not isinstance(loaded, list):
                raise data_ops.DataOperationError(
                    "JSON input must be a top-level array of objects."
                )
            rows = loaded
        else:
            raise data_ops.DataOperationError(f"Unsupported input format {input_format!r}.")
    except json.JSONDecodeError as exc:
        raise data_ops.DataOperationError(f"Invalid JSON input: {exc.msg}.") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise data_ops.DataOperationError("Every input row must be a JSON object.")
    return list(rows)


def _coerce_batch_delete_id(item: object, *, input_format: str) -> UUID:
    if isinstance(item, str):
        return UUID(item)
    if isinstance(item, dict) and "id" in item:
        return UUID(str(item["id"]))
    raise data_ops.DataOperationError(
        f"Batch-delete {input_format.upper()} input must contain UUID strings or objects with `id`."
    )


def _read_ids_from_plain_text(raw_text: str) -> list[UUID]:
    return [UUID(line.strip()) for line in raw_text.splitlines() if line.strip()]


def _read_ids_from_jsonl(raw_text: str) -> list[UUID]:
    record_ids: list[UUID] = []
    for line in raw_text.splitlines():
        if not line.strip():
            continue
        record_ids.append(_coerce_batch_delete_id(json.loads(line), input_format="jsonl"))
    return record_ids


def _read_ids_from_json(raw_text: str) -> list[UUID]:
    loaded = json.loads(raw_text)
    if not isinstance(loaded, list):
        raise data_ops.DataOperationError("Batch-delete JSON input must be a JSON array.")
    return [_coerce_batch_delete_id(item, input_format="json") for item in loaded]


def _read_ids_from_text_input(
    *,
    file_path: str | None,
    stdin: bool,
    input_format: str,
) -> list[UUID]:
    raw_text = _read_text(file_path, stdin=stdin)
    if input_format == "plain":
        return _read_ids_from_plain_text(raw_text)
    if input_format == "jsonl":
        return _read_ids_from_jsonl(raw_text)
    if input_format == "json":
        return _read_ids_from_json(raw_text)
    raise data_ops.DataOperationError(f"Unsupported delete input format {input_format!r}.")


def _read_ids(
    *,
    repeated_ids: list[UUID] | None,
    ids_file: str | None,
    file_path: str | None,
    stdin: bool,
    input_format: str,
) -> list[UUID]:
    ids = list(repeated_ids or [])
    try:
        if ids_file is not None:
            ids.extend(_read_ids_from_plain_text(Path(ids_file).read_text(encoding="utf-8")))
        if file_path is not None or stdin:
            ids.extend(
                _read_ids_from_text_input(
                    file_path=file_path, stdin=stdin, input_format=input_format
                )
            )
    except json.JSONDecodeError as exc:
        raise data_ops.DataOperationError(f"Invalid JSON input: {exc.msg}.") from exc
    except ValueError as exc:
        raise data_ops.DataOperationError(str(exc)) from exc
    if not ids:
        raise data_ops.DataOperationError(
            "Provide identifiers with --id, --ids-file, --file, or --stdin."
        )
    return list(dict.fromkeys(ids))


def _write_output(*, output_path: str | None, content: str) -> None:
    if output_path is None:
        print(content, end="" if content.endswith("\n") else "\n")
        return
    Path(output_path).write_text(content, encoding="utf-8")


def _serialize_rows(*, rows: list[dict[str, Any]], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    if output_format == "jsonl":
        return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    raise data_ops.DataOperationError(f"Unsupported export format {output_format!r}.")


def _format_failures(failures: tuple[data_ops.DataOperationFailure, ...]) -> str:
    return "\n".join(
        json.dumps(
            {
                "resource": failure.resource,
                "index": failure.index,
                "record_id": None if failure.record_id is None else str(failure.record_id),
                "message": failure.message,
                "payload": failure.payload,
            },
            ensure_ascii=False,
        )
        for failure in failures
    )


def _write_failures(
    *,
    failure_path: str | None,
    failures: tuple[data_ops.DataOperationFailure, ...],
) -> None:
    if failure_path is None or not failures:
        return
    Path(failure_path).write_text(_format_failures(failures) + "\n", encoding="utf-8")


async def handle_data_export_async(args: argparse.Namespace) -> int:
    try:
        async with db_session.session_scope() as session:
            if args.target == "all":
                if args.output is None:
                    print("Bundle export requires --output.", file=sys.stderr)
                    return 1
                report = await data_ops.export_bundle(
                    session,
                    output_path=Path(args.output),
                )
                print(f"Exported bundle to {report.output_path}")
                for resource, count in report.resource_counts.items():
                    print(f"{resource}: {count}")
                return 0

            if args.format == "bundle":
                print("Bundle format is only supported with `data export all`.", file=sys.stderr)
                return 1
            rows = await data_ops.export_resource_snapshot(
                session,
                resource=args.target,
            )
        _write_output(
            output_path=args.output,
            content=_serialize_rows(rows=rows, output_format=args.format),
        )
        if args.output is not None:
            print(f"Exported {len(rows)} {args.target} rows to {args.output}")
        return 0
    except data_ops.DataOperationError as exc:
        return cli_handler_utils.print_cli_error(exc)


async def _import_rows(
    *,
    resource: str,
    rows: list[dict[str, Any]],
    dry_run: bool,
    continue_on_error: bool,
    key_field: str | None = None,
) -> data_ops.DataImportReport:
    if key_field is not None:
        data_ops.validate_upsert_key(resource, key_field)
    session = db_session.get_async_session_factory()()
    created_count = 0
    updated_count = 0
    failures: list[data_ops.DataOperationFailure] = []
    try:
        for index, row in enumerate(rows, start=1):
            original_row = row
            try:
                async with session.begin_nested():
                    if key_field is not None:
                        row = await data_ops.resolve_upsert_row_id(
                            session,
                            resource=resource,
                            row=row,
                            key_field=key_field,
                            index=index,
                        )
                    report = await data_ops.import_resource_snapshot(
                        session,
                        resource=resource,
                        rows=[row],
                    )
                    created_count += report.created_count
                    updated_count += report.updated_count
            except (data_ops.DataOperationError, LookupError, ValueError) as exc:
                failures.append(
                    data_ops.DataOperationFailure(
                        index=index,
                        resource=resource,
                        message=str(exc),
                        payload=original_row,
                        record_id=_maybe_record_id(original_row),
                    )
                )
                if not continue_on_error:
                    break
        if not failures or continue_on_error:
            await data_ops.run_post_import_hooks(session, resources={resource})
        if dry_run or failures and not continue_on_error:
            await session.rollback()
        else:
            await session.commit()
    finally:
        await session.close()
    return data_ops.DataImportReport(
        resource=resource,
        processed_count=len(rows),
        created_count=created_count,
        updated_count=updated_count,
        failed_count=len(failures),
        failures=tuple(failures),
    )


async def handle_data_import_async(args: argparse.Namespace) -> int:
    try:
        if args.mode == "upsert" and not args.key:
            print("--mode upsert requires --key <field>.", file=sys.stderr)
            return 1
        if args.mode == "create" and args.key is not None:
            print("--key is only supported with --mode upsert.", file=sys.stderr)
            return 1
        if args.target == "bundle":
            if args.mode == "upsert" or args.key is not None:
                print(
                    "--mode and --key apply to single-resource imports only.",
                    file=sys.stderr,
                )
                return 1
            if args.continue_on_error:
                print(
                    "Bundle import is atomic and does not support --continue-on-error.",
                    file=sys.stderr,
                )
                return 1
            if args.file is None:
                print("Bundle import requires --file.", file=sys.stderr)
                return 1
            bundle_payload = data_ops.read_bundle(Path(args.file))
            session = db_session.get_async_session_factory()()
            try:
                bundle_report = await data_ops.import_bundle(
                    session,
                    bundle_rows=bundle_payload.resources,
                    replace_existing=args.replace_existing,
                )
                if args.dry_run:
                    await session.rollback()
                else:
                    await session.commit()
            finally:
                await session.close()
            print(f"Bundle resources: {', '.join(bundle_report.imported_resources) or '-'}")
            print(f"Created rows: {bundle_report.created_count}")
            print(f"Updated rows: {bundle_report.updated_count}")
            if args.dry_run:
                print("Dry run: bundle changes were rolled back.")
            return 0

        if args.format == "bundle":
            print("Bundle format is only supported with `data import bundle`.", file=sys.stderr)
            return 1
        rows = _read_rows(args.file, stdin=args.stdin, input_format=args.format)
        import_report = await _import_rows(
            resource=args.target,
            rows=rows,
            dry_run=args.dry_run,
            continue_on_error=args.continue_on_error,
            key_field=args.key,
        )
        _write_failures(failure_path=args.error_file, failures=import_report.failures)
        print(f"Resource: {import_report.resource}")
        print(f"Processed rows: {import_report.processed_count}")
        print(f"Created rows: {import_report.created_count}")
        print(f"Updated rows: {import_report.updated_count}")
        print(f"Failed rows: {import_report.failed_count}")
        return 0 if import_report.failed_count == 0 else 1
    except (data_ops.DataOperationError, LookupError, ValueError) as exc:
        return cli_handler_utils.print_cli_error(exc)


async def handle_data_batch_update_async(args: argparse.Namespace) -> int:
    try:
        rows = _read_rows(args.file, stdin=args.stdin, input_format=args.format)
        session = db_session.get_async_session_factory()()
        try:
            report = await data_ops.batch_update_resource(
                session,
                resource=args.target,
                rows=rows,
                continue_on_error=args.continue_on_error,
            )
            if args.dry_run or report.failed_count and not args.continue_on_error:
                await session.rollback()
            else:
                await session.commit()
        finally:
            await session.close()
        _write_failures(failure_path=args.error_file, failures=report.failures)
        print(f"Resource: {report.resource}")
        print(f"Processed rows: {report.processed_count}")
        print(f"Updated rows: {report.updated_count}")
        print(f"Failed rows: {report.failed_count}")
        return 0 if report.failed_count == 0 else 1
    except data_ops.DataOperationError as exc:
        return cli_handler_utils.print_cli_error(exc)


async def handle_data_batch_delete_async(args: argparse.Namespace) -> int:
    try:
        record_ids = _read_ids(
            repeated_ids=args.record_ids,
            ids_file=args.ids_file,
            file_path=args.file,
            stdin=args.stdin,
            input_format=args.format,
        )
    except data_ops.DataOperationError as exc:
        return cli_handler_utils.print_cli_error(exc)

    session = db_session.get_async_session_factory()()
    try:
        report = await data_ops.batch_delete_resource(
            session,
            resource=args.target,
            record_ids=record_ids,
        )
        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()
    except (data_ops.DataOperationError, LookupError, ValueError) as exc:
        await session.rollback()
        await session.close()
        return cli_handler_utils.print_cli_error(exc)
    await session.close()
    _write_failures(failure_path=args.error_file, failures=report.failures)
    print(f"Resource: {report.resource}")
    print(f"Processed IDs: {report.processed_count}")
    print(f"Deleted rows: {report.deleted_count}")
    print(f"Failed rows: {report.failed_count}")
    return 0 if report.failed_count == 0 else 1
