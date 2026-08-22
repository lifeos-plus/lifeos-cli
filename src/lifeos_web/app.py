"""FastAPI application factory for the local LifeOS Web service."""

from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lifeos_web.deps import LIFEOS_SESSION_STATE_KEY
from lifeos_web.routers import (
    areas,
    body_measurements,
    finance,
    habits,
    health,
    menstrual,
    notes,
    person,
    planned_events,
    preferences,
    sleep,
    stats,
    tags,
    tasks,
    timelog_templates,
    timelogs,
    visions,
)

API_PREFIX = "/api/v1"
SPA_FALLBACK_EXCLUDED_SEGMENTS = frozenset({"api", "assets", "healthy"})

DEFAULT_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DEFAULT_CORS_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")
DEFAULT_MAX_BODY_BYTES = 1_048_576
DEFAULT_RATE_LIMIT_PER_MINUTE = 300
ALLOWED_HOSTS_ENV = "LIFEOS_WEB_ALLOWED_HOSTS"
MAX_BODY_BYTES_ENV = "LIFEOS_WEB_MAX_BODY_BYTES"
RATE_LIMIT_PER_MINUTE_ENV = "LIFEOS_WEB_RATE_LIMIT_PER_MINUTE"


def _header_value(scope: Scope, name: bytes) -> str | None:
    """Return one decoded HTTP header value from the ASGI scope."""
    for header_name, value in scope.get("headers") or []:
        if header_name == name:
            return value.decode("latin-1")
    return None


def _normalize_netloc(url: str) -> str:
    """Return the lower-cased netloc of one URL, or an empty string."""
    try:
        return (urlsplit(url).netloc or "").lower()
    except ValueError:
        return ""


