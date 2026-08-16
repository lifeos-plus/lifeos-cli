"""Export the Web API OpenAPI document without starting a server or database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lifeos_web.app import create_app

RELEASE_PROVENANCE_KEY = "x-lifeos-cli-release"


def export_openapi(output: Path, release_tag: str | None = None) -> None:
    """Write a deterministic OpenAPI JSON document to ``output``."""
    document = create_app().openapi()
    if release_tag:
        document.setdefault("info", {})[RELEASE_PROVENANCE_KEY] = release_tag
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="OpenAPI JSON output path.")
    parser.add_argument(
        "--release-tag",
        help=(
            "GitHub release tag (for example v1.2.0) recorded under "
            f"info.{RELEASE_PROVENANCE_KEY} so the pinned contract is "
            "self-describing. Omit to keep the exported document tag-free."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    export_openapi(args.output, release_tag=args.release_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
