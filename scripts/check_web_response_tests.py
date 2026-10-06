"""Enforce HTTP test coverage for Web API response model changes.

When a change touches ``src/lifeos_web/response_schemas`` it must also update
``tests/test_web_api_http.py`` so the affected response contracts stay
exercised through a real HTTP round trip. The comparison is scoped to the
commits on the current branch using the merge base of the base ref (``--base``,
``LIFEOS_BASE_REF``, or ``origin/main`` by default).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

RESPONSE_SCHEMA_PREFIX = "src/lifeos_web/response_schemas/"
HTTP_TEST_PATH = "tests/test_web_api_http.py"
DEFAULT_BASE_REF = "origin/main"


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _resolve_base(base_ref: str, *, strict: bool) -> str | None:
    try:
        return _git("rev-parse", "--verify", f"{base_ref}^{{commit}}")
    except subprocess.CalledProcessError:
        if strict:
            print(
                f"[web-response-test-guard] base ref {base_ref!r} could not be resolved.",
                file=sys.stderr,
            )
            raise SystemExit(2) from None
        print(
            f"[web-response-test-guard] base ref {base_ref!r} unavailable; "
            "skipping response-contract test coverage check."
        )
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="Base ref to compare against.")
    parser.add_argument("--head", default="HEAD", help="Head ref to compare.")
    args = parser.parse_args(argv)

    explicit_base = args.base or os.environ.get("LIFEOS_BASE_REF") or None
    base_ref = explicit_base or DEFAULT_BASE_REF
    base_commit = _resolve_base(base_ref, strict=explicit_base is not None)
    if base_commit is None:
        return 0

    try:
        head_commit = _git("rev-parse", "--verify", f"{args.head}^{{commit}}")
        merge_base = _git("merge-base", base_commit, head_commit)
        changed = set(_git("diff", "--name-only", merge_base, head_commit).splitlines())
    except subprocess.CalledProcessError as exc:
        print(
            f"[web-response-test-guard] git command failed while comparing changes: {exc}",
            file=sys.stderr,
        )
        return 2

    schema_changes = sorted(path for path in changed if path.startswith(RESPONSE_SCHEMA_PREFIX))
    if not schema_changes:
        print("[web-response-test-guard] no response schema changes detected.")
        return 0

    if HTTP_TEST_PATH in changed:
        print(
            "[web-response-test-guard] response schema changes are covered by an "
            f"HTTP test update in {HTTP_TEST_PATH}."
        )
        return 0

    print(
        "[web-response-test-guard] response schema changes require an HTTP test update:",
        file=sys.stderr,
    )
    for path in schema_changes:
        print(f"  - {path}", file=sys.stderr)
    print(
        f"Update {HTTP_TEST_PATH} so the changed response contracts are exercised "
        "through a real HTTP round trip.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
