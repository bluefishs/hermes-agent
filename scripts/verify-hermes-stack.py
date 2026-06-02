#!/usr/bin/env python3
"""End-to-end probe for the running hermes-stack (CK_AaaP/runbooks/hermes-stack).

This is the "demo-ready" gate Memo
[[feedback-pre-demo-functional-verification]] requires: before claiming
"hermes-stack is demo-ready / user can chat", run this script and read the
JSON output line-by-line.

Four layers of probe, in increasing depth:

1. Connectivity   — TCP + /health on each container port. No auth, no LLM.
2. Auth           — :8642 /v1/models with API_SERVER_KEY Bearer. Confirms
                    Gateway-layer Bearer check passes (this is the 401 path
                    in gateway/platforms/api_server.py:760-772, often
                    confused with upstream-LLM 401 — see L21 diagnose).
3. LLM dispatch   — :8642 /v1/chat/completions with minimal prompt. Confirms
                    _resolve_runtime_agent_kwargs() resolved a working
                    provider AND the LLM responded. Gated by
                    HERMES_E2E_REAL_STACK=1 (default skipped, since this
                    actually hits a paid LLM key OR your local ck-ollama).
4. Skill dispatch — :8642 /v1/chat/completions with a REAL domain query
                    ("目前系統有幾份公文？"). Asserts the agent actually
                    dispatches ck-missive-bridge instead of hallucinating
                    `from hermes_tools import ...` code (the 2026-05-31 NO-GO
                    bug). FAIL if any HALLUCINATION_MARKERS appears. This is
                    the gate that distinguishes "LLM replies" (L3) from
                    "agent reaches the skill and returns data" (L4). Gated by
                    HERMES_E2E_REAL_STACK=1.

Usage::

    python scripts/verify-hermes-stack.py                    # layer 1+2 only
    HERMES_E2E_REAL_STACK=1 python scripts/verify-hermes-stack.py    # all 4
    python scripts/verify-hermes-stack.py --gateway-port 8642 --web-port 9119

Env vars consulted::

    API_SERVER_KEY            — Bearer for :8642 (required for layer 2)
    HERMES_E2E_REAL_STACK     — "1" to run layer 3 + 4 (LLM + skill dispatch)
    HERMES_E2E_PROMPT         — override layer 3 prompt (default 繁中 minimal)
    HERMES_E2E_SKILL_PROMPT   — override layer 4 domain query (default 公文總數)
    HERMES_E2E_MODEL          — override model id for L3/L4 (else auto-detected
                                from /v1/models, e.g. "meta"; fallback "meta")

Output: one JSON object per probe to stdout. Exit code 0 if every enabled
layer succeeds; non-zero if any fails. Layer 1 / 2 failure does NOT abort
later probes (so a single run gives you the full picture, mapping to L21
diagnose §1 lines A/B/C in one shot).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Optional

TIMEOUT_S = 10
DEFAULT_PROMPT = "回應一個字：好"
# Layer 4 — skill dispatch. This is the probe the 2026-05-31 NO-GO turned on:
# a minimal LLM reply (L3) can pass while the agent still FAILS to dispatch
# ck-missive-bridge (writes hallucinated `from hermes_tools import ...` code
# instead of running `python3 scripts/query.py`). L4 asserts a real domain
# query actually reaches the skill and returns data.
DEFAULT_SKILL_PROMPT = "目前系統有幾份公文？"
# Markers that prove the agent hallucinated instead of dispatching the skill.
HALLUCINATION_MARKERS = (
    "from hermes_tools",
    "import hermes",
    "terminal(command",
    "没有找到",          # 簡中「找不到工具/公文」降級語
    "找不到工具",
    "ck-missive-bridge 工具",
    "AI 服務暫時不可用",  # Missive agent LLM 生成層降級 canned fallback
)


@dataclass
class ProbeResult:
    layer: int
    name: str
    target: str
    status: str  # "OK" | "FAIL" | "SKIP"
    detail: str = ""
    elapsed_ms: int = 0
    extra: dict = field(default_factory=dict)


def _tcp_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_get(url: str, headers: Optional[dict] = None, timeout: float = TIMEOUT_S):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    return urllib.request.urlopen(req, timeout=timeout)


def _http_post_json(url: str, payload: dict, headers: Optional[dict] = None, timeout: float = TIMEOUT_S):
    data = json.dumps(payload).encode("utf-8")
    hdr = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def probe_l1_connectivity(host: str, port: int, label: str) -> ProbeResult:
    t0 = time.monotonic()
    ok = _tcp_open(host, port)
    elapsed = int((time.monotonic() - t0) * 1000)
    if not ok:
        return ProbeResult(1, f"tcp:{label}", f"{host}:{port}", "FAIL", "connection refused", elapsed)
    return ProbeResult(1, f"tcp:{label}", f"{host}:{port}", "OK", elapsed_ms=elapsed)


def probe_l1_health(host: str, port: int, path: str, label: str) -> ProbeResult:
    url = f"http://{host}:{port}{path}"
    t0 = time.monotonic()
    try:
        with _http_get(url, timeout=5) as resp:
            body = resp.read(2048).decode("utf-8", errors="replace")
            elapsed = int((time.monotonic() - t0) * 1000)
            return ProbeResult(1, f"health:{label}", url, "OK", body[:200], elapsed, {"status": resp.status})
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return ProbeResult(1, f"health:{label}", url, "FAIL", f"HTTP {e.code}", elapsed, {"status": e.code})
    except (urllib.error.URLError, socket.timeout) as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return ProbeResult(1, f"health:{label}", url, "FAIL", f"unreachable: {e}", elapsed)


def probe_l2_models(host: str, port: int, api_key: Optional[str]) -> ProbeResult:
    url = f"http://{host}:{port}/v1/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    t0 = time.monotonic()
    try:
        with _http_get(url, headers=headers, timeout=5) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            elapsed = int((time.monotonic() - t0) * 1000)
            try:
                parsed = json.loads(body)
                models = [m.get("id") for m in parsed.get("data", [])]
            except Exception:
                models = []
            extra = {"status": resp.status, "models": models, "auth_sent": bool(api_key)}
            return ProbeResult(2, "auth:/v1/models", url, "OK", body[:200], elapsed, extra)
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        body = e.read(1024).decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        # 401 here is the api_server.py:_check_auth path. Surface that explicitly.
        diag = f"HTTP {e.code}"
        if e.code == 401:
            diag += " — Gateway Bearer auth failed (check API_SERVER_KEY in hermes-stack/.env matches client). NOT an upstream LLM 401."
        return ProbeResult(2, "auth:/v1/models", url, "FAIL", f"{diag} · {body[:150]}", elapsed, {"status": e.code, "auth_sent": bool(api_key)})
    except (urllib.error.URLError, socket.timeout) as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return ProbeResult(2, "auth:/v1/models", url, "FAIL", f"unreachable: {e}", elapsed, {"auth_sent": bool(api_key)})


def probe_l3_dispatch(host: str, port: int, api_key: Optional[str], prompt: str, model: str = "meta") -> ProbeResult:
    url = f"http://{host}:{port}/v1/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    t0 = time.monotonic()
    try:
        with _http_post_json(url, payload, headers=headers, timeout=60) as resp:
            body = resp.read(8192).decode("utf-8", errors="replace")
            elapsed = int((time.monotonic() - t0) * 1000)
            try:
                parsed = json.loads(body)
                content = ""
                if parsed.get("choices"):
                    content = parsed["choices"][0].get("message", {}).get("content", "")[:200]
                provider = parsed.get("system_fingerprint") or "<unknown>"
            except Exception:
                content = "<unparseable>"
                provider = "<unknown>"
            extra = {"status": resp.status, "content_preview": content, "provider_fingerprint": provider}
            return ProbeResult(3, "dispatch:/v1/chat/completions", url, "OK", content, elapsed, extra)
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        body = e.read(2048).decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        diag = f"HTTP {e.code}"
        if e.code == 401:
            diag += " — either Gateway Bearer OR upstream LLM auth. Check container logs to distinguish."
        return ProbeResult(3, "dispatch:/v1/chat/completions", url, "FAIL", f"{diag} · {body[:200]}", elapsed, {"status": e.code})
    except (urllib.error.URLError, socket.timeout) as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return ProbeResult(3, "dispatch:/v1/chat/completions", url, "FAIL", f"network: {e}", elapsed)


def probe_l4_skill_dispatch(host: str, port: int, api_key: Optional[str], prompt: str, model: str = "meta") -> ProbeResult:
    """Assert the agent actually dispatches a skill for a real domain query.

    Success = HTTP 200 + non-empty content + NO hallucination marker.
    A FAIL here with a hallucination marker is the exact L21/2026-05-31
    dispatching bug (agent sees the skill in its prompt but doesn't know how
    to run it). Latency is reported so a slow-but-correct path is still visible.
    """
    url = f"http://{host}:{port}/v1/chat/completions"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    t0 = time.monotonic()
    try:
        with _http_post_json(url, payload, headers=headers, timeout=120) as resp:
            body = resp.read(16384).decode("utf-8", errors="replace")
            elapsed = int((time.monotonic() - t0) * 1000)
            content = ""
            tools_used = []
            try:
                parsed = json.loads(body)
                if parsed.get("choices"):
                    content = parsed["choices"][0].get("message", {}).get("content", "") or ""
                # some gateways surface tool calls; capture if present (best-effort)
                tools_used = parsed.get("tools_used") or parsed.get("choices", [{}])[0].get("tools_used", []) or []
            except Exception:
                content = "<unparseable>"
            hit = next((m for m in HALLUCINATION_MARKERS if m in content), None)
            extra = {
                "status": resp.status,
                "content_preview": content[:200],
                "tools_used": tools_used,
                "elapsed_s": round(elapsed / 1000, 1),
            }
            if hit:
                return ProbeResult(
                    4, "skill_dispatch:公文總數", url, "FAIL",
                    f"agent 未真正呼叫 skill（命中幻覺/降級標記 '{hit}'）", elapsed, extra,
                )
            if not content.strip():
                return ProbeResult(4, "skill_dispatch:公文總數", url, "FAIL", "空回應", elapsed, extra)
            return ProbeResult(4, "skill_dispatch:公文總數", url, "OK", content[:80], elapsed, extra)
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        body = e.read(2048).decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return ProbeResult(4, "skill_dispatch:公文總數", url, "FAIL", f"HTTP {e.code} · {body[:200]}", elapsed, {"status": e.code})
    except (urllib.error.URLError, socket.timeout) as e:
        elapsed = int((time.monotonic() - t0) * 1000)
        return ProbeResult(4, "skill_dispatch:公文總數", url, "FAIL", f"network: {e}", elapsed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--gateway-port", type=int, default=8642, help="hermes-gateway OpenAI-compat port")
    parser.add_argument("--web-port", type=int, default=9119, help="hermes-web port")
    parser.add_argument("--openwebui-port", type=int, default=3000, help="Open WebUI port (optional)")
    parser.add_argument("--skip-openwebui", action="store_true", help="Skip Open WebUI probe (it's optional)")
    parser.add_argument("--json", action="store_true", help="Output one JSON object per line (machine-readable)")
    args = parser.parse_args()

    results: list[ProbeResult] = []

    # Layer 1 — connectivity
    results.append(probe_l1_connectivity(args.host, args.gateway_port, "gateway"))
    results.append(probe_l1_connectivity(args.host, args.web_port, "web"))
    if not args.skip_openwebui:
        results.append(probe_l1_connectivity(args.host, args.openwebui_port, "openwebui"))

    # Layer 1 — /health on gateway
    results.append(probe_l1_health(args.host, args.gateway_port, "/health", "gateway"))

    # Layer 2 — auth (only meaningful if gateway TCP is open)
    api_key = os.environ.get("API_SERVER_KEY")
    if results[0].status == "OK":
        results.append(probe_l2_models(args.host, args.gateway_port, api_key))
    else:
        results.append(ProbeResult(2, "auth:/v1/models", f"{args.host}:{args.gateway_port}", "SKIP", "gateway TCP unreachable"))

    # Resolve the model id for L3/L4 from the /v1/models response (the active
    # profile id, e.g. "meta") so we don't hardcode a wrong name. Env override
    # HERMES_E2E_MODEL wins; else first id from L2; else "meta".
    _l2 = results[-1]
    _discovered = (_l2.extra.get("models") or [None])[0] if _l2.extra else None
    model_id = os.environ.get("HERMES_E2E_MODEL") or _discovered or "meta"

    # Layer 3 — LLM dispatch
    if os.environ.get("HERMES_E2E_REAL_STACK") == "1":
        if results[0].status == "OK":
            prompt = os.environ.get("HERMES_E2E_PROMPT", DEFAULT_PROMPT)
            results.append(probe_l3_dispatch(args.host, args.gateway_port, api_key, prompt, model_id))
        else:
            results.append(ProbeResult(3, "dispatch:/v1/chat/completions", f"{args.host}:{args.gateway_port}", "SKIP", "gateway TCP unreachable"))
    else:
        results.append(ProbeResult(3, "dispatch:/v1/chat/completions", "", "SKIP", "HERMES_E2E_REAL_STACK not set"))

    # Layer 4 — skill dispatch (real domain query → ck-missive-bridge)
    if os.environ.get("HERMES_E2E_REAL_STACK") == "1":
        if results[0].status == "OK":
            skill_prompt = os.environ.get("HERMES_E2E_SKILL_PROMPT", DEFAULT_SKILL_PROMPT)
            results.append(probe_l4_skill_dispatch(args.host, args.gateway_port, api_key, skill_prompt, model_id))
        else:
            results.append(ProbeResult(4, "skill_dispatch:公文總數", f"{args.host}:{args.gateway_port}", "SKIP", "gateway TCP unreachable"))
    else:
        results.append(ProbeResult(4, "skill_dispatch:公文總數", "", "SKIP", "HERMES_E2E_REAL_STACK not set"))

    # Output
    if args.json:
        for r in results:
            print(json.dumps(asdict(r), ensure_ascii=False))
    else:
        print(f"\n{'Layer':<6}{'Status':<8}{'Probe':<32}{'Elapsed':>8}  Detail")
        print("-" * 90)
        for r in results:
            print(f"L{r.layer:<5}{r.status:<8}{r.name:<32}{r.elapsed_ms:>6}ms  {r.detail[:60]}")
            if r.extra:
                extra_str = " · ".join(f"{k}={v}" for k, v in r.extra.items() if v not in (None, "", []))
                if extra_str:
                    print(f"{'':<14}{'':<32}{'':<8}    [{extra_str[:80]}]")

    # Exit code: any non-SKIP failure → non-zero
    fail_count = sum(1 for r in results if r.status == "FAIL")
    print(f"\n{fail_count} failure(s), {sum(1 for r in results if r.status == 'OK')} ok, {sum(1 for r in results if r.status == 'SKIP')} skipped")
    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
