"""FastAPI application factory for the local LifeOS Web service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from lifeos_web.routers import (
    areas,
    finance,
    habits,
    health,
    notes,
    persons,
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


async def commit_session_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Commit the request session before the response is sent to the client.

    FastAPI runs the exit code of ``yield`` dependencies after the response is
    sent, so ``session_scope``'s teardown commit is too late for clients that
    read immediately after a write (for example the Web UI refetching a list
    right after a POST). Committing here closes that window: once a successful
    response reaches the client, the write is durable and visible to reads.
    """
    response = await call_next(request)
    session = getattr(request.state, "lifeos_session", None)
    if session is not None and response.status_code < 400:
        await session.commit()
    return response


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
    app.middleware("http")(commit_session_middleware)
    app.include_router(health.router)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(visions.router, prefix=API_PREFIX)
    app.include_router(habits.router, prefix=API_PREFIX)
    app.include_router(notes.router, prefix=API_PREFIX)
    app.include_router(timelogs.router, prefix=API_PREFIX)
    app.include_router(timelog_templates.router, prefix=API_PREFIX)
    app.include_router(persons.router, prefix=API_PREFIX)
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
