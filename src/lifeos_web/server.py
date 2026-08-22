"""Runtime entrypoints for serving LifeOS Web locally."""

from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

from lifeos_cli.config import (
    ensure_database_driver_available,
    ensure_database_url_storage_ready,
    get_database_settings,
)
from lifeos_cli.i18n import cli_message as _

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def is_loopback_host(host: str) -> bool:
    """Return whether binding ``host`` targets the loopback interface."""
    normalized = host.strip().lower()
    if normalized in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def warn_if_non_loopback_binding(host: str) -> None:
    """Warn on stderr when the unauthenticated Web service binds beyond loopback."""
    if is_loopback_host(host):
        return
    print(
        _("system.web_commands.non_loopback_binding_warning").format(host=host),
        file=sys.stderr,
    )


def preflight_database_runtime() -> None:
    """Fail before serving HTTP when the configured database runtime is incomplete."""
    database_url = get_database_settings().require_database_url()
    ensure_database_driver_available(database_url)
    ensure_database_url_storage_ready(database_url)


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    reload: bool = False,
    static_dir: Path | None = None,
    docs: bool = False,
) -> None:
    """Run the local Web service with uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised by users without [web]
        raise RuntimeError(
            "LifeOS Web dependencies are not installed. Install with `lifeos-cli[web]`."
        ) from exc

    preflight_database_runtime()

    warn_if_non_loopback_binding(host)

    if static_dir is None and not docs:
        uvicorn.run("lifeos_web.app:app", host=host, port=port, reload=reload)
        return

    if static_dir is not None or docs:
        from lifeos_web.app import create_app

        uvicorn.run(
            create_app(static_dir=static_dir, docs_enabled=docs),
            host=host,
            port=port,
            reload=reload,
        )
        return
