#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXPECTED="${REPO_ROOT}/docs/cli-tree.md"
ACTUAL="$(mktemp)"
trap 'rm -f "${ACTUAL}"' EXIT

export LIFEOS_LANGUAGE=en
uv run python "${SCRIPT_DIR}/audit_cli_help.py" --format tree --output "${ACTUAL}"
if ! diff -u "${EXPECTED}" "${ACTUAL}"; then
  echo "docs/cli-tree.md is out of date. Regenerate with:" >&2
  echo "  LIFEOS_LANGUAGE=en uv run python scripts/audit_cli_help.py --format tree --output docs/cli-tree.md" >&2
  exit 1
fi
