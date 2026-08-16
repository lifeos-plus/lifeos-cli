#!/usr/bin/env python3
"""Execute CLI help commands and render a command reference.

The default Markdown mode runs every ``--help`` invocation and writes a
review-friendly audit report. The JSON mode introspects the parser tree and
writes a machine-readable command reference without spawning subprocesses.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from lifeos_cli.cli import build_parser
from lifeos_cli.cli_support.help_audit import (
    build_machine_readable_reference,
    collect_help_invocations,
    filter_help_invocations,
    filter_reference_commands,
    lint_help_summary_conventions,
    render_help_audit_report,
    render_machine_readable_reference,
    run_help_audit,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the help audit script."""
    parser = argparse.ArgumentParser(
        description=("Render a Markdown help audit or a machine-readable JSON command reference."),
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format: markdown audit report or JSON command reference.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Print to stdout when omitted.",
    )
    parser.add_argument(
        "--path-prefix",
        default="",
        help=(
            "Optional command subtree to audit, for example 'note' or 'timelog stats'. "
            "Leave empty to audit every parser level."
        ),
    )
    parser.add_argument(
        "--command-prefix",
        default="uv run lifeos",
        help="Executable prefix used to run help queries. Default: 'uv run lifeos'.",
    )
    parser.add_argument(
        "--check-summaries",
        action="store_true",
        help="Lint command summary conventions and exit non-zero on violations.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the CLI help audit or emit a machine-readable command reference."""
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    command_prefix = tuple(shlex.split(args.command_prefix))
    path_prefix = tuple(shlex.split(args.path_prefix))

    if args.check_summaries:
        reference = build_machine_readable_reference(build_parser())
        violations = lint_help_summary_conventions(reference)
        if violations:
            print(
                "Command summary convention violations:",
                file=sys.stderr,
            )
            for violation in violations:
                print(f"  {violation}", file=sys.stderr)
            print(
                "Remove trailing periods from command summaries in the locale catalogs.",
                file=sys.stderr,
            )
            return 1
        print("All command summaries follow the summary conventions.")
        return 0

    if args.format == "json":
        reference = build_machine_readable_reference(build_parser())
        if path_prefix:
            reference = filter_reference_commands(
                reference,
                path_prefix=path_prefix,
            )
        content = render_machine_readable_reference(reference)
        exit_code = 0
    else:
        invocations = collect_help_invocations(build_parser())
        if path_prefix:
            invocations = filter_help_invocations(invocations, path_prefix=path_prefix)
        results = run_help_audit(
            invocations,
            command_prefix=command_prefix,
            cwd=repo_root,
        )
        content = render_help_audit_report(results)
        exit_code = 0 if all(result.ok for result in results) else 1

    if args.output is None:
        sys.stdout.write(content)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Wrote CLI command reference: {args.output}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
