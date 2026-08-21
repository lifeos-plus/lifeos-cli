"""Top-level parser and CLI entrypoint assembly."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from functools import partial
from importlib.metadata import PackageNotFoundError, metadata
from typing import cast

from pyfiglet import figlet_format
from sqlalchemy.exc import SQLAlchemyError

from lifeos_cli.application.package_metadata import get_installed_package_version
from lifeos_cli.cli_support.help_utils import CompactSubcommandHelpFormatter, build_epilog
from lifeos_cli.cli_support.resources.area.parser import build_area_parser
from lifeos_cli.cli_support.resources.body_measurement.parser import build_body_measurement_parser
from lifeos_cli.cli_support.resources.data.parser import build_data_parser
from lifeos_cli.cli_support.resources.event.parser import build_event_parser
from lifeos_cli.cli_support.resources.finance.parser import build_finance_parser
from lifeos_cli.cli_support.resources.habit.parser import build_habit_parser
from lifeos_cli.cli_support.resources.habit_action.parser import build_habit_action_parser
from lifeos_cli.cli_support.resources.menstrual.parser import build_menstrual_parser
from lifeos_cli.cli_support.resources.menstrual_factor.parser import (
    build_menstrual_factor_parser,
)
from lifeos_cli.cli_support.resources.note.parser import build_note_parser
from lifeos_cli.cli_support.resources.person.parser import build_person_parser
from lifeos_cli.cli_support.resources.planning.parser import build_planning_parser
from lifeos_cli.cli_support.resources.schedule.parser import build_schedule_parser
from lifeos_cli.cli_support.resources.sleep.parser import build_sleep_parser
from lifeos_cli.cli_support.resources.tag.parser import build_tag_parser
from lifeos_cli.cli_support.resources.task.parser import build_task_parser
from lifeos_cli.cli_support.resources.timelog.parser import build_timelog_parser
from lifeos_cli.cli_support.resources.vision.parser import build_vision_parser
from lifeos_cli.cli_support.runtime_utils import print_database_runtime_error
from lifeos_cli.cli_support.system.config_commands import build_config_parser
from lifeos_cli.cli_support.system.db_commands import build_db_parser
from lifeos_cli.cli_support.system.init_commands import build_init_parser
from lifeos_cli.cli_support.system.web_commands import build_web_parser
from lifeos_cli.config import ConfigurationError
from lifeos_cli.i18n import cli_message as _
from lifeos_cli.i18n import configure_argparse_translations

CLI_BRAND_TEXT = "LifeOS"
CLI_BRAND_FONT = "ansi_shadow"
PROJECT_REPOSITORY_URL_FALLBACK = "https://github.com/lifeos-plus/lifeos-cli"
PROJECT_ISSUES_URL_FALLBACK = "https://github.com/lifeos-plus/lifeos-cli/issues"
HELP_FLAGS = frozenset({"-h", "--help"})

ResourceBuilder = Callable[
    ["argparse._SubParsersAction[argparse.ArgumentParser]"],
    None,
]

RESOURCE_BUILDERS: tuple[tuple[str, ResourceBuilder], ...] = (
    ("init", build_init_parser),
    ("config", build_config_parser),
    ("db", build_db_parser),
    ("web", build_web_parser),
    ("data", build_data_parser),
    ("area", build_area_parser),
    ("body-measurement", build_body_measurement_parser),
    ("event", build_event_parser),
    ("finance", build_finance_parser),
    ("schedule", build_schedule_parser),
    ("tag", build_tag_parser),
    ("person", build_person_parser),
    ("vision", build_vision_parser),
    ("task", build_task_parser),
    ("planning", build_planning_parser),
    ("timelog", build_timelog_parser),
    ("habit", build_habit_parser),
    ("habit-action", build_habit_action_parser),
    ("menstrual", build_menstrual_parser),
    ("menstrual-factor", build_menstrual_factor_parser),
    ("note", build_note_parser),
    ("sleep", build_sleep_parser),
)


class TopLevelArgumentParser(argparse.ArgumentParser):
    """Strip the generated usage line from the top-level help output only."""

    def format_help(self) -> str:
        help_text = super().format_help()
        lines = help_text.splitlines(keepends=True)
        if lines and (
            lines[0].startswith("usage:")
            or lines[0].startswith("用法：")
            or lines[0].startswith("usage：")
        ):
            return "".join(lines[1:]).lstrip("\n")
        return help_text


def get_subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    """Return the parser's subparser action when one exists."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def normalize_help_request(
    parser: argparse.ArgumentParser,
    argv: Sequence[str],
) -> list[str]:
    """Rewrite misplaced help flags so subcommand help remains reachable."""
    normalized: list[str] = []
    tokens = list(argv)
    active_parser = parser
    index = 0
    pending_help = False

    while index < len(tokens):
        subparsers_action = get_subparsers_action(active_parser)
        if subparsers_action is None:
            break

        current = tokens[index]
        if (
            current in HELP_FLAGS
            and index + 1 < len(tokens)
            and tokens[index + 1] in subparsers_action.choices
        ):
            pending_help = True
            index += 1
            current = tokens[index]

        normalized.append(current)
        index += 1

        next_parser = subparsers_action.choices.get(current)
        if next_parser is None:
            break
        active_parser = next_parser

        next_subparsers_action = get_subparsers_action(active_parser)
        next_token = tokens[index] if index < len(tokens) else None
        if pending_help and (
            next_subparsers_action is None
            or next_token is None
            or next_token.startswith("-")
            or next_token not in next_subparsers_action.choices
        ):
            normalized.append("--help")
            pending_help = False

    if pending_help:
        normalized.append("--help")
    normalized.extend(tokens[index:])
    return normalized


