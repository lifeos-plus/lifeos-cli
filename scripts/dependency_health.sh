#!/usr/bin/env bash
set -euo pipefail

echo "[dependency-health] list outdated packages"
uv pip list --outdated

dev_requirements="$(mktemp)"
trap 'rm -f "${dev_requirements}"' EXIT

echo "[dependency-health] export dev extra requirements"
uv export --format requirements.txt --extra dev --no-dev --locked --no-emit-project --output-file "${dev_requirements}" >/dev/null

echo "[dependency-health] run dev dependency vulnerability audit"
PIP_NO_CACHE_DIR=1 uv run pip-audit --requirement "${dev_requirements}"
