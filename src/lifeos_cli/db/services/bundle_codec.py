"""Safe archive codec for portable LifeOS database bundles."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
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

    def read_entry(self, name: str) -> bytes:
        """Read one previously validated archive entry."""
        try:
            return self._archive.read(name)
        except RuntimeError as exc:
            raise BundleCodecError(f"Unable to read bundle entry {name!r}: {exc}.") from exc


class BundleArchiveWriter:
    """Validated entry writer for an atomic bundle archive."""

    def __init__(self, archive: ZipFile) -> None:
        self._archive = archive
        self._names: set[str] = set()
        self._manifest_written = False

    def write_entry(self, name: str, content: bytes) -> None:
        """Write one unique non-manifest archive entry."""
        if self._manifest_written:
            raise BundleCodecError("Bundle entries cannot be written after the manifest.")
        _validate_entry_name(name)
        if name == "manifest.json":
            raise BundleCodecError("manifest.json must be written with write_manifest().")
        if name in self._names:
            raise BundleCodecError(f"Duplicate bundle entry name: {name!r}.")
        self._archive.writestr(name, content)
        self._names.add(name)

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        """Write the archive manifest exactly once."""
        if self._manifest_written:
            raise BundleCodecError("Bundle manifest has already been written.")
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        self._archive.writestr("manifest.json", manifest_bytes)
        self._manifest_written = True


def encode_jsonl(rows: list[dict[str, Any]]) -> bytes:
    """Encode canonical JSONL bytes for hashing and archive storage."""
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BundleCodecError(f"JSON object contains duplicate key {key!r}.")
        value[key] = item
    return value


def decode_jsonl(content: bytes, *, entry_name: str) -> list[dict[str, Any]]:
    """Decode one JSONL archive entry and require object rows."""
    try:
        values = [
            json.loads(line, object_pairs_hook=_reject_duplicate_json_keys)
            for line in content.decode("utf-8").splitlines()
            if line.strip()
        ]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleCodecError(f"Invalid JSONL content in {entry_name}: {exc}.") from exc
    if not all(isinstance(value, dict) for value in values):
        raise BundleCodecError(f"Every row in {entry_name} must be a JSON object.")
    return values


def sha256_hex(content: bytes) -> str:
    """Return the lowercase SHA-256 digest for content."""
    return hashlib.sha256(content).hexdigest()


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
