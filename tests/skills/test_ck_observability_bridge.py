"""Happy-path tests for ck-observability-bridge skill (B2 Sprint A.2 acceptance)."""
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
    / "ck-observability-bridge-skeleton"
    / "tools.py"
)


@pytest.fixture
def tools_module(monkeypatch):
    monkeypatch.setenv("OBS_LOKI_URL", "http://test-loki")
    monkeypatch.setenv("OBS_PROMETHEUS_URL", "http://test-prom")
    monkeypatch.setenv("OBS_GRAFANA_URL", "http://test-grafana")
    monkeypatch.setenv("OBS_ALERTMANAGER_URL", "http://test-alert")
    monkeypatch.setenv("OBS_GRAFANA_TOKEN", "test-token")
    monkeypatch.setenv("OBS_SAFE_MODE", "true")

    sys.modules.pop("ck_obs_tools", None)
    spec = importlib.util.spec_from_file_location("ck_obs_tools", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("ck_obs_tools", None)


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
    """Stub urlopen to return a queue of fake responses (one per call)."""
    pending = list(queue)
    captured: list[Any] = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        if not pending:
            raise AssertionError("urlopen called more times than expected")
        return FakeResponse(pending.pop(0))

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    yield captured


def test_obs_prom_query_summarizes_series(monkeypatch, tools_module):
    body = {
        "status": "success",
        "data": {
            "result": [
                {
                    "metric": {"job": "ck_missive", "instance": "host:8000"},
                    "values": [["1700000000", "0.10"], ["1700000060", "0.20"], ["1700000120", "0.30"]],
                }
            ]
        },
    }
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.obs_prom_query("up", window="1h"))
    assert result["series_count"] == 1
    s = result["series"][0]
    assert s["min"] == 0.10
    assert s["max"] == 0.30
    assert s["trend"] == "rising"


def test_obs_prom_query_prom_failure_returns_error(monkeypatch, tools_module):
    body = {"status": "error", "error": "bad query", "errorType": "bad_data"}
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.obs_prom_query("???"))
    assert result["error"] == "prom_query_failed"


def test_obs_grafana_dashboard_url_with_uid(monkeypatch, tools_module):
    meta = {
        "dashboard": {"title": "Missive Overview"},
        "meta": {"url": "/d/abc123/missive-overview"},
    }
    with stub_http(monkeypatch, tools_module, [meta]):
        result = json.loads(tools_module.obs_grafana_dashboard_url(
            dashboard_id="abc123",
            variables={"container": "ck_missive_backend"},
        ))
    assert result["dashboard_id"] == "abc123"
    assert "var-container=ck_missive_backend" in result["url"]
    assert result["url"].startswith("http://test-grafana/d/abc123")


def test_obs_grafana_dashboard_url_search_by_name(monkeypatch, tools_module):
    search_resp = [{"uid": "uid-9", "title": "Loki Errors"}]
    detail_resp = {"dashboard": {"title": "Loki Errors"}, "meta": {"url": "/d/uid-9/loki-errors"}}
    with stub_http(monkeypatch, tools_module, [search_resp, detail_resp]):  # multi-response queue
        result = json.loads(tools_module.obs_grafana_dashboard_url(dashboard_name="Loki"))
    assert result["dashboard_id"] == "uid-9"
    assert result["title"] == "Loki Errors"


def test_obs_grafana_dashboard_url_missing_args(tools_module):
    result = json.loads(tools_module.obs_grafana_dashboard_url())
    assert result["error"] == "missing_arg"


def test_obs_alertmanager_silence_safe_mode_returns_dry_run(tools_module):
    result = json.loads(tools_module.obs_alertmanager_silence(
        matchers=[{"name": "alertname", "value": "HighCPU", "isRegex": False}],
        duration="30m",
        comment="test",
        mode="run",
    ))
    assert result["dry_run"] is True
    assert result["reason"] == "OBS_SAFE_MODE=true"
    assert result["would_post"]["matchers"][0]["value"] == "HighCPU"


