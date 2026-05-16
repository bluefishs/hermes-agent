"""Tests for tools/missive_tool.py.

Covers:
- Config parsing from env (base_url normalization, token, timeout fallback).
- Header builder (with / without token).
- Document_id validation regex.
- Sync handlers happy path + error branches (via patched async helpers).
- check_fn availability gate.
- Registry registration (names, toolset, schemas, check_fn wiring).
"""

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

from tools.missive_tool import (
    _DOCUMENT_ID_RE,
    _build_headers,
    _check_missive_available,
    _get_config,
    _handle_get_document,
    _handle_health,
)
from tools.registry import registry


# ---------------------------------------------------------------------------
# Config + headers
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_empty_env_returns_blank_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = _get_config()
        assert cfg["base_url"] == ""
        assert cfg["token"] == ""
        assert cfg["timeout"] == 15.0

    def test_trailing_slash_stripped(self):
        with patch.dict(os.environ, {"MISSIVE_BASE_URL": "http://m.local:8002/"}, clear=True):
            cfg = _get_config()
        assert cfg["base_url"] == "http://m.local:8002"

    def test_token_passes_through(self):
        with patch.dict(
            os.environ,
            {"MISSIVE_BASE_URL": "http://m.local", "MISSIVE_API_TOKEN": "abc"},
            clear=True,
        ):
            cfg = _get_config()
        assert cfg["token"] == "abc"

    def test_timeout_override(self):
        with patch.dict(
            os.environ,
            {"MISSIVE_BASE_URL": "http://m.local", "MISSIVE_TIMEOUT_SECONDS": "3.5"},
            clear=True,
        ):
            cfg = _get_config()
        assert cfg["timeout"] == 3.5

    def test_timeout_invalid_falls_back(self):
        with patch.dict(
            os.environ,
            {"MISSIVE_BASE_URL": "http://m.local", "MISSIVE_TIMEOUT_SECONDS": "not-a-number"},
            clear=True,
        ):
            cfg = _get_config()
        assert cfg["timeout"] == 15.0


class TestBuildHeaders:
    def test_no_token(self):
        h = _build_headers("")
        assert h == {"Accept": "application/json"}

    def test_with_token(self):
        h = _build_headers("token-x")
        assert h["Authorization"] == "Bearer token-x"
        assert h["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# Document id validation
# ---------------------------------------------------------------------------


class TestDocumentIdRegex:
    @pytest.mark.parametrize(
        "value",
        ["abc", "ABC123", "doc_42", "uuid-1234-abcd", "x" * 128],
    )
    def test_accepts_safe_ids(self, value):
        assert _DOCUMENT_ID_RE.match(value)

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "../etc",
            "doc/123",
            "doc.json",
            "x" * 129,
            "中文",
            "doc?query=1",
            "doc 1",
        ],
    )
    def test_rejects_unsafe_ids(self, value):
        assert not _DOCUMENT_ID_RE.match(value)


# ---------------------------------------------------------------------------
# Handler: missive_health
# ---------------------------------------------------------------------------


class TestHandleHealth:
    def test_success(self):
        async_result = {
            "status_code": 200,
            "ok": True,
            "body": {"status": "ok", "version": "5.5.8"},
        }
        with patch("tools.missive_tool._async_health", new_callable=AsyncMock) as m:
            m.return_value = async_result
            raw = _handle_health({})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["status_code"] == 200
        assert payload["body"]["status"] == "ok"

    def test_underlying_error_returns_tool_error(self):
        with patch("tools.missive_tool._async_health", new_callable=AsyncMock) as m:
            m.side_effect = RuntimeError("boom")
            raw = _handle_health({})
        payload = json.loads(raw)
        assert "error" in payload
        assert "missive_health failed" in payload["error"]


# ---------------------------------------------------------------------------
# Handler: missive_get_document
# ---------------------------------------------------------------------------


class TestHandleGetDocument:
    def test_missing_id(self):
        raw = _handle_get_document({})
        payload = json.loads(raw)
        assert "error" in payload
        assert "document_id" in payload["error"]

    def test_blank_id(self):
        raw = _handle_get_document({"document_id": "   "})
        payload = json.loads(raw)
        assert "error" in payload

    def test_invalid_id_rejected(self):
        raw = _handle_get_document({"document_id": "../etc/passwd"})
        payload = json.loads(raw)
        assert "error" in payload
        assert "Invalid document_id" in payload["error"]

    def test_success(self):
        async_result = {
            "status_code": 200,
            "ok": True,
            "body": {"id": "doc-1", "title": "Demo"},
        }
        with patch(
            "tools.missive_tool._async_get_document", new_callable=AsyncMock
        ) as m:
            m.return_value = async_result
            raw = _handle_get_document({"document_id": "doc-1"})
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["body"]["title"] == "Demo"

    def test_404(self):
        async_result = {
            "status_code": 404,
            "ok": False,
            "error": "document_not_found",
        }
        with patch(
            "tools.missive_tool._async_get_document", new_callable=AsyncMock
        ) as m:
            m.return_value = async_result
            raw = _handle_get_document({"document_id": "missing"})
        payload = json.loads(raw)
        assert payload["status_code"] == 404
        assert payload["error"] == "document_not_found"

    def test_underlying_error_wrapped(self):
        with patch(
            "tools.missive_tool._async_get_document", new_callable=AsyncMock
        ) as m:
            m.side_effect = TimeoutError("slow")
            raw = _handle_get_document({"document_id": "doc-1"})
        payload = json.loads(raw)
        assert "error" in payload
        assert "missive_get_document failed" in payload["error"]


# ---------------------------------------------------------------------------
# check_fn gate
# ---------------------------------------------------------------------------


class TestCheckAvailable:
    def test_disabled_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _check_missive_available() is False

    def test_enabled_when_base_url_set(self):
        with patch.dict(os.environ, {"MISSIVE_BASE_URL": "http://m.local"}, clear=True):
            assert _check_missive_available() is True


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_both_tools_registered(self):
        # importing tools.missive_tool at the top of this file already triggers
        # registry.register(); just assert both are present.
        names = {entry.name for entry in registry._tools.values()}
        assert "missive_health" in names
        assert "missive_get_document" in names

    def test_toolset_is_missive(self):
        entries = {
            name: entry
            for name, entry in registry._tools.items()
            if name in {"missive_health", "missive_get_document"}
        }
        for entry in entries.values():
            assert entry.toolset == "missive"

    def test_check_fn_wired(self):
        entry = registry._tools["missive_health"]
        assert entry.check_fn is _check_missive_available

    def test_schemas_have_required_fields(self):
        health = registry._tools["missive_health"].schema
        doc = registry._tools["missive_get_document"].schema
        assert health["name"] == "missive_health"
        assert doc["name"] == "missive_get_document"
        assert doc["parameters"]["required"] == ["document_id"]