def get_project_urls() -> tuple[str, str]:
    """Return repository and issue tracker URLs from package metadata when available."""
    repository_url = PROJECT_REPOSITORY_URL_FALLBACK
    issues_url = PROJECT_ISSUES_URL_FALLBACK
    try:
        distribution_metadata = metadata("lifeos-cli")
    except PackageNotFoundError:
        return repository_url, issues_url
    for project_url in distribution_metadata.get_all("Project-URL", []):
        label, separator, url = project_url.partition(",")
        if not separator:
            continue
        normalized_label = label.strip().lower()
        normalized_url = url.strip()
        if normalized_label == "repository":
            repository_url = normalized_url
        elif normalized_label == "issues":
            issues_url = normalized_url
    return repository_url, issues_url


def build_cli_brand_banner() -> str:
    """Render the CLI brand banner with the canonical shadow font."""
    return cast(str, figlet_format(CLI_BRAND_TEXT, font=CLI_BRAND_FONT)).rstrip("\n")


def get_cli_brand_banner_width() -> int:
    """Return the widest banner line length for help formatter sizing."""
    banner = build_cli_brand_banner()
    return max((len(line) for line in banner.splitlines()), default=0)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    configure_argparse_translations()
    repository_url, _issues_url = get_project_urls()
    brand_banner = build_cli_brand_banner()
    formatter_class = partial(
        CompactSubcommandHelpFormatter,
        width=max(100, get_cli_brand_banner_width() + 2),
    )
    parser = TopLevelArgumentParser(
        prog="lifeos",
        description=(
            brand_banner
            + "\n\n"
            + f"repo: {repository_url}\n"
            + "uv tool install --upgrade lifeos-cli\n\n"
            + _("app.parser.command_grammar")
            + "\n"
            + "  lifeos <resource> <action> [arguments] [options]"
        ),
        epilog=build_epilog(
            examples=(
                "lifeos init",
                "lifeos config show",
                "lifeos schedule show",
                "lifeos task list",
                'lifeos note add "Capture an idea"',
            ),
            notes=(
                _(
                    "app.parser.use_lifeos_resource_help_and_lifeos_resource_action_help_as_primary_command"
                ),
                _("app.parser.run_lifeos_init_to_initialize_lifeos_before_getting_started"),
                _(
                    "app.parser.welcome_bug_reports_and_suggestions_through_https_github_com_lifeos_plus_lifeos_cli"
                ),
            ),
        ),
        formatter_class=formatter_class,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {get_installed_package_version()}",
        help=_("app.parser.show_program_version_and_exit"),
    )
    subparsers = parser.add_subparsers(
        dest="resource",
        title=_("app.parser.resources"),
        metavar=_("app.parser.resource"),
        parser_class=argparse.ArgumentParser,
    )
    for _resource, builder in RESOURCE_BUILDERS:
        builder(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    parsed_argv = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(normalize_help_request(parser, parsed_argv))
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return int(handler(args))
    except (ConfigurationError, SQLAlchemyError) as exc:
        return print_database_runtime_error(exc)
    except EOFError as exc:
        print(f"Initialization aborted: {exc}", file=sys.stderr)
        return 1
