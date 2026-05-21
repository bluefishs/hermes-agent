"""Tests for tools/observability_tool.py.

Covers:
- Per-backend env parsing + base url normalization.
- Grafana basic auth header builder (with / without creds).
- Handlers: happy path, missing required arg, underlying error wrapping.
- Per-backend check_fn gating.
- Registry: all 4 tools registered under 'observability' toolset.
"""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from tools.observability_tool import (
    _base,
    _check_alert,
    _check_grafana,
    _check_loki,
    _check_prom,
    _common_headers,
    _get_timeout,
    _grafana_basic_auth_header,
    _handle_alerts_active,
    _handle_grafana_health,
    _handle_loki_query_range,
    _handle_prometheus_query,
)
from tools.registry import registry


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


class TestConfigHelpers:
    def test_base_empty_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _base("OBS_PROMETHEUS_URL") == ""

    def test_base_strips_trailing_slash(self):
        with patch.dict(
            os.environ,
            {"OBS_PROMETHEUS_URL": "http://host.docker.internal:19090/"},
            clear=True,
        ):
            assert _base("OBS_PROMETHEUS_URL") == (
                "http://host.docker.internal:19090"
            )

    def test_timeout_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _get_timeout() == 15.0

    def test_timeout_override(self):
        with patch.dict(
            os.environ, {"OBS_TIMEOUT_S": "8"}, clear=True
        ):
            assert _get_timeout() == 8.0

    def test_timeout_invalid_falls_back(self):
        with patch.dict(
            os.environ, {"OBS_TIMEOUT_S": "weird"}, clear=True
        ):
            assert _get_timeout() == 15.0


class TestGrafanaBasicAuth:
    def test_none_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _grafana_basic_auth_header() is None

    def test_none_when_user_only(self):
        with patch.dict(
            os.environ, {"OBS_GRAFANA_USER": "u"}, clear=True
        ):
            assert _grafana_basic_auth_header() is None

    def test_basic_token_built(self):
        with patch.dict(
            os.environ,
            {
                "OBS_GRAFANA_USER": "u",
                "OBS_GRAFANA_PASS": "p",
            },
            clear=True,
        ):
            header = _grafana_basic_auth_header()
        assert header is not None
        assert header.startswith("Basic ")


class TestCommonHeaders:
    def test_no_auth(self):
        assert _common_headers() == {"Accept": "application/json"}

    def test_with_auth(self):
        h = _common_headers("Bearer xyz")
        assert h["Authorization"] == "Bearer xyz"


# ---------------------------------------------------------------------------
# Per-backend check_fn
# ---------------------------------------------------------------------------


