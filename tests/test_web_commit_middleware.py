"""Tests for the commit-before-response Web API middleware."""

from __future__ import annotations

import asyncio

from starlette.types import Message, Receive, Scope, Send

from lifeos_web.app import CommitSessionMiddleware, create_app


class FakeSession:
    """Stand-in for an AsyncSession that records finalization ordering."""

    def __init__(self) -> None:
        self.log: list[str] = []
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1
        self.log.append("commit")

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.log.append("rollback")


def _run_middleware(
    *,
    session: FakeSession | None,
    status: int,
    scope_type: str = "http",
) -> tuple[list[str], FakeSession | None]:
    """Drive the middleware through a canned response and capture ordering."""
    log: list[str] = []
    if session is not None:
        session.log = log
    scope: Scope = {"type": scope_type, "state": {}}
    if session is not None:
        scope["state"]["lifeos_session"] = session

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        log.append(f"send:{message['type']}")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": status})
        await send({"type": "http.response.body", "body": b""})

    asyncio.run(CommitSessionMiddleware(app)(scope, receive, send))
    return log, session


def test_commit_runs_before_response_start_is_sent() -> None:
    session = FakeSession()

    log, returned_session = _run_middleware(session=session, status=200)

    assert returned_session is not None
    assert returned_session.commits == 1
    assert log.index("commit") < log.index("send:http.response.start")


def test_rollback_for_error_response() -> None:
    session = FakeSession()

    log, returned_session = _run_middleware(session=session, status=500)

    assert returned_session is not None
    assert returned_session.commits == 0
    assert returned_session.rollbacks == 1
    assert log.index("rollback") < log.index("send:http.response.start")


def test_commit_skipped_when_no_session_registered() -> None:
    log, _ = _run_middleware(session=None, status=200)

    assert "commit" not in log
    assert "rollback" not in log


def test_non_http_scopes_pass_through() -> None:
    log: list[str] = []

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        log.append(f"send:{message['type']}")

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "lifespan.startup.complete"})

    asyncio.run(
        CommitSessionMiddleware(app)(
            {"type": "lifespan", "state": {}},
            receive,
            send,
        )
    )

    assert log == ["send:lifespan.startup.complete"]


def test_create_app_registers_commit_middleware() -> None:
    middleware_classes = [middleware.cls for middleware in create_app().user_middleware]
    assert CommitSessionMiddleware in middleware_classes


def test_middleware_is_async_callable() -> None:
    assert asyncio.iscoroutinefunction(CommitSessionMiddleware.__call__)
