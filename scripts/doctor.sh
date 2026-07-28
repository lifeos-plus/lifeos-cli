#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${SCRIPT_DIR}/load_local_env.sh"
load_local_env "${REPO_ROOT}/.env"

clean_build_artifacts() {
  rm -rf build dist src/*.egg-info
}

echo "[doctor] sync dependencies"
uv sync --extra dev --extra web --extra postgres --frozen

echo "[doctor] run lint"
uv run pre-commit run --all-files

echo "[doctor] run tests"
uv run pytest -m "not integration"

echo "[doctor] export locked requirements with all extras"
uv export --format requirements.txt --all-extras --no-dev --locked --no-emit-project \
  --output-file /tmp/locked-requirements.txt >/dev/null

echo "[doctor] run locked dependency vulnerability audit"
uv run pip-audit --requirement /tmp/locked-requirements.txt

echo "[doctor] clean build artifacts"
clean_build_artifacts

echo "[doctor] build package artifacts"
uv build --no-sources

echo "[doctor] run integration tests"
integration_status="passed"
if bash ./scripts/integration_tests.sh; then
  :
else
  status=$?
  if [ "$status" -eq 3 ]; then
    integration_status="skipped"
    echo "[doctor] integration tests skipped: PostgreSQL CLI coverage requires LIFEOS_TEST_DATABASE_URL" >&2
  else
    exit "$status"
  fi
fi

echo "[doctor] clean build artifacts after validation"
clean_build_artifacts

if [ "$integration_status" = "skipped" ]; then
  echo "[doctor] completed without PostgreSQL CLI integration coverage" >&2
else
  echo "[doctor] completed with PostgreSQL CLI integration coverage"
fi
