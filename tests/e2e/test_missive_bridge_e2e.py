"""End-to-end mock baseline for the ck-missive-bridge native tool (QW-3).

Spins up a tiny aiohttp server on an ephemeral port, points
``MISSIVE_BASE_URL`` at it, and invokes ``_handle_health`` /
``_handle_get_document`` from ``tools/missive_tool.py``. The captured
requests prove that:

1. ``missive_health`` actually opens a TCP socket and emits ``GET /health``.
2. ``missive_get_document`` builds ``GET /api/v1/documents/{id}`` and
   forwards the bearer token when ``MISSIVE_API_TOKEN`` is set.
3. The handler round-trips a real JSON response back through the sync
   wrapper (``_run_async`` → asyncio.run in a worker thread).

Unlike the unit tests in ``tests/tools/test_missive_tool.py`` which patch
``_async_health`` / ``_async_get_document``, this file exercises the
aiohttp socket layer for real.

Not gated by ``-m integration`` because the mock server is in-process —
runs in any environment with aiohttp installed.
"""

import asyncio
import json
import os
import socket
import threading
from contextlib import contextmanager
from typing import Iterator, List

import pytest
from aiohttp import web


# ---------------------------------------------------------------------------
# In-process aiohttp server fixture
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _MockMissiveServer:
    """Records each request and lets tests script the next response."""

    def __init__(self) -> None:
        self.requests: List[dict] = []
        # next response per path; default 200 + {}
        self._scripted: dict[str, tuple[int, dict]] = {}
        self.host = "127.0.0.1"
        self.port = _free_port()
        self._runner: web.AppRunner | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def script(self, path: str, status: int, body: dict) -> None:
        self._scripted[path] = (status, body)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def _handle(self, request: web.Request) -> web.Response:
        body: dict | None
        try:
            body = await request.json() if request.body_exists else None
        except Exception:
            body = None
        self.requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": dict(request.query),
                "headers": dict(request.headers),
                "json": body,
            }
        )
        scripted = self._scripted.get(request.path)
        if scripted:
            status, payload = scripted
        else:
            status, payload = 200, {"status": "ok"}
        return web.json_response(payload, status=status)

    def _make_app(self) -> web.Application:
        app = web.Application()
        # Catch-all on every method/path so any URL the tool emits is recorded.
        app.router.add_route("*", "/{tail:.*}", self._handle)
        return app

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        async def _start() -> None:
            self._runner = web.AppRunner(self._make_app())
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.host, self.port)
            await site.start()
            self._ready.set()

        loop.run_until_complete(_start())
        try:
            loop.run_forever()
        finally:
            loop.run_until_complete(self._runner.cleanup())  # type: ignore[union-attr]
            loop.close()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("mock missive server failed to start in 5s")

    def stop(self) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)


@contextmanager
def _server() -> Iterator[_MockMissiveServer]:
    srv = _MockMissiveServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


def test_missive_health_hits_real_socket(monkeypatch):
    from tools.missive_tool import _handle_health

    with _server() as srv:
        srv.script("/health", 200, {"status": "ok", "version": "5.5.8"})
        monkeypatch.setenv("MISSIVE_BASE_URL", srv.base_url)
        monkeypatch.delenv("MISSIVE_API_TOKEN", raising=False)

        raw = _handle_health({})

        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["status_code"] == 200
        assert payload["body"]["version"] == "5.5.8"

        # exactly one request, GET /health, no auth header
        assert len(srv.requests) == 1
        req = srv.requests[0]
        assert req["method"] == "GET"
        assert req["path"] == "/health"
        assert "Authorization" not in req["headers"]


def test_missive_get_document_forwards_bearer_token(monkeypatch):
    from tools.missive_tool import _handle_get_document

    with _server() as srv:
        srv.script(
            "/api/v1/documents/doc-42",
            200,
            {"id": "doc-42", "title": "Demo"},
        )
        monkeypatch.setenv("MISSIVE_BASE_URL", srv.base_url)
        monkeypatch.setenv("MISSIVE_API_TOKEN", "secret-xyz")

        raw = _handle_get_document({"document_id": "doc-42"})

        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["body"]["id"] == "doc-42"

        assert len(srv.requests) == 1
        req = srv.requests[0]
        assert req["method"] == "GET"
        assert req["path"] == "/api/v1/documents/doc-42"
        assert req["headers"].get("Authorization") == "Bearer secret-xyz"


def test_missive_get_document_propagates_404(monkeypatch):
    from tools.missive_tool import _handle_get_document

    with _server() as srv:
        srv.script(
            "/api/v1/documents/missing",
            404,
            {"detail": "not found"},
        )
        monkeypatch.setenv("MISSIVE_BASE_URL", srv.base_url)
        monkeypatch.delenv("MISSIVE_API_TOKEN", raising=False)

        raw = _handle_get_document({"document_id": "missing"})

        payload = json.loads(raw)
        assert payload["status_code"] == 404
        assert payload["ok"] is False
        assert payload["error"] == "document_not_found"
        # 確認真打 socket，不是 short-circuit
        assert len(srv.requests) == 1
        assert srv.requests[0]["path"] == "/api/v1/documents/missing"


def test_missive_health_unreachable_url_returns_tool_error(monkeypatch):
    """When the server is down, the handler must surface tool_error JSON
    rather than raising — proves the sync wrapper catches transport
    exceptions end-to-end."""
    from tools.missive_tool import _handle_health

    # Use a port we know is closed (free_port returns one we never bind)
    closed_port = _free_port()
    monkeypatch.setenv("MISSIVE_BASE_URL", f"http://127.0.0.1:{closed_port}")
    monkeypatch.delenv("MISSIVE_API_TOKEN", raising=False)
    monkeypatch.setenv("MISSIVE_TIMEOUT_SECONDS", "2")

    raw = _handle_health({})

    payload = json.loads(raw)
    assert "error" in payload
    assert "missive_health failed" in payload["error"]
