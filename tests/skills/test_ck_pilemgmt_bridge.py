"""Happy-path tests for ck-pilemgmt-bridge skill (B2 Sprint A.4 acceptance)."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "plans"
    / "ck-pilemgmt-bridge-stub"
    / "tools.py"
)


@pytest.fixture
def tools_module(monkeypatch):
    monkeypatch.setenv("PILE_BASE_URL", "http://test-pile:8004")
    monkeypatch.setenv("PILE_API_TOKEN", "test-token")
    monkeypatch.setenv("PILE_CELERY_FLOWER_URL", "http://test-flower:5555")

    sys.modules.pop("ck_pile_tools", None)
    spec = importlib.util.spec_from_file_location("ck_pile_tools", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("ck_pile_tools", None)


class FakeResponse:
    def __init__(self, body: dict[str, Any] | list[Any]):
        self._body = json.dumps(body).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


@contextmanager
def stub_http(monkeypatch, mod, queue: list[Any]):
    pending = list(queue)
    captured: list[Any] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        return FakeResponse(pending.pop(0))

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    yield captured


def _http_error(url: str, code: int, body: bytes = b"{}") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(body))


def test_pile_health_returns_struct(monkeypatch, tools_module):
    body = {
        "status": "healthy",
        "containers": [{"name": "ck_pilemgmt-backend", "state": "running"}],
        "db": {"connected": True},
        "celery": {"workers": 2},
        "version": "1.2.3",
    }
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.pile_health())
    assert result["status"] == "healthy"
    assert result["version"] == "1.2.3"
    assert captured[0].full_url == "http://test-pile:8004/api/health/detail"
    assert captured[0].headers.get("Authorization") == "Bearer test-token"


def test_pile_query_sync_requires_question(tools_module):
    result = json.loads(tools_module.pile_query_sync(""))
    assert result["error"] == "missing_arg"


def test_pile_query_sync_returns_answer_when_backend_ready(monkeypatch, tools_module):
    body = {"answer": "樁 A1 已驗收", "sources": [{"id": "case-001"}]}
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.pile_query_sync("樁 A1 狀態？"))
    assert result["answer"] == "樁 A1 已驗收"
    assert len(result["sources"]) == 1


def test_pile_query_sync_404_returns_backend_endpoint_missing(monkeypatch, tools_module):
    def fake_urlopen(req, timeout=None):
        raise _http_error(req.full_url, 404, b'{"detail": "not implemented"}')

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", fake_urlopen)
    result = json.loads(tools_module.pile_query_sync("anything"))
    assert result["error"] == "backend_endpoint_missing"
    assert result["status"] == 404
    assert "ADR-0023" in result["message"]


def test_pile_celery_status_primary_endpoint(monkeypatch, tools_module):
    body = {
        "active": [{"id": "task-1"}],
        "scheduled": [],
        "reserved": [],
        "workers": [{"name": "celery@worker1"}],
    }
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.pile_celery_status())
    assert result["source"] == "pile_celery_endpoint"
    assert len(result["active"]) == 1
    assert result["workers"][0]["name"] == "celery@worker1"


def test_pile_celery_status_falls_back_to_flower(monkeypatch, tools_module):
    """Primary endpoint 5xx → Flower fallback engages."""
    flower_body = {
        "task-a": {"state": "STARTED", "name": "ingest"},
        "task-b": {"state": "RECEIVED", "name": "scan"},
        "task-c": {"state": "SUCCESS", "name": "done"},
    }
    call_count = {"n": 0}

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise _http_error(req.full_url, 500, b'{"detail": "internal"}')
        return FakeResponse(flower_body)

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", fake_urlopen)
    result = json.loads(tools_module.pile_celery_status())
    assert result["source"] == "flower_fallback"
    assert len(result["active"]) == 1
    assert len(result["scheduled"]) == 1


def test_pile_celery_status_no_flower_surfaces_primary_error(monkeypatch, tools_module):
    monkeypatch.setattr(tools_module, "FLOWER_URL", "")

    def fake_urlopen(req, timeout=None):
        raise _http_error(req.full_url, 500, b'{"detail": "internal"}')

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", fake_urlopen)
    result = json.loads(tools_module.pile_celery_status())
    assert result["error"] == "pile_http_error"
    assert result["status"] == 500


def test_pile_unreachable_returns_structured_error(monkeypatch, tools_module):
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", boom)
    result = json.loads(tools_module.pile_health())
    assert result["error"] == "pile_unreachable"


def test_register_all_registers_three_tools(tools_module):
    class FakeRegistry:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def register(self, **kwargs: Any) -> None:
            self.calls.append(kwargs)

    reg = FakeRegistry()
    count = tools_module.register_all(reg)
    assert count == 3
    names = {c["name"] for c in reg.calls}
    assert names == {"pile_health", "pile_query_sync", "pile_celery_status"}
