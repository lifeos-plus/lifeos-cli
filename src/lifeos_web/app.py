"""FastAPI application factory for the local LifeOS Web service."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lifeos_web.deps import LIFEOS_SESSION_STATE_KEY
from lifeos_web.routers import (
    areas,
    finance,
    habits,
    health,
    notes,
    person,
    planned_events,
    preferences,
    stats,
    tags,
    tasks,
    timelog_templates,
    timelogs,
    visions,
)

API_PREFIX = "/api/v1"
SPA_FALLBACK_EXCLUDED_SEGMENTS = frozenset({"api", "assets", "health"})


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


def create_app(*, static_dir: Path | None = None) -> FastAPI:
    """Create the local LifeOS Web FastAPI application."""
    app = FastAPI(
        title="LifeOS Web UI",
        version="0.1.0",
        description="Local-first Web API for lifeos-cli data.",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CommitSessionMiddleware)
    app.include_router(health.router)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(visions.router, prefix=API_PREFIX)
    app.include_router(habits.router, prefix=API_PREFIX)
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