def test_obs_alertmanager_silence_query_mode_dry_run(monkeypatch, tools_module):
    monkeypatch.setattr(tools_module, "SAFE_MODE", False)
    result = json.loads(tools_module.obs_alertmanager_silence(
        matchers=[{"name": "alertname", "value": "X", "isRegex": False}],
        mode="query",
    ))
    assert result["dry_run"] is True
    assert result["reason"] == "mode=query"


def test_obs_alertmanager_silence_run_mode_actually_calls(monkeypatch, tools_module):
    monkeypatch.setattr(tools_module, "SAFE_MODE", False)
    body = {"silenceID": "sid-42"}
    with stub_http(monkeypatch, tools_module, [body]) as captured:
        result = json.loads(tools_module.obs_alertmanager_silence(
            matchers=[{"name": "alertname", "value": "X", "isRegex": False}],
            mode="run",
        ))
    assert result["silenceID"] == "sid-42"
    assert captured[0].method == "POST"
    assert captured[0].full_url.endswith("/api/v2/silences")


def test_obs_container_health_classifies_state(monkeypatch, tools_module):
    body = {
        "status": "success",
        "data": {
            "result": [
                {"metric": {"name": "ck_missive_backend", "image": "ck_missive:latest"},
                 "value": [0, str(int(__import__("time").time()))]},
                {"metric": {"name": "ck_missive_old", "image": "ck_missive:legacy"},
                 "value": [0, str(int(__import__("time").time()) - 1000)]},
            ]
        },
    }
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.obs_container_health("ck_missive_"))
    assert result["total"] == 2
    states = {c["container"]: c["state"] for c in result["containers"]}
    assert states["ck_missive_backend"] == "running"
    assert states["ck_missive_old"] == "down"
    assert "running" in result["summary"]


def test_obs_container_health_missing_arg(tools_module):
    result = json.loads(tools_module.obs_container_health(""))
    assert result["error"] == "missing_arg"


def test_obs_alert_active_filters_by_severity(monkeypatch, tools_module):
    body = [
        {
            "labels": {"alertname": "HighCPU", "severity": "warning", "service": "missive"},
            "status": {"state": "active"},
            "startsAt": "2026-04-28T00:00:00Z",
            "annotations": {"summary": "CPU > 80%"},
        },
        {
            "labels": {"alertname": "DiskFull", "severity": "critical", "service": "loki"},
            "status": {"state": "active"},
            "startsAt": "2026-04-28T01:00:00Z",
            "annotations": {"summary": "disk full"},
        },
    ]
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.obs_alert_active(severity="critical"))
    assert result["total"] == 1
    assert result["alerts"][0]["alertname"] == "DiskFull"
    assert result["by_severity"] == {"critical": 1}


def test_obs_alert_active_filters_by_project_substring(monkeypatch, tools_module):
    body = [
        {"labels": {"alertname": "A", "service": "missive"}, "status": {"state": "active"},
         "startsAt": "", "annotations": {"summary": ""}},
        {"labels": {"alertname": "B", "service": "loki"}, "status": {"state": "active"},
         "startsAt": "", "annotations": {"summary": ""}},
    ]
    with stub_http(monkeypatch, tools_module, [body]):
        result = json.loads(tools_module.obs_alert_active(project_filter="missive"))
    assert result["total"] == 1
    assert result["alerts"][0]["alertname"] == "A"


def test_loki_unreachable_returns_structured_error(monkeypatch, tools_module):
    def boom(req, timeout=None):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(tools_module.urllib.request, "urlopen", boom)
    result = json.loads(tools_module.obs_loki_query('{container="x"}'))
    assert result["error"] == "loki_unreachable"
    assert result["url"] == "http://test-loki"


def test_register_all_registers_eight_tools(tools_module):
    class FakeRegistry:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []

        def register(self, **kwargs: Any) -> None:
            self.calls.append(kwargs)

    reg = FakeRegistry()
    count = tools_module.register_all(reg)
    assert count == 8
    names = {c["name"] for c in reg.calls}
    assert names == {
        "obs_loki_query", "obs_loki_errors", "obs_loki_briefing",
        "obs_prom_query", "obs_grafana_dashboard_url",
        "obs_alertmanager_silence", "obs_container_health", "obs_alert_active",
    }
