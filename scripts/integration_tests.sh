#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${SCRIPT_DIR}/load_local_env.sh"
load_local_env "${REPO_ROOT}/.env"

if [ -z "${LIFEOS_TEST_DATABASE_URL:-}" ]; then
  echo "[integration] skipped: set LIFEOS_TEST_DATABASE_URL to run PostgreSQL CLI integration tests" >&2
  exit 3
fi

uv sync --extra dev --extra web --extra postgres --frozen
# Select by the shared marker so database service integration tests participate too.
uv run pytest -m integration
