"""Tests for tools/pilemgmt_tool.py."""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from tools.pilemgmt_tool import (
    _QUEUE_FILTER_RE,
    _build_headers,
    _check_pile_available,
    _get_config,
    _handle_celery_status,
    _handle_health,
)
from tools.registry import registry


class TestGetConfig:
    def test_blank_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = _get_config()
        assert cfg == {"base_url": "", "token": "", "timeout": 30.0}

    def test_strips_trailing_slash(self):
        with patch.dict(
            os.environ, {"PILE_BASE_URL": "http://pile/"}, clear=True
        ):
            assert _get_config()["base_url"] == "http://pile"

    def test_token_and_timeout(self):
        with patch.dict(
            os.environ,
            {
                "PILE_BASE_URL": "http://pile",
                "PILE_API_TOKEN": "t",
                "PILE_TIMEOUT_SECONDS": "10",
            },
            clear=True,
        ):
            cfg = _get_config()
        assert cfg["token"] == "t"
        assert cfg["timeout"] == 10.0

    def test_invalid_timeout_default(self):
        with patch.dict(
            os.environ,
            {"PILE_BASE_URL": "http://pile", "PILE_TIMEOUT_SECONDS": "weird"},
            clear=True,
        ):
            assert _get_config()["timeout"] == 30.0


class TestBuildHeaders:
    def test_no_token_no_body(self):
        assert _build_headers() == {"Accept": "application/json"}

    def test_with_token(self):
        h = _build_headers("abc")
        assert h["Authorization"] == "Bearer abc"

    def test_with_json_body(self):
        h = _build_headers("abc", json_body=True)
        assert h["Content-Type"] == "application/json"
        assert h["Authorization"] == "Bearer abc"


class TestQueueFilterRegex:
    @pytest.mark.parametrize("v", ["celery", "high.priority", "queue-1", "q_2"])
    def test_accepts_valid(self, v):
        assert _QUEUE_FILTER_RE.match(v)

    @pytest.mark.parametrize("v", ["", "中文", "queue/x", "q?x", "a" * 65])
    def test_rejects_invalid(self, v):
        assert not _QUEUE_FILTER_RE.match(v)


class TestHandleHealth:
    def test_success(self):
        with patch("tools.pilemgmt_tool._async_health", new_callable=AsyncMock) as m:
            m.return_value = {"status_code": 200, "ok": True, "body": {"status": "ok"}}
            payload = json.loads(_handle_health({}))
        assert payload["ok"] is True

    def test_underlying_error(self):
        with patch("tools.pilemgmt_tool._async_health", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("boom")
            payload = json.loads(_handle_health({}))
        assert "error" in payload
        assert "pile_health failed" in payload["error"]


class TestHandleCeleryStatus:
    def test_invalid_queue_filter(self):
        payload = json.loads(_handle_celery_status({"queue_filter": "../q"}))
        assert "Invalid queue_filter" in payload["error"]

    def test_blank_queue_filter_treated_as_none(self):
        with patch(
            "tools.pilemgmt_tool._async_celery_status", new_callable=AsyncMock
        ) as m:
            m.return_value = {"status_code": 200, "ok": True, "body": {}}
            _handle_celery_status({"queue_filter": "   "})
        m.assert_awaited_once_with(None)

    def test_success(self):
        with patch(
            "tools.pilemgmt_tool._async_celery_status", new_callable=AsyncMock
        ) as m:
            m.return_value = {
                "status_code": 200,
                "ok": True,
                "body": {"active": 3, "workers": 2},
            }
            payload = json.loads(_handle_celery_status({"queue_filter": "celery"}))
        assert payload["body"]["active"] == 3
        m.assert_awaited_once_with("celery")

    def test_no_queue_filter_passes_none(self):
        with patch(
            "tools.pilemgmt_tool._async_celery_status", new_callable=AsyncMock
        ) as m:
            m.return_value = {"status_code": 200, "ok": True, "body": {}}
            _handle_celery_status({})
        m.assert_awaited_once_with(None)

    def test_token_missing_error_propagates(self):
        with patch(
            "tools.pilemgmt_tool._async_celery_status", new_callable=AsyncMock
        ) as m:
            m.side_effect = RuntimeError("PILE_API_TOKEN is required for celery_status")
            payload = json.loads(_handle_celery_status({}))
        assert "PILE_API_TOKEN" in payload["error"]


class TestCheckAvailable:
    def test_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_pile_available() is False

    def test_enabled(self):
        with patch.dict(
            os.environ, {"PILE_BASE_URL": "http://pile"}, clear=True
        ):
            assert _check_pile_available() is True


class TestRegistry:
    @pytest.mark.parametrize("name", ["pile_health", "pile_celery_status"])
    def test_each_tool_registered(self, name):
        assert name in registry._tools
        assert registry._tools[name].toolset == "pilemgmt"

    def test_check_fn_wired(self):
        assert registry._tools["pile_health"].check_fn is _check_pile_available

    def test_schemas(self):
        assert (
            registry._tools["pile_health"].schema["parameters"]["required"] == []
        )
        assert (
            registry._tools["pile_celery_status"].schema["parameters"]["required"]
            == []
        )
