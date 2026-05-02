"""Happy-path tests for ck-lvrland-bridge skill (B2 Sprint A.5 acceptance)."""
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
    / "ck-lvrland-bridge-stub"
    / "tools.py"
)


@pytest.fixture
def tools_module(monkeypatch):
    monkeypatch.setenv("LVRLAND_BASE_URL", "http://test-lvrland:8002")
    monkeypatch.setenv("LVRLAND_API_TOKEN", "test-token")
    monkeypatch.setenv("LVRLAND_DEFAULT_DISTRICTS", "中壢區,桃園區")

    sys.modules.pop("ck_lvrland_tools", None)
    spec = importlib.util.spec_from_file_location("ck_lvrland_tools", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("ck_lvrland_tools", None)


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


# ── lvrland_health ─────────────────────────────────────────
def test_lvrland_health_detail_endpoint_struct(monkeypatch, tools_module):
    body = {
        "status": "healthy",
        "containers": [{"name": "ck-lvrland-backend", "state": "running"}],
        "db": {"connected": True},
        "ollama": {"reachable": True},
        "version": "1.0.0",
    }
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.lvrland_health())
    assert result["status"] == "healthy"
    assert result["source"] == "detail_endpoint"
    assert result["version"] == "1.0.0"
    assert captured[0].full_url == "http://test-lvrland:8002/api/health/detail"
    assert captured[0].headers.get("Authorization") == "Bearer test-token"


def test_lvrland_health_falls_back_to_plain(monkeypatch, tools_module):
    """detail endpoint 404 → fall back to GET /api/health."""
    plain_body = {"status": "ok"}
    call_count = {"n": 0}

    def fake_urlopen(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise _http_error(req.full_url, 404, b'{"detail": "not found"}')
        return FakeResponse(plain_body)

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", fake_urlopen)
    result = json.loads(tools_module.lvrland_health())
    assert result["source"] == "plain_health"
    assert result["status"] == "ok"


# ── lvrland_query_sync ─────────────────────────────────────
def test_lvrland_query_sync_requires_question(tools_module):
    result = json.loads(tools_module.lvrland_query_sync(""))
    assert result["error"] == "missing_arg"


def test_lvrland_query_sync_text_response_struct(monkeypatch, tools_module):
    body = {"type": "text_response", "content": "中壢區 2026 Q1 平均房價 38.5 萬/坪"}
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.lvrland_query_sync("中壢區房價"))
    assert result["type"] == "text_response"
    assert "38.5" in result["content"]
    assert captured[0].full_url == "http://test-lvrland:8002/api/v1/ai/query"
    sent_body = json.loads(captured[0].data.decode("utf-8"))
    assert sent_body["question"] == "中壢區房價"


def test_lvrland_query_sync_tool_call_struct(monkeypatch, tools_module):
    """Question with map keyword + known district → tool_call response."""
    body = {
        "type": "tool_call",
        "tool_name": "map_highlight",
        "arguments": {"area_name": "中壢區"},
    }
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.lvrland_query_sync("在地圖上顯示中壢區"))
    assert result["type"] == "tool_call"
    assert result["tool_name"] == "map_highlight"
    assert result["arguments"]["area_name"] == "中壢區"


# ── lvrland_price_trends ───────────────────────────────────
def test_lvrland_price_trends_with_list_input(monkeypatch, tools_module):
    body = {
        "中壢區": {
            "periods": ["2025Q4", "2026Q1"],
            "avg_prices": [37.2, 38.5],
            "volumes": [120, 135],
            "building_type_breakdown": [{}, {}],
        },
    }
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.lvrland_price_trends(["中壢區"]))
    assert result["districts"] == ["中壢區"]
    assert "中壢區" in result["trends"]
    assert captured[0].full_url == "http://test-lvrland:8002/api/v1/analytics/price-volume-trends"
    sent_body = json.loads(captured[0].data.decode("utf-8"))
    assert sent_body["districts"] == ["中壢區"]


def test_lvrland_price_trends_with_csv_string(monkeypatch, tools_module):
    """CLI ergonomics: comma-separated string is split into list."""
    with stub_http(monkeypatch, tools_module, [{}]) as captured:
        json.loads(tools_module.lvrland_price_trends("中壢區,桃園區,觀音區"))
    sent_body = json.loads(captured[0].data.decode("utf-8"))
    assert sent_body["districts"] == ["中壢區", "桃園區", "觀音區"]


def test_lvrland_price_trends_default_districts(monkeypatch, tools_module):
    """None input falls back to LVRLAND_DEFAULT_DISTRICTS env."""
    with stub_http(monkeypatch, tools_module, [{}]) as captured:
        result = json.loads(tools_module.lvrland_price_trends(None))
    sent_body = json.loads(captured[0].data.decode("utf-8"))
    assert sent_body["districts"] == ["中壢區", "桃園區"]
    assert result["districts"] == ["中壢區", "桃園區"]


def test_lvrland_price_trends_empty_with_no_default(monkeypatch, tools_module):
    monkeypatch.setattr(tools_module, "DEFAULT_DISTRICTS", [])
    result = json.loads(tools_module.lvrland_price_trends(None))
    assert result["error"] == "missing_arg"


# ── error paths ─────────────────────────────────────────────
def test_lvrland_unreachable_returns_structured_error(monkeypatch, tools_module):
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", boom)
    result = json.loads(tools_module.lvrland_health())
    assert result["error"] == "lvrland_unreachable"


def test_lvrland_http_5xx_surfaces_error(monkeypatch, tools_module):
    def fake_urlopen(req, timeout=None):
        raise _http_error(req.full_url, 500, b'{"detail": "internal"}')

    monkeypatch.setattr(tools_module.urllib.request, "urlopen", fake_urlopen)
    result = json.loads(tools_module.lvrland_query_sync("anything"))
    assert result["error"] == "lvrland_http_error"
    assert result["status"] == 500


# ── register_all ────────────────────────────────────────────
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
    assert names == {"lvrland_health", "lvrland_query_sync", "lvrland_price_trends"}
