#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}/web"

echo "[web-validate] install locked dependencies"
npm ci

echo "[web-validate] audit high-severity vulnerabilities"
npm audit --audit-level=high

echo "[web-validate] validate translation catalogs"
npm run i18n:check

echo "[web-validate] build frontend"
npm run build

echo "[web-validate] lint frontend"
npm run lint

echo "[web-validate] run frontend tests"
npm test