class TestCheckFunctions:
    def test_prom_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_prom() is False

    def test_prom_enabled(self):
        with patch.dict(
            os.environ,
            {"OBS_PROMETHEUS_URL": "http://p:19090"},
            clear=True,
        ):
            assert _check_prom() is True

    def test_loki_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_loki() is False

    def test_loki_enabled(self):
        with patch.dict(
            os.environ, {"OBS_LOKI_URL": "http://l:13100"}, clear=True
        ):
            assert _check_loki() is True

    def test_grafana_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_grafana() is False

    def test_grafana_enabled(self):
        with patch.dict(
            os.environ,
            {"OBS_GRAFANA_URL": "http://g:13000"},
            clear=True,
        ):
            assert _check_grafana() is True

    def test_alert_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_alert() is False

    def test_alert_enabled(self):
        with patch.dict(
            os.environ,
            {"OBS_ALERTMANAGER_URL": "http://a:19093"},
            clear=True,
        ):
            assert _check_alert() is True


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class TestPrometheusQuery:
    def test_missing_query(self):
        raw = _handle_prometheus_query({})
        payload = json.loads(raw)
        assert "error" in payload
        assert "query" in payload["error"]

    def test_blank_query(self):
        raw = _handle_prometheus_query({"query": "   "})
        payload = json.loads(raw)
        assert "error" in payload

    def test_success(self):
        async_result = {
            "status_code": 200,
            "ok": True,
            "body": {"status": "success", "data": {"result": []}},
        }
        with patch(
            "tools.observability_tool._async_prometheus_query",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = async_result
            raw = _handle_prometheus_query({"query": "up"})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["body"]["status"] == "success"

    def test_underlying_error(self):
        with patch(
            "tools.observability_tool._async_prometheus_query",
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = RuntimeError("backend down")
            raw = _handle_prometheus_query({"query": "up"})
        payload = json.loads(raw)
        assert "error" in payload
        assert "prometheus_query failed" in payload["error"]


class TestLokiQueryRange:
    def test_missing_query(self):
        raw = _handle_loki_query_range({})
        payload = json.loads(raw)
        assert "error" in payload

    def test_success(self):
        async_result = {
            "status_code": 200,
            "ok": True,
            "body": {"status": "success", "data": {"resultType": "streams"}},
        }
        with patch(
            "tools.observability_tool._async_loki_query_range",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = async_result
            raw = _handle_loki_query_range({"query": '{container="x"}'})
        payload = json.loads(raw)
        assert payload["ok"] is True

    def test_passes_optional_params(self):
        with patch(
            "tools.observability_tool._async_loki_query_range",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = {"status_code": 200, "ok": True, "body": {}}
            _handle_loki_query_range(
                {
                    "query": '{container="x"}',
                    "start": "2026-05-16T00:00:00Z",
                    "end": "2026-05-16T01:00:00Z",
                    "limit": 100,
                    "step": "30s",
                }
            )
        # AsyncMock records the call; verify forwarding
        m.assert_awaited_once_with(
            '{container="x"}',
            start="2026-05-16T00:00:00Z",
            end="2026-05-16T01:00:00Z",
            limit=100,
            step="30s",
        )

    def test_underlying_error(self):
        with patch(
            "tools.observability_tool._async_loki_query_range",
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = TimeoutError("slow")
            raw = _handle_loki_query_range({"query": "{a=\"b\"}"})
        payload = json.loads(raw)
        assert "error" in payload


class TestGrafanaHealth:
    def test_success(self):
        async_result = {
            "status_code": 200,
            "ok": True,
            "body": {"database": "ok", "version": "10.4.2"},
        }
        with patch(
            "tools.observability_tool._async_grafana_health",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = async_result
            raw = _handle_grafana_health({})
        payload = json.loads(raw)
        assert payload["body"]["database"] == "ok"

    def test_underlying_error(self):
        with patch(
            "tools.observability_tool._async_grafana_health",
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = ConnectionError("refused")
            raw = _handle_grafana_health({})
        payload = json.loads(raw)
        assert "error" in payload


class TestAlertsActive:
    def test_success_no_args(self):
        async_result = {"status_code": 200, "ok": True, "body": []}
        with patch(
            "tools.observability_tool._async_alerts_active",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = async_result
            raw = _handle_alerts_active({})
        payload = json.loads(raw)
        assert payload["ok"] is True
        m.assert_awaited_once_with(active=None, silenced=None)

    def test_filters_passed(self):
        with patch(
            "tools.observability_tool._async_alerts_active",
            new_callable=AsyncMock,
        ) as m:
            m.return_value = {"status_code": 200, "ok": True, "body": []}
            _handle_alerts_active({"active": True, "silenced": False})
        m.assert_awaited_once_with(active=True, silenced=False)

    def test_underlying_error(self):
        with patch(
            "tools.observability_tool._async_alerts_active",
            new_callable=AsyncMock,
        ) as m:
            m.side_effect = RuntimeError("nope")
            raw = _handle_alerts_active({})
        payload = json.loads(raw)
        assert "error" in payload


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


class TestRegistry:
    @pytest.mark.parametrize(
        "name",
        ["prometheus_query", "loki_query_range", "grafana_health", "alerts_active"],
    )
    def test_each_tool_registered(self, name):
        assert name in registry._tools

    @pytest.mark.parametrize(
        "name",
        ["prometheus_query", "loki_query_range", "grafana_health", "alerts_active"],
    )
    def test_toolset_is_observability(self, name):
        assert registry._tools[name].toolset == "observability"

    def test_required_envs_split_per_tool(self):
        assert registry._tools["prometheus_query"].requires_env == [
            "OBS_PROMETHEUS_URL"
        ]
        assert registry._tools["loki_query_range"].requires_env == [
            "OBS_LOKI_URL"
        ]
        assert registry._tools["grafana_health"].requires_env == [
            "OBS_GRAFANA_URL"
        ]
        assert registry._tools["alerts_active"].requires_env == [
            "OBS_ALERTMANAGER_URL"
        ]

    def test_check_fns_split_per_tool(self):
        assert registry._tools["prometheus_query"].check_fn is _check_prom
        assert registry._tools["loki_query_range"].check_fn is _check_loki
        assert registry._tools["grafana_health"].check_fn is _check_grafana
        assert registry._tools["alerts_active"].check_fn is _check_alert

    def test_schemas_have_required_fields(self):
        assert (
            registry._tools["prometheus_query"].schema["parameters"]["required"]
            == ["query"]
        )
        assert (
            registry._tools["loki_query_range"].schema["parameters"]["required"]
            == ["query"]
        )
        assert (
            registry._tools["grafana_health"].schema["parameters"]["required"] == []
        )
        assert (
            registry._tools["alerts_active"].schema["parameters"]["required"] == []
        )
