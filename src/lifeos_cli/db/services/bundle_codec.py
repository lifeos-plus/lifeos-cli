"""Safe archive codec for portable LifeOS database bundles."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

MAX_BUNDLE_ENTRY_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_TOTAL_BYTES = 1024 * 1024 * 1024


class BundleCodecError(RuntimeError):
    """Raised when a bundle archive is incomplete, unsafe, or malformed."""


@dataclass(frozen=True)
class DecodedBundleArchive:
    """Validated manifest and raw archive entries."""

    manifest: dict[str, Any]
    entries: dict[str, bytes]


def encode_jsonl(rows: list[dict[str, Any]]) -> bytes:
    """Encode canonical JSONL bytes for hashing and archive storage."""
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def decode_jsonl(content: bytes, *, entry_name: str) -> list[dict[str, Any]]:
    """Decode one JSONL archive entry and require object rows."""
    try:
        values = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
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


def write_bundle_atomic(
    output_path: Path,
    *,
    entries: dict[str, bytes],
    manifest: dict[str, Any],
) -> None:
    """Write a complete owner-only archive and atomically replace the target."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for entry_name in entries:
        _validate_entry_name(entry_name)
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w+b") as handle:
            with ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
                for entry_name, content in entries.items():
                    archive.writestr(entry_name, content)
                archive.writestr("manifest.json", manifest_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output_path)
        os.chmod(output_path, 0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def read_bundle_archive(path: Path) -> DecodedBundleArchive:
    """Read an archive with path, duplicate-name, and decompressed-size guards."""
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
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BundleCodecError(f"Invalid bundle manifest: {exc}.") from exc
            if not isinstance(manifest, dict):
                raise BundleCodecError("Bundle manifest must be a JSON object.")
            entries = {
                info.filename: archive.read(info.filename)
                for info in infos
                if info.filename != "manifest.json"
            }
    except (BadZipFile, OSError) as exc:
        raise BundleCodecError(f"Unable to read bundle archive: {exc}.") from exc
    return DecodedBundleArchive(manifest=manifest, entries=entries)
