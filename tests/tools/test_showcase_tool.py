"""Tests for tools/showcase_tool.py.

Covers:
- Config parsing (base url, token, timeout fallback).
- Header builder (with / without token, with / without json body).
- Project id regex.
- 3 handlers (health, managed_projects, governance_health) happy + error.
- check_fn gating.
- Registry wiring.
"""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from tools.showcase_tool import (
    _PROJECT_ID_RE,
    _build_headers,
    _check_showcase_available,
    _get_config,
    _handle_governance_health,
    _handle_health,
    _handle_managed_projects,
)
from tools.registry import registry


# ---------------------------------------------------------------------------
# Config + headers
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_blank_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = _get_config()
        assert cfg == {"base_url": "", "token": "", "timeout": 15.0}

    def test_trailing_slash_stripped(self):
        with patch.dict(
            os.environ, {"SHOWCASE_BASE_URL": "https://showcase.cksurvey.tw/"}, clear=True
        ):
            cfg = _get_config()
        assert cfg["base_url"] == "https://showcase.cksurvey.tw"

    def test_token_and_timeout(self):
        with patch.dict(
            os.environ,
            {
                "SHOWCASE_BASE_URL": "https://s",
                "SHOWCASE_API_TOKEN": "t",
                "SHOWCASE_TIMEOUT_SECONDS": "5",
            },
            clear=True,
        ):
            cfg = _get_config()
        assert cfg["token"] == "t"
        assert cfg["timeout"] == 5.0

    def test_invalid_timeout_falls_back(self):
        with patch.dict(
            os.environ,
            {"SHOWCASE_BASE_URL": "https://s", "SHOWCASE_TIMEOUT_SECONDS": "x"},
            clear=True,
        ):
            assert _get_config()["timeout"] == 15.0


class TestBuildHeaders:
    def test_no_token_no_body(self):
        assert _build_headers("") == {"Accept": "application/json"}

    def test_with_token(self):
        h = _build_headers("abc")
        assert h["Authorization"] == "Bearer abc"

    def test_with_json_body(self):
        h = _build_headers("", json_body=True)
        assert h["Content-Type"] == "application/json"
        assert "Authorization" not in h


# ---------------------------------------------------------------------------
# project_id regex
# ---------------------------------------------------------------------------


class TestProjectIdRegex:
    @pytest.mark.parametrize(
        "value", ["ck_missive", "ck_aaap", "ck-lvrland", "x", "a_1"]
    )
    def test_accepts_valid(self, value):
        assert _PROJECT_ID_RE.match(value)

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "CK_Missive",  # uppercase not allowed
            "1abc",  # leading digit
            "_abc",  # leading underscore
            "a" * 65,  # too long
            "ab/cd",
            "ab.cd",
            "中文",
        ],
    )
    def test_rejects_invalid(self, value):
        assert not _PROJECT_ID_RE.match(value)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class TestHandleHealth:
    def test_success(self):
        with patch("tools.showcase_tool._async_health", new_callable=AsyncMock) as m:
            m.return_value = {"status_code": 200, "ok": True, "body": {"status": "ok"}}
            raw = _handle_health({})
        payload = json.loads(raw)
        assert payload["ok"] is True

    def test_underlying_error(self):
        with patch("tools.showcase_tool._async_health", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("x")
            raw = _handle_health({})
        payload = json.loads(raw)
        assert "error" in payload
        assert "showcase_health failed" in payload["error"]


class TestHandleManagedProjects:
    def test_success(self):
        with patch(
            "tools.showcase_tool._async_managed_projects", new_callable=AsyncMock
        ) as m:
            m.return_value = {
                "status_code": 200,
                "ok": True,
                "body": {"projects": [{"id": "ck_missive"}]},
            }
            raw = _handle_managed_projects({})
        payload = json.loads(raw)
        assert payload["body"]["projects"][0]["id"] == "ck_missive"

    def test_underlying_error(self):
        with patch(
            "tools.showcase_tool._async_managed_projects", new_callable=AsyncMock
        ) as m:
            m.side_effect = ConnectionError("nope")
            raw = _handle_managed_projects({})
        payload = json.loads(raw)
        assert "error" in payload


class TestHandleGovernanceHealth:
    def test_missing_project_id(self):
        raw = _handle_governance_health({})
        payload = json.loads(raw)
        assert "error" in payload
        assert "project_id" in payload["error"]

    def test_blank_project_id(self):
        raw = _handle_governance_health({"project_id": "   "})
        payload = json.loads(raw)
        assert "error" in payload

    def test_invalid_format_rejected(self):
        raw = _handle_governance_health({"project_id": "../etc"})
        payload = json.loads(raw)
        assert "Invalid project_id" in payload["error"]

    def test_success(self):
        with patch(
            "tools.showcase_tool._async_governance_health", new_callable=AsyncMock
        ) as m:
            m.return_value = {
                "status_code": 200,
                "ok": True,
                "body": {"adr_coverage": 0.85},
            }
            raw = _handle_governance_health({"project_id": "ck_missive"})
        payload = json.loads(raw)
        assert payload["body"]["adr_coverage"] == 0.85
        m.assert_awaited_once_with("ck_missive")

    def test_underlying_error(self):
        with patch(
            "tools.showcase_tool._async_governance_health", new_callable=AsyncMock
        ) as m:
            m.side_effect = TimeoutError("slow")
            raw = _handle_governance_health({"project_id": "ck_missive"})
        payload = json.loads(raw)
        assert "error" in payload


# ---------------------------------------------------------------------------
# check_fn
# ---------------------------------------------------------------------------


class TestCheckAvailable:
    def test_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_showcase_available() is False

    def test_enabled(self):
        with patch.dict(
            os.environ, {"SHOWCASE_BASE_URL": "https://s"}, clear=True
        ):
            assert _check_showcase_available() is True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    @pytest.mark.parametrize(
        "name",
        [
            "showcase_health",
            "showcase_managed_projects",
            "showcase_governance_health",
        ],
    )
    def test_each_tool_registered(self, name):
        assert name in registry._tools
        assert registry._tools[name].toolset == "showcase"

    def test_check_fn_wired(self):
        assert (
            registry._tools["showcase_health"].check_fn is _check_showcase_available
        )

    def test_schemas_required(self):
        assert (
            registry._tools["showcase_health"].schema["parameters"]["required"] == []
        )
        assert (
            registry._tools["showcase_managed_projects"].schema["parameters"][
                "required"
            ]
            == []
        )
        assert registry._tools["showcase_governance_health"].schema["parameters"][
            "required"
        ] == ["project_id"]
