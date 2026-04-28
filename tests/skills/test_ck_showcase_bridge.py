"""Happy-path tests for ck-showcase-bridge skill (B2 Sprint A.3 acceptance)."""
from __future__ import annotations

import importlib.util
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
    / "ck-showcase-bridge-stub"
    / "tools.py"
)


@pytest.fixture
def tools_module(monkeypatch):
    monkeypatch.setenv("SHOWCASE_BASE_URL", "http://test-showcase:5200")
    monkeypatch.setenv("SHOWCASE_API_TOKEN", "test-token")
    monkeypatch.setenv("SHOWCASE_SAFE_MODE", "true")

    sys.modules.pop("ck_showcase_tools", None)
    spec = importlib.util.spec_from_file_location("ck_showcase_tools", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("ck_showcase_tools", None)


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


def _decoded_body(req) -> dict[str, Any]:
    raw = req.data.decode("utf-8") if isinstance(req.data, bytes) else req.data
    return json.loads(raw)  # type: ignore[no-any-return]


def test_showcase_managed_projects_list(monkeypatch, tools_module):
    body = {"projects": [{"id": "ck_missive", "phase": "production"},
                         {"id": "ck_lvrland", "phase": "phase-2"}]}
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.showcase_managed_projects_list())
    assert result["total"] == 2
    assert captured[0].full_url == "http://test-showcase:5200/api/overview/projects"
    assert captured[0].headers.get("Authorization") == "Bearer test-token"


def test_showcase_adr_map_query_requires_project_id(tools_module):
    result = json.loads(tools_module.showcase_adr_map_query(""))
    assert result["error"] == "missing_arg"


def test_showcase_adr_map_query_passes_filters(monkeypatch, tools_module):
    body = {"summary": {"accepted": 5, "proposed": 2}, "recent": [{"fqid": "ck_missive#0006"}]}
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.showcase_adr_map_query(
            "ck_missive", status_filter="accepted", limit=3,
        ))
    sent = _decoded_body(captured[0])
    assert sent == {"project_id": "ck_missive", "limit": 3, "status_filter": "accepted"}
    assert result["summary"]["accepted"] == 5


def test_showcase_governance_health_platform_wide(monkeypatch, tools_module):
    body = {"by_project": {"ck_missive": {"score": 0.9}},
            "overall": {"score": 0.85}}
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.showcase_governance_health())
    sent = _decoded_body(captured[0])
    assert sent == {}
    assert result["overall"]["score"] == 0.85


def test_showcase_platform_metrics_validates_window(tools_module):
    result = json.loads(tools_module.showcase_platform_metrics(window="3d"))
    assert result["error"] == "bad_arg"


def test_showcase_platform_metrics_returns_metrics(monkeypatch, tools_module):
    body = {"metrics": {"adr_total": 105}, "generated_at": "2026-04-28T00:00:00Z"}
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.showcase_platform_metrics(window="30d"))
    assert result["metrics"]["adr_total"] == 105


def test_showcase_skills_sync_status_requires_project(tools_module):
    result = json.loads(tools_module.showcase_skills_sync_status(""))
    assert result["error"] == "missing_arg"


def test_showcase_skills_sync_status_drops_drift_when_excluded(monkeypatch, tools_module):
    body = {"last_sync_at": "2026-04-28", "count": 12, "drift": [{"name": "x"}]}
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.showcase_skills_sync_status(
            "ck_missive", include_drift=False,
        ))
    assert result["count"] == 12
    assert result["drift"] is None


def test_showcase_agents_list_validates_filter(tools_module):
    result = json.loads(tools_module.showcase_agents_list("ck_missive", status_filter="bogus"))
    assert result["error"] == "bad_arg"


def test_showcase_agents_list_returns_agents(monkeypatch, tools_module):
    body = {"agents": [{"id": "agent-a"}, {"id": "agent-b"}]}
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.showcase_agents_list("ck_missive"))
    assert result["total"] == 2


def test_showcase_security_scan_safe_mode_forces_dry_run(tools_module):
    result = json.loads(tools_module.showcase_security_scan_run(
        "ck_missive", mode="run", scan_type="full",
    ))
    assert result["dry_run"] is True
    assert result["reason"] == "SHOWCASE_SAFE_MODE=true"
    assert result["estimated_duration_s"] == 120


def test_showcase_security_scan_query_dry_run(monkeypatch, tools_module):
    monkeypatch.setattr(tools_module, "SAFE_MODE", False)
    result = json.loads(tools_module.showcase_security_scan_run("ck_missive", mode="query"))
    assert result["dry_run"] is True
    assert result["reason"] == "mode=query"


def test_showcase_security_scan_run_actually_calls(monkeypatch, tools_module):
    monkeypatch.setattr(tools_module, "SAFE_MODE", False)
    body = {"scan_id": "scan-42", "findings": [{"severity": "high"}]}
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.showcase_security_scan_run(
            "ck_missive", mode="run", scan_type="quick",
        ))
    sent = _decoded_body(captured[0])
    assert sent == {"project_id": "ck_missive", "mode": "run", "scan_type": "quick"}
    assert result["scan_id"] == "scan-42"
    assert result["findings_count"] == 1


def test_showcase_sso_status_returns_disabled_default(monkeypatch, tools_module):
    body = {"enabled": False, "provider": "", "active_users": 0}
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.showcase_sso_status("ck_missive"))
    assert result["enabled"] is False


def test_showcase_unreachable_returns_structured_error(monkeypatch, tools_module):
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(tools_module.urllib.request, "urlopen", boom)
    result = json.loads(tools_module.showcase_managed_projects_list())
    assert result["error"] == "showcase_unreachable"


def test_register_all_registers_eight_tools(tools_module):
    class FakeRegistry:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def register(self, **kwargs: Any) -> None:
            self.calls.append(kwargs)

    reg = FakeRegistry()
    count = tools_module.register_all(reg)
    assert count == 8
    names = {c["name"] for c in reg.calls}
    assert names == {
        "showcase_managed_projects_list", "showcase_adr_map_query",
        "showcase_governance_health", "showcase_platform_metrics",
        "showcase_skills_sync_status", "showcase_agents_list",
        "showcase_security_scan_run", "showcase_sso_status",
    }
