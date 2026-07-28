import json
import re
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from lifeos_cli.config import SUPPORTED_THEMES

GITIGNORE_TEXT = Path(".gitignore").read_text()
DEPENDABOT_CONFIG = yaml.safe_load(Path(".github/dependabot.yml").read_text())
DOCTOR_TEXT = Path("scripts/doctor.sh").read_text()
DEAD_CODE_CHECK_TEXT = Path("scripts/dead_code_check.sh").read_text()
DEPENDENCY_HEALTH_TEXT = Path("scripts/dependency_health.sh").read_text()
WEB_DEPENDENCY_HEALTH_TEXT = Path("scripts/web_dependency_health.sh").read_text()
WEB_VALIDATE_TEXT = Path("scripts/web_validate.sh").read_text()
PRE_COMMIT_CONFIG = yaml.safe_load(Path(".pre-commit-config.yaml").read_text())
DEPENDENCY_REVIEW_WORKFLOW = yaml.safe_load(
    Path(".github/workflows/dependency-review.yml").read_text()
)
FRONTEND_DEPENDENCY_AUDIT_WORKFLOW = yaml.safe_load(
    Path(".github/workflows/frontend-dependency-audit.yml").read_text()
)
VALIDATE_WORKFLOW = yaml.safe_load(Path(".github/workflows/validate.yml").read_text())
VULTURE_WHITELIST_TEXT = Path("scripts/vulture_whitelist.py").read_text()
LOAD_LOCAL_ENV_TEXT = Path("scripts/load_local_env.sh").read_text()
WEB_THEME_TEXT = Path("web/src/theme.ts").read_text()


def _non_comment_shell_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _workflow_job_steps(workflow: dict[str, Any], job_name: str) -> list[dict[str, Any]]:
    jobs = cast(dict[str, Any], workflow["jobs"])
    steps = cast(list[dict[str, Any]], jobs[job_name]["steps"])
    assert isinstance(steps, list)
    return steps


