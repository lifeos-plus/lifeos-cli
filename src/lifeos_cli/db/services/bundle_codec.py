"""Safe archive codec for portable LifeOS database bundles."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

MAX_BUNDLE_ENTRY_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_TOTAL_BYTES = 1024 * 1024 * 1024


class BundleCodecError(RuntimeError):
    """Raised when a bundle archive is incomplete, unsafe, or malformed."""


@dataclass(frozen=True)
class BundleArchiveReader:
    """Validated manifest and streaming access to archive entries."""

    manifest: dict[str, Any]
    entry_names: tuple[str, ...]
    _archive: ZipFile

    @contextmanager
    def open_entry(self, name: str) -> Iterator[IO[bytes]]:
        """Open one previously validated archive entry for incremental reads."""
        try:
            with self._archive.open(name, "r") as handle:
                yield handle
        except RuntimeError as exc:
            raise BundleCodecError(f"Unable to read bundle entry {name!r}: {exc}.") from exc

    def read_entry(self, name: str) -> bytes:
        """Read one previously validated archive entry."""
        with self.open_entry(name) as handle:
            return handle.read()


class BundleArchiveWriter:
    """Validated entry writer for an atomic bundle archive."""

    def __init__(self, archive: ZipFile) -> None:
        self._archive = archive
        self._names: set[str] = set()
        self._manifest_written = False

    def _reserve_entry_name(self, name: str) -> None:
        if self._manifest_written:
            raise BundleCodecError("Bundle entries cannot be written after the manifest.")
        _validate_entry_name(name)
        if name == "manifest.json":
            raise BundleCodecError("manifest.json must be written with write_manifest().")
        if name in self._names:
            raise BundleCodecError(f"Duplicate bundle entry name: {name!r}.")
        self._names.add(name)

    @contextmanager
    def open_entry(self, name: str) -> Iterator[IO[bytes]]:
        """Open one unique archive entry for incremental binary writes."""
        self._reserve_entry_name(name)
        with self._archive.open(name, "w", force_zip64=True) as handle:
            yield handle

    def write_entry(self, name: str, content: bytes) -> None:
        """Write one unique non-manifest archive entry."""
        with self.open_entry(name) as handle:
            handle.write(content)

    def write_manifest(self, manifest: dict[str, Any]) -> int:
        """Write the archive manifest exactly once and return its expanded size."""
        if self._manifest_written:
            raise BundleCodecError("Bundle manifest has already been written.")
        try:
            manifest_bytes = json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise BundleCodecError(f"Bundle manifest is not valid JSON: {exc}.") from exc
        self._archive.writestr("manifest.json", manifest_bytes)
        self._manifest_written = True
        return len(manifest_bytes)


def encode_jsonl_row(row: dict[str, Any]) -> bytes:
    """Encode one canonical JSONL row for incremental hashing and writes."""
    try:
        return (json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BundleCodecError(f"Bundle row is not valid JSON: {exc}.") from exc


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BundleCodecError(f"JSON object contains duplicate key {key!r}.")
        value[key] = item
    return value


def _reject_nonfinite_json_number(value: str) -> Any:
    raise BundleCodecError(f"JSON contains non-finite number {value!r}.")


def decode_jsonl_row(content: bytes, *, entry_name: str, line_number: int) -> dict[str, Any]:
    """Decode one JSONL row and require an object value."""
    try:
        value = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleCodecError(
            f"Invalid JSONL content in {entry_name} at line {line_number}: {exc}."
        ) from exc
    if not isinstance(value, dict):
        raise BundleCodecError(
            f"Bundle entry {entry_name} line {line_number} must be a JSON object."
        )
    return value


def decode_jsonl(content: bytes, *, entry_name: str) -> list[dict[str, Any]]:
    """Decode one JSONL archive entry and require object rows."""
    return [
        decode_jsonl_row(line, entry_name=entry_name, line_number=line_number)
        for line_number, line in enumerate(content.splitlines(), start=1)
        if line.strip()
    ]


def _validate_entry_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not name or name.endswith("/"):
        raise BundleCodecError(f"Unsafe bundle entry name: {name!r}.")


def _fsync_directory(path: Path) -> None:
    """Persist a completed rename on filesystems that support directory fsync."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        try:
            os.fsync(directory_descriptor)
        except OSError:
            pass
    finally:
        os.close(directory_descriptor)


@contextmanager
def open_bundle_atomic(output_path: Path) -> Iterator[BundleArchiveWriter]:
    """Yield an owner-only archive writer and atomically publish it on success."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "w+b")
        descriptor = -1
        with handle:
            with ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
                writer = BundleArchiveWriter(archive)
                yield writer
                if not writer._manifest_written:
                    raise BundleCodecError("Bundle archive is missing its manifest.")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output_path)
        _fsync_directory(output_path.parent)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        raise


@contextmanager
def open_bundle_archive(path: Path) -> Iterator[BundleArchiveReader]:
    """Validate archive structure and yield streaming entry access."""
    try:
        with ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise BundleCodecError("Bundle archive contains duplicate entry names.")
            for name in names:
                _validate_entry_name(name)
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_BUNDLE_TOTAL_BYTES:
                raise BundleCodecError("Bundle archive exceeds the maximum expanded size.")
            oversized = [info.filename for info in infos if info.file_size > MAX_BUNDLE_ENTRY_BYTES]
            if oversized:
                raise BundleCodecError(
                    "Bundle entry exceeds the maximum expanded size: " + ", ".join(oversized)
                )
            if "manifest.json" not in names:
                raise BundleCodecError("Bundle archive is missing manifest.json.")
            try:
                manifest = json.loads(
                    archive.read("manifest.json").decode("utf-8"),
                    object_pairs_hook=_reject_duplicate_json_keys,
                    parse_constant=_reject_nonfinite_json_number,
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BundleCodecError(f"Invalid bundle manifest: {exc}.") from exc
            if not isinstance(manifest, dict):
                raise BundleCodecError("Bundle manifest must be a JSON object.")
            yield BundleArchiveReader(
                manifest=manifest,
                entry_names=tuple(name for name in names if name != "manifest.json"),
                _archive=archive,
            )
    except (BadZipFile, OSError) as exc:
        raise BundleCodecError(f"Unable to read bundle archive: {exc}.") from exc
