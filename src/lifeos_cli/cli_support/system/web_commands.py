"""Local Web service CLI commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from lifeos_cli.cli_support.help_utils import (
    HelpContent,
    add_documented_help_parser,
    add_documented_parser,
)
from lifeos_cli.i18n import cli_message as _


def run_web_serve(args: argparse.Namespace) -> int:
    """Serve the local LifeOS Web application."""
    from lifeos_web.server import serve

    serve(
        host=args.host,
        port=args.port,
        reload=args.reload,
        static_dir=Path(args.static_dir) if args.static_dir else None,
    )
    return 0


def build_web_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Build the local Web command tree."""
    web_parser = add_documented_help_parser(
        subparsers,
        "web",
        help_content=HelpContent(
            summary=_("system.web_commands.run_optional_local_web_api"),
            description=(_("system.web_commands.run_local_lifeos_web_service")),
            examples=("lifeos web serve", "lifeos web serve --port 8765"),
            notes=(_("system.web_commands.install_optional_web_dependencies"),),
        ),
    )
    web_subparsers = web_parser.add_subparsers(
        dest="web_command",
        title=_("common.messages.actions"),
        metavar=_("common.messages.action"),
    )
    serve_parser = add_documented_parser(
        web_subparsers,
        "serve",
        help_content=HelpContent(
            summary=_("system.web_commands.serve_local_web_api"),
            description=_("system.web_commands.start_fastapi_server_bound_to_localhost"),
            examples=(
                "lifeos web serve",
                "lifeos web serve --host 127.0.0.1 --port 8765",
                "lifeos web serve --static-dir <path-to>/lifeos-web/dist",
            ),
            notes=(_("system.web_commands.use_vite_during_frontend_development"),),
        ),
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=_("system.web_commands.bind_host"),
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help=_("system.web_commands.bind_port"),
    )
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help=_("system.web_commands.enable_uvicorn_reload"),
    )
    serve_parser.add_argument(
        "--static-dir",
        help=_("system.web_commands.serve_built_frontend_directory"),
    )
    serve_parser.set_defaults(handler=run_web_serve)
