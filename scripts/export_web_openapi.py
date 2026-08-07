"""Export the Web API OpenAPI document without starting a server or database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lifeos_web.app import create_app


def export_openapi(output: Path) -> None:
    """Write a deterministic OpenAPI JSON document to ``output``."""
    document = create_app().openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="OpenAPI JSON output path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    export_openapi(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
