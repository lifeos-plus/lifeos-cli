"""Structured argparse help helpers for CLI resources."""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from lifeos_cli.i18n import cli_message as _
from lifeos_cli.i18n import keyed_message


@dataclass(frozen=True)
class HelpContent:
    """Structured help content for CLI parsers."""

    summary: str
    description: str
    examples: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class CompactSubcommandHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Render subcommand groups without a duplicated metavar heading."""

    def __init__(
        self,
        prog: str,
        indent_increment: int = 2,
        max_help_position: int = 48,
        width: int | None = None,
    ) -> None:
        """Use a wider default layout so help text wraps less aggressively."""
        terminal_width = shutil.get_terminal_size(fallback=(100, 24)).columns
        effective_width = max(100, terminal_width) if width is None else width
        super().__init__(
            prog,
            indent_increment=indent_increment,
            max_help_position=max_help_position,
            width=effective_width,
        )

    def _format_action(self, action: argparse.Action) -> str:
        if isinstance(action, argparse._SubParsersAction):
            self._indent()
            try:
                subactions = list(action._get_subactions())
                previous_max_length = self._action_max_length
                subaction_max_length = max(
                    (
                        self._current_indent + len(self._format_action_invocation(subaction))
                        for subaction in subactions
                    ),
                    default=0,
                )
                self._action_max_length = max(previous_max_length, subaction_max_length)
                return self._join_parts(
                    [self._format_action(subaction) for subaction in subactions]
                )
            finally:
                self._action_max_length = previous_max_length
                self._dedent()
        return super()._format_action(action)


def build_epilog(*, examples: tuple[str, ...] = (), notes: tuple[str, ...] = ()) -> str | None:
    """Build an argparse epilog from examples and notes."""
    sections: list[str] = []
    if examples:
        example_lines = "\n".join(f"  {example}" for example in examples)
        sections.append(f"{_('common.help.examples')}:\n{example_lines}")
    if notes:
        note_lines = "\n".join(f"  {note}" for note in notes)
        sections.append(f"{_('common.help.notes')}:\n{note_lines}")
    if not sections:
        return None
    return "\n\n".join(sections)


def help_message(key: str) -> str:
    """Return one CLI help message from the keyed help catalog."""
    return keyed_message("cli_help", key)


def make_help_handler(parser: argparse.ArgumentParser) -> Callable[[argparse.Namespace], int]:
    """Return a handler that prints parser help for resource-level commands."""

    def _handler(_: argparse.Namespace) -> int:
        parser.print_help()
        return 0

    return _handler


def add_documented_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    *,
    help_content: HelpContent,
) -> argparse.ArgumentParser:
    """Add a parser with structured description and examples."""
    parser = subparsers.add_parser(
        name,
        help=help_content.summary,
        description=help_content.description,
        epilog=build_epilog(examples=help_content.examples, notes=help_content.notes),
        formatter_class=CompactSubcommandHelpFormatter,
    )
    # Keep the structured content on the parser so machine-readable command
    # references can introspect the tree without re-parsing rendered text.
    cast(Any, parser)._lifeos_help_content = help_content
    return parser


def add_documented_help_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    *,
    help_content: HelpContent,
) -> argparse.ArgumentParser:
    """Add a documented parser that defaults to printing its own help output."""
    parser = add_documented_parser(subparsers, name, help_content=help_content)
    parser.set_defaults(handler=make_help_handler(parser))
    return parser