def _env_int(name: str, default: int) -> int:
    """Read one optional integer environment override."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolved_allowed_hosts() -> list[str]:
    """Return loopback hosts plus any comma-separated environment override."""
    hosts = set(DEFAULT_ALLOWED_HOSTS)
    for host in os.environ.get(ALLOWED_HOSTS_ENV, "").split(","):
        normalized = host.strip().lower()
        if normalized:
            hosts.add(normalized)
    return sorted(hosts)


class OriginValidationMiddleware:
    """Reject requests whose Origin is neither same-origin nor allowlisted.

    Browsers attach an ``Origin`` header to cross-origin and same-origin
    requests. Non-browser clients usually omit it and are unaffected. This
    middleware complements the CORS allowlist as a defense-in-depth boundary
    against DNS rebinding and cross-site request forgery once the local API is
    served from a dedicated origin.
    """

    def __init__(self, app: ASGIApp, *, allowed_origins: tuple[str, ...]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        origin = _header_value(scope, b"origin")
        if origin is None:
            await self.app(scope, receive, send)
            return
        host = _header_value(scope, b"host")
        same_origin = bool(host) and _normalize_netloc(origin) == host.lower()
        if origin in self.allowed_origins or same_origin:
            await self.app(scope, receive, send)
            return
        response = PlainTextResponse("Origin not allowed", status_code=403)
        await response(scope, receive, send)


class _BodyTooLarge(Exception):
    """Raised when a streamed request body exceeds the configured limit."""


class RequestBodySizeLimitMiddleware:
    """Reject request bodies larger than ``max_bytes``.

    The limit is enforced both from ``Content-Length`` (when present) and by
    counting bytes received for streamed or chunked bodies.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        content_length = _header_value(scope, b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body") or b"")
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = PlainTextResponse("Request body too large", status_code=413)
        await response(scope, receive, send)


class RateLimitMiddleware:
    """Apply a lightweight per-client sliding-window limit to API requests."""

    def __init__(self, app: ASGIApp, *, limit_per_minute: int) -> None:
        self.app = app
        self.limit_per_minute = limit_per_minute
        self._window_seconds = 60.0
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path == "/healthy" or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        key = client[0] if client else "unknown"
        now = time.monotonic()
        async with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self._window_seconds:
                hits.popleft()
            if len(hits) >= self.limit_per_minute:
                response = PlainTextResponse("Rate limit exceeded", status_code=429)
                await response(scope, receive, send)
                return
            hits.append(now)
        await self.app(scope, receive, send)


def _is_spa_fallback_excluded_path(path: str) -> bool:
    first_segment = path.lstrip("/").split("/", 1)[0]
    return first_segment in SPA_FALLBACK_EXCLUDED_SEGMENTS


class SPAStaticFiles(StaticFiles):
    """Serve index.html for client-side application routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if (
                exc.status_code == 404
                and "." not in Path(path).name
                and not _is_spa_fallback_excluded_path(path)
            ):
                response = await super().get_response("index.html", scope)
            else:
                raise
        response.headers["Cache-Control"] = "no-store"
        return response


class CommitSessionMiddleware:
    """Commit the request session before the response start event is sent.

    FastAPI runs the exit code of ``yield`` dependencies after the response is
    sent, so ``session_scope``'s teardown commit is too late for clients that
    read immediately after a write (for example the Web UI refetching a list
    right after a POST). Committing when the response starts closes that
    window: the client cannot receive any response byte before the write is
    durable and visible to reads. Error responses are rolled back before they
    are sent, and failed commits surface as a 5xx instead of a misleading 2xx.

    This middleware is the sole transaction finalizer for Web request
    sessions; ``get_db_session`` registers the session on the request scope
    and never commits it itself.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_commit(message: Message) -> None:
            if message["type"] == "http.response.start":
                status = message.get("status", 200)
                session = scope.setdefault("state", {}).get(LIFEOS_SESSION_STATE_KEY)
                if session is not None:
                    if status < 400:
                        await session.commit()
                    else:
                        await session.rollback()
            await send(message)

        await self.app(scope, receive, send_with_commit)


def create_app(
    *,
    static_dir: Path | None = None,
    docs_enabled: bool = False,
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    """Create the local LifeOS Web FastAPI application."""
    resolved_hosts = _resolved_allowed_hosts() if allowed_hosts is None else allowed_hosts
    resolved_hosts = [host.strip().lower() for host in resolved_hosts]
    max_body_bytes = _env_int(MAX_BODY_BYTES_ENV, DEFAULT_MAX_BODY_BYTES)
    rate_limit_per_minute = _env_int(
        RATE_LIMIT_PER_MINUTE_ENV,
        DEFAULT_RATE_LIMIT_PER_MINUTE,
    )
    docs_url = f"{API_PREFIX}/docs" if docs_enabled else None
    openapi_url = f"{API_PREFIX}/openapi.json" if docs_enabled else None
    app = FastAPI(
        title="LifeOS Web UI",
        version="0.1.0",
        description="Local-first Web API for lifeos-cli data.",
        docs_url=docs_url,
        openapi_url=openapi_url,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved_hosts)
    app.add_middleware(
        OriginValidationMiddleware,
        allowed_origins=DEFAULT_CORS_ORIGINS,
    )
    app.add_middleware(RequestBodySizeLimitMiddleware, max_bytes=max_body_bytes)
    app.add_middleware(
        RateLimitMiddleware,
        limit_per_minute=rate_limit_per_minute,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEFAULT_CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CommitSessionMiddleware)
    app.include_router(health.router)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(visions.router, prefix=API_PREFIX)
    app.include_router(habits.router, prefix=API_PREFIX)
    app.include_router(menstrual.router, prefix=API_PREFIX)
    app.include_router(menstrual.factor_router, prefix=API_PREFIX)
    app.include_router(body_measurements.router, prefix=API_PREFIX)
    app.include_router(sleep.router, prefix=API_PREFIX)
    app.include_router(notes.router, prefix=API_PREFIX)
    app.include_router(timelogs.router, prefix=API_PREFIX)
    app.include_router(timelog_templates.router, prefix=API_PREFIX)
    app.include_router(person.router, prefix=API_PREFIX)
    app.include_router(areas.router, prefix=API_PREFIX)
    app.include_router(finance.router, prefix=API_PREFIX)
    app.include_router(planned_events.router, prefix=API_PREFIX)
    app.include_router(stats.router, prefix=API_PREFIX)
    app.include_router(tags.router, prefix=API_PREFIX)
    app.include_router(preferences.router, prefix=API_PREFIX)

    resolved_static_dir = static_dir or Path(__file__).with_name("static")
    if resolved_static_dir.exists():
        app.mount("/", SPAStaticFiles(directory=resolved_static_dir, html=True), name="static")
    return app


app = create_app()
