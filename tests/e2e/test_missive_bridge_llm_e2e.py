"""LLM-driven e2e for ck-missive-bridge (B-4 Sprint B upgrade of mock baseline).

Builds on top of ``test_missive_bridge_e2e.py``'s ``_MockMissiveServer``
fixture and adds a real LLM in the loop:

  user prompt
    → OpenAI-compatible /v1/chat/completions on ck-ollama (qwen2.5:7b)
    → LLM emits a tool_call referencing ``missive_health``
    → we dispatch the tool_call into ``_handle_health``
    → handler hits the in-process aiohttp mock server (TCP socket)
    → mock server records the request

The chain proves end-to-end that the tool *schema* is understood by a real
LLM and that the registry+native-tool wiring actually routes a model
emission to a working HTTP socket.

## Why Ollama, not Anthropic

ADR-0014 / [[architecture-retro-2026-05-18]] document that the Anthropic
credit gate has blocked full LLM-driven verification for over a month.
ck-ollama (RTX 4060, local) runs qwen2.5:7b — confirmed to support
OpenAI-style ``tools`` / ``tool_calls`` payloads. This unblocks the e2e
without any cost or external dependency.

## Gating

Skipped unless ``HERMES_E2E_LLM=ollama`` (or any truthy value) AND the
Ollama endpoint is reachable. The CI mock-baseline lane stays the always-on
guard; this is an opt-in deeper lane.

Run locally:
    HERMES_E2E_LLM=ollama pytest tests/e2e/test_missive_bridge_llm_e2e.py
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

import pytest

from .test_missive_bridge_e2e import _server  # type: ignore


# ---------------------------------------------------------------------------
# Configuration / gating
# ---------------------------------------------------------------------------

OLLAMA_URL = os.getenv("HERMES_E2E_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("HERMES_E2E_OLLAMA_MODEL", "qwen2.5:7b")
LLM_GATE = os.getenv("HERMES_E2E_LLM", "").strip().lower()


def _ollama_reachable() -> bool:
    if not LLM_GATE:
        return False
    if LLM_GATE not in {"ollama", "1", "true", "yes"}:
        return False
    try:
        with socket.create_connection(("localhost", 11434), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_reachable(),
    reason=(
        "LLM-driven e2e disabled. Set HERMES_E2E_LLM=ollama + ensure "
        f"{OLLAMA_URL} reachable to enable."
    ),
)


# ---------------------------------------------------------------------------
# OpenAI-compatible chat helper (stdlib urllib — no SDK dependency)
# ---------------------------------------------------------------------------


def _chat_with_tools(
    *,
    user_prompt: str,
    tools: list[dict[str, Any]],
    system: str = "You are a helpful Traditional Chinese assistant. Call tools when relevant.",
    timeout: int = 60,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "tools": tools,
            # Force tool use bias; qwen2.5 honours it. Lower temp = more
            # deterministic in CI.
            "temperature": 0.1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# Tool schema mirrors the OpenAI tool spec emitted by the native tool
# registry. Keep in sync with ``tools/missive_tool.py``'s registry entry.
MISSIVE_HEALTH_TOOL = {
    "type": "function",
    "function": {
        "name": "missive_health",
        "description": "Check whether the Missive backend (CK 公文管理系統) is alive. Returns status/version.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_llm_emits_missive_health_tool_call_and_hits_mock_socket(monkeypatch):
    """Happy path: user asks zh-TW about Missive → LLM tool_call → mock socket."""
    from tools.missive_tool import _handle_health

    with _server() as srv:
        srv.script("/health", 200, {"status": "ok", "version": "5.5.8"})
        monkeypatch.setenv("MISSIVE_BASE_URL", srv.base_url)
        monkeypatch.delenv("MISSIVE_API_TOKEN", raising=False)

        completion = _chat_with_tools(
            user_prompt="幫我看看 Missive 還好嗎？",
            tools=[MISSIVE_HEALTH_TOOL],
        )

        choice = completion["choices"][0]
        msg = choice["message"]
        tool_calls = msg.get("tool_calls") or []
        # The LLM must elect to call the tool. If it didn't, surface the
        # text response in the assertion message so we can debug model
        # behaviour without re-running.
        assert tool_calls, (
            "LLM did not emit a tool_call. Raw assistant message: "
            f"{json.dumps(msg, ensure_ascii=False)}"
        )

        # Pick the first call that targets missive_health.
        target = next(
            (
                c
                for c in tool_calls
                if c.get("function", {}).get("name") == "missive_health"
            ),
            None,
        )
        assert target is not None, (
            f"No tool_call named missive_health. Got: {[c['function']['name'] for c in tool_calls]}"
        )

        # Dispatch into the native tool handler. Arguments may be "{}" or "".
        raw_args = target["function"].get("arguments") or "{}"
        args = json.loads(raw_args) if raw_args.strip() else {}
        raw = _handle_health(args)
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["status_code"] == 200
        assert payload["body"]["version"] == "5.5.8"

        # The mock server saw exactly one GET /health request.
        assert len(srv.requests) == 1
        req = srv.requests[0]
        assert req["method"] == "GET"
        assert req["path"] == "/health"


def test_llm_endpoint_returns_openai_compatible_shape():
    """Smoke: confirms Ollama exposes the OpenAI shape we depend on.

    If this breaks, the project either lost the qwen2.5 image or someone
    swapped Ollama for a non-compatible runtime. Fail fast with a clear
    pointer instead of letting the happy-path test fail mysteriously.
    """
    completion = _chat_with_tools(
        user_prompt="Reply with the single word: ok",
        tools=[],
    )
    assert "choices" in completion and completion["choices"], completion
    choice = completion["choices"][0]
    assert "message" in choice
    assert "role" in choice["message"]