def _flatten_json_catalog_keys(catalog: dict[str, Any]) -> dict[str, str]:
    flattened: dict[str, str] = {}

    def _visit(node: Any, prefix: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                _visit(value, (*prefix, str(key)))
            return
        flattened[".".join(prefix)] = node if isinstance(node, str) else ""

    _visit(catalog, ())
    return flattened


def _extract_frontend_available_themes() -> tuple[str, ...]:
    match = re.search(
        r"export const AVAILABLE_THEMES: AppTheme\[] = \[(?P<body>.*?)\];",
        WEB_THEME_TEXT,
        flags=re.DOTALL,
    )
    assert match is not None
    return tuple(re.findall(r'"([^"]+)"', match.group("body")))


DOCTOR_COMMANDS = _non_comment_shell_lines(DOCTOR_TEXT)
DEPENDENCY_HEALTH_COMMANDS = _non_comment_shell_lines(DEPENDENCY_HEALTH_TEXT)
WEB_DEPENDENCY_HEALTH_COMMANDS = _non_comment_shell_lines(WEB_DEPENDENCY_HEALTH_TEXT)
WEB_VALIDATE_COMMANDS = _non_comment_shell_lines(WEB_VALIDATE_TEXT)
QUALITY_GATE_STEPS = _workflow_job_steps(VALIDATE_WORKFLOW, "quality-gate")
INTEGRATION_JOB_STEPS = _workflow_job_steps(VALIDATE_WORKFLOW, "integration-postgres")


def test_dependabot_configuration_keeps_backend_and_frontend_updates_separate() -> None:
    updates = DEPENDABOT_CONFIG["updates"]
    assert isinstance(updates, list)
    entries = {entry["package-ecosystem"]: entry for entry in updates}
    assert set(entries) == {"uv", "npm"}

    uv_entry = entries["uv"]
    assert uv_entry["directory"] == "/"
    assert uv_entry["schedule"]["interval"] == "weekly"
    assert uv_entry["open-pull-requests-limit"] == 1
    assert uv_entry["allow"] == [
        {
            "dependency-type": "direct",
            "update-types": [
                "version-update:semver-minor",
            ],
        }
    ]
    assert uv_entry["labels"] == ["backend", "dependencies"]
    assert uv_entry["groups"]["uv-all-updates"]["applies-to"] == "version-updates"
    assert uv_entry["groups"]["uv-all-updates"]["update-types"] == ["minor"]
    assert uv_entry["groups"]["uv-all-updates"]["patterns"] == ["*"]

    npm_entry = entries["npm"]
    assert npm_entry["directory"] == "/web"
    assert npm_entry["schedule"]["interval"] == "weekly"
    assert npm_entry["open-pull-requests-limit"] == 2
    assert npm_entry["allow"] == [
        {
            "dependency-type": "production",
            "update-types": [
                "version-update:semver-minor",
            ],
        },
        {
            "dependency-type": "development",
            "update-types": [
                "version-update:semver-minor",
            ],
        },
    ]
    assert npm_entry["commit-message"]["prefix"] == "deps(web)"
    assert npm_entry["labels"] == ["frontend", "dependencies"]
    assert npm_entry["groups"]["web-runtime"]["applies-to"] == "version-updates"
    assert npm_entry["groups"]["web-runtime"]["dependency-type"] == "production"
    assert npm_entry["groups"]["web-runtime"]["update-types"] == ["minor"]
    assert npm_entry["groups"]["web-runtime"]["patterns"] == ["*"]
    assert npm_entry["groups"]["web-tooling"]["applies-to"] == "version-updates"
    assert npm_entry["groups"]["web-tooling"]["dependency-type"] == "development"
    assert npm_entry["groups"]["web-tooling"]["update-types"] == ["minor"]
    assert npm_entry["groups"]["web-tooling"]["patterns"] == ["*"]


def test_backend_theme_preferences_match_frontend_theme_options() -> None:
    assert SUPPORTED_THEMES == _extract_frontend_available_themes()


def test_dependency_scripts_keep_separate_scopes() -> None:
    assert 'source "${SCRIPT_DIR}/load_local_env.sh"' in DOCTOR_TEXT
    assert 'load_local_env "${REPO_ROOT}/.env"' in DOCTOR_TEXT
    assert "clean_build_artifacts()" in DOCTOR_TEXT
    assert "rm -rf build dist src/*.egg-info" in DOCTOR_TEXT
    assert "[doctor] clean build artifacts after validation" in DOCTOR_TEXT
    assert any(
        "uv sync --extra dev --extra web --extra postgres --frozen" in line
        for line in DOCTOR_COMMANDS
    )
    assert any(
        "uv export --format requirements.txt --all-extras --no-dev --locked" in line
        for line in DOCTOR_COMMANDS
    )
    assert any('uv run pytest -m "not integration"' in line for line in DOCTOR_COMMANDS)
    assert not any("uv pip list --outdated" in line for line in DOCTOR_COMMANDS)
    assert any("uv run pip-audit" in line for line in DOCTOR_COMMANDS)
    assert any("uv build --no-sources" in line for line in DOCTOR_COMMANDS)
    assert any("uv pip list --outdated" in line for line in DEPENDENCY_HEALTH_COMMANDS)
    assert any("uv run pip-audit" in line for line in DEPENDENCY_HEALTH_COMMANDS)
    assert not any("uv run pytest" in line for line in DEPENDENCY_HEALTH_COMMANDS)
    assert any("npm ci" in line for line in WEB_DEPENDENCY_HEALTH_COMMANDS)
    assert any("npm outdated --long || true" in line for line in WEB_DEPENDENCY_HEALTH_COMMANDS)
    assert any("npm audit --audit-level=low" in line for line in WEB_DEPENDENCY_HEALTH_COMMANDS)
    assert not any("uv " in line for line in WEB_DEPENDENCY_HEALTH_COMMANDS)
    assert any("npm ci" in line for line in WEB_VALIDATE_COMMANDS)
    assert any("npm audit --audit-level=high" in line for line in WEB_VALIDATE_COMMANDS)


def test_dependency_review_workflow_audits_backend_and_frontend_dependencies() -> None:
    jobs = DEPENDENCY_REVIEW_WORKFLOW["jobs"]
    assert set(jobs) == {"python-dependency-health", "web-dependency-health"}

    python_steps = _workflow_job_steps(DEPENDENCY_REVIEW_WORKFLOW, "python-dependency-health")
    python_run_steps = [step["run"] for step in python_steps if "run" in step]
    assert "bash ./scripts/dependency_health.sh" in python_run_steps

    web_steps = _workflow_job_steps(DEPENDENCY_REVIEW_WORKFLOW, "web-dependency-health")
    web_run_steps = [step["run"] for step in web_steps if "run" in step]
    assert "bash ./scripts/web_dependency_health.sh" in web_run_steps
    setup_node_step = next(
        step for step in web_steps if step.get("uses") == "actions/setup-node@v6"
    )
    assert setup_node_step["with"]["cache"] == "npm"
    assert setup_node_step["with"]["cache-dependency-path"] == "web/package-lock.json"


def test_frontend_dependency_audit_workflow_creates_non_force_fix_prs() -> None:
    assert FRONTEND_DEPENDENCY_AUDIT_WORKFLOW["permissions"] == {
        "contents": "write",
        "pull-requests": "write",
    }

    steps = _workflow_job_steps(FRONTEND_DEPENDENCY_AUDIT_WORKFLOW, "frontend-dependency-audit")
    run_steps = [step["run"] for step in steps if "run" in step]
    joined_run_steps = "\n".join(run_steps)
    assert "npm audit --json > /tmp/web-npm-audit.json" in joined_run_steps
    assert "npm audit fix --package-lock-only" in joined_run_steps
    assert "npm audit --audit-level=high" in joined_run_steps
    assert "--force" not in joined_run_steps

    verification_step = next(
        step
        for step in steps
        if step.get("name") == "Verify no high-severity vulnerabilities remain"
    )
    assert verification_step["if"] == "always()"
    assert verification_step["run"] == "npm audit --audit-level=high"

    create_pr_step = next(
        step for step in steps if step.get("uses") == "peter-evans/create-pull-request@v8"
    )
    create_pr_inputs = create_pr_step["with"]
    assert create_pr_inputs["base"] == "main"
    assert create_pr_inputs["branch"] == "chore/web-npm-audit-fix"
    assert create_pr_inputs["draft"] is True
    assert create_pr_inputs["title"] == "chore(web): apply npm audit fix updates"
    assert create_pr_inputs["commit-message"] == "chore(web): apply npm audit fix updates"
    assert "#133" not in create_pr_inputs["body"]
    assert create_pr_inputs["add-paths"].splitlines() == [
        "web/package-lock.json",
        "web/package.json",
    ]
    assert "labels" not in create_pr_inputs


def test_dead_code_scan_is_part_of_the_default_validation_gate() -> None:
    repo_hooks = PRE_COMMIT_CONFIG["repos"]
    assert isinstance(repo_hooks, list)
    local_repo = next(repo for repo in repo_hooks if repo["repo"] == "local")
    hook_ids = {hook["id"] for hook in local_repo["hooks"]}
    assert "dead-code" in hook_ids
    assert any("uv run pre-commit run --all-files" in line for line in DOCTOR_COMMANDS)
    assert any('uv run pytest -m "not integration"' in line for line in DOCTOR_COMMANDS)
    assert any("bash ./scripts/integration_tests.sh" in line for line in DOCTOR_COMMANDS)
    assert (
        'FRAMEWORK_IGNORE_NAMES="down_revision,branch_labels,depends_on,downgrade,'
        'pytestmark"' in DEAD_CODE_CHECK_TEXT
    )
    assert '--ignore-names "${FRAMEWORK_IGNORE_NAMES}"' in DEAD_CODE_CHECK_TEXT


def test_locale_catalog_sync_is_part_of_the_default_validation_gate() -> None:
    repo_hooks = PRE_COMMIT_CONFIG["repos"]
    assert isinstance(repo_hooks, list)
    local_repo = next(repo for repo in repo_hooks if repo["repo"] == "local")
    hook_entries = {hook["id"]: hook["entry"] for hook in local_repo["hooks"]}
    assert hook_entries["locale-catalog-sync"] == "uv run python scripts/check_locale_catalog.py"


def test_validate_workflow_runs_real_cli_integration_tests() -> None:
    quality_gate_run_steps = [
        step["run"] for step in QUALITY_GATE_STEPS if isinstance(step, dict) and "run" in step
    ]
    assert any("bash ./scripts/doctor.sh" in run for run in quality_gate_run_steps)

    integration_run_step = next(
        step for step in INTEGRATION_JOB_STEPS if step.get("name") == "Run CLI integration tests"
    )
    integration_env = integration_run_step["env"]
    assert "LIFEOS_TEST_DATABASE_URL" in integration_env
    database_url = integration_env["LIFEOS_TEST_DATABASE_URL"]
    assert "127.0.0.1:5432" in database_url
    assert "lifeos_test" in database_url
    assert integration_run_step["run"] == "bash ./scripts/integration_tests.sh"


def test_integration_tests_require_an_explicit_test_database_url() -> None:
    script_text = Path("scripts/integration_tests.sh").read_text()
    assert "LIFEOS_RUN_INTEGRATION" not in script_text
    assert "LIFEOS_TEST_DATABASE_URL:-" in script_text
    assert "exit 3" in script_text
    assert "uv sync --extra dev --extra web --extra postgres --frozen" in script_text
    assert "uv run pytest -m integration tests/test_cli_integration_*.py" in script_text
    assert 'source "${SCRIPT_DIR}/load_local_env.sh"' in script_text
    assert 'load_local_env "${REPO_ROOT}/.env"' in script_text
    support_text = Path("tests/cli_integration_support.py").read_text()
    assert "normalize_integration_database_url" in support_text
    assert 'database_name = f"{database_name}_test"' in support_text
    assert "DatabaseSettings.from_env" not in support_text
    assert 'schema = f"lifeos_test_{uuid4().hex[:12]}"' in Path("tests/conftest.py").read_text()


def test_load_local_env_script_exports_local_env_files() -> None:
    assert "load_local_env()" in LOAD_LOCAL_ENV_TEXT
    assert 'local env_file="${1:-.env}"' in LOAD_LOCAL_ENV_TEXT
    assert '. "$env_file"' in LOAD_LOCAL_ENV_TEXT
    assert "set -a" in LOAD_LOCAL_ENV_TEXT
    assert "set +a" in LOAD_LOCAL_ENV_TEXT


def test_gitignore_keeps_local_env_files_untracked() -> None:
    assert "\n.env\n" in GITIGNORE_TEXT
    assert "\n.env.local\n" in GITIGNORE_TEXT


def test_vulture_whitelist_keeps_intentional_framework_symbols() -> None:
    for symbol in (
        "type_annotation_map",
        "isolated_runtime_locale",
        "_use_stable_note_timezone",
        "configured_time_preferences",
    ):
        assert symbol in VULTURE_WHITELIST_TEXT


def test_json_locale_catalogs_are_complete() -> None:
    locales_dir = Path("src/lifeos_cli/locales")
    locale_names = sorted(path.name for path in locales_dir.iterdir() if path.is_dir())
    catalog_paths = sorted(locales_dir.glob("*/*.json"))
    grouped_catalog_paths: dict[str, dict[str, Path]] = {}
    for catalog_path in catalog_paths:
        grouped_catalog_paths.setdefault(catalog_path.name, {})[catalog_path.parent.name] = (
            catalog_path
        )

    assert catalog_paths
    assert "en" in locale_names

    for catalog_name, locale_paths in grouped_catalog_paths.items():
        assert set(locale_paths) == set(locale_names), catalog_name
        default_catalog = json.loads(locale_paths["en"].read_text(encoding="utf-8"))
        default_keys = _flatten_json_catalog_keys(default_catalog)
        assert default_keys
        assert all(default_keys.values())

        for locale_name, catalog_path in locale_paths.items():
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            keys_to_values = _flatten_json_catalog_keys(catalog)
            assert set(keys_to_values) == set(default_keys), (catalog_name, locale_name)
            assert all(keys_to_values.values()), (catalog_name, locale_name)


def test_zh_hans_json_catalogs_keep_internal_entity_terms_in_english() -> None:
    catalog_paths = sorted(Path("src/lifeos_cli/locales/zh_Hans").glob("*.json"))
    entries: list[tuple[str, str, str]] = []
    for catalog_path in catalog_paths:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        entries.extend(
            (catalog_path.name, key, value)
            for key, value in _flatten_json_catalog_keys(catalog).items()
            if value
        )

    banned_terms = (
        "领域",
        "愿景",
        "任务",
        "笔记",
        "标签",
        "事件",
        "日程",
        "时间记录",
        "习惯执行记录",
        "习惯",
        "人员",
    )

    offenders = [
        (catalog_name, key, value)
        for catalog_name, key, value in entries
        if any(term in value for term in banned_terms)
    ]

    assert offenders == []
