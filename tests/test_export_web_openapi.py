"""Tests for the Web API OpenAPI export provenance."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_export_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "export_web_openapi.py"
    spec = importlib.util.spec_from_file_location("export_web_openapi", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export_module = _load_export_module()


def test_export_records_the_release_tag(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    export_module.export_openapi(output, release_tag="v1.2.0")

    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["info"]["x-lifeos-cli-release"] == "v1.2.0"


def test_export_omits_provenance_without_a_release_tag(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    export_module.export_openapi(output)

    document = json.loads(output.read_text(encoding="utf-8"))
    assert "x-lifeos-cli-release" not in document["info"]
