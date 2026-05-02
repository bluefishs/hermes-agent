"""
ck-lvrland-bridge tools — Hermes skill loader entry

依 ADR-0024（提案中）規範。3 tools 全 functional，對應 LvrLand 已上線 endpoint：
- /api/v1/ai/query              — Groq+Ollama 混合 RAG
- /api/v1/analytics/price-volume-trends — 房價量時序
- /api/health                   — 標準健康檢查

部署：CK_AaaP session 採納後複製到
  platform/services/docs/hermes-skills/ck-lvrland-bridge/tools.py
runtime 安裝：~/.hermes/skills/ck-lvrland-bridge/tools.py
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# ── Environment ────────────────────────────────────────────
LVRLAND_BASE = os.environ.get("LVRLAND_BASE_URL", "http://host.docker.internal:8002")
LVRLAND_TOKEN = os.environ.get("LVRLAND_API_TOKEN", "")
TIMEOUT_S = float(os.environ.get("LVRLAND_TIMEOUT_S", "30"))
DEFAULT_DISTRICTS = [
    d.strip()
    for d in os.environ.get("LVRLAND_DEFAULT_DISTRICTS", "中壢區,桃園區").split(",")
    if d.strip()
]


# ── Helpers ────────────────────────────────────────────────
def _err(code: str, msg: str, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "error": code,
        "tool": extra.pop("tool", ""),
        "message": msg,
        **extra,
    }
    return json.dumps(payload, ensure_ascii=False)


def _wrap(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _request(
    url: str,
    method: str,
    body: dict[str, Any] | None,
    tool: str,
    timeout: float | None = None,
) -> Any:
    """Issue HTTP request with optional LVRLAND_API_TOKEN bearer auth.

    Returns parsed JSON or _err string. LvrLand defaults to dev mode (no auth);
    token is sent only when set.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if LVRLAND_TOKEN:
        headers["Authorization"] = f"Bearer {LVRLAND_TOKEN}"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT_S) as resp:
            text = resp.read().decode("utf-8")
            if not text:
                return {}
            return json.loads(text)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="ignore")[:300]
        if e.code == 404:
            return _err(
                "backend_endpoint_missing",
                f"LvrLand has not exposed {url}; check backend version.",
                tool=tool, status=404, url=url, hint=body_text,
            )
        return _err("lvrland_http_error", body_text, tool=tool, status=e.code, url=url)
    except urllib.error.URLError as e:
        return _err("lvrland_unreachable", str(e.reason), tool=tool, url=url)
    except json.JSONDecodeError as e:
        return _err("lvrland_invalid_json", str(e), tool=tool, url=url)


# ── Tool 1: lvrland_health ─────────────────────────────────
def lvrland_health(channel: str = "cli", session_id: str = "") -> str:
    """LvrLand backend health check (containers / DB / Ollama)."""
    # Try detail endpoint first (PileMgmt pattern), fall back to GET /api/health
    result = _request(
        f"{LVRLAND_BASE.rstrip('/')}/api/health/detail",
        method="POST",
        body={},
        tool="lvrland_health",
        timeout=10,
    )
    if isinstance(result, str):
        # detail not exposed → fall back to plain health
        plain = _request(
            f"{LVRLAND_BASE.rstrip('/')}/api/health",
            method="GET",
            body=None,
            tool="lvrland_health",
            timeout=5,
        )
        if isinstance(plain, str):
            return plain
        return _wrap({
            "status": (plain.get("status") if isinstance(plain, dict) else "ok") or "ok",
            "source": "plain_health",
            "containers": [],
            "db": {},
        })

    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response", tool="lvrland_health")
    return _wrap({
        "status": result.get("status", "unknown"),
        "source": "detail_endpoint",
        "containers": result.get("containers", []),
        "db": result.get("db", {}),
        "ollama": result.get("ollama", {}),
        "version": result.get("version", ""),
    })


# ── Tool 2: lvrland_query_sync ─────────────────────────────
def lvrland_query_sync(question: str, channel: str = "hermes", session_id: str = "") -> str:
    """Natural-language query to LvrLand /api/v1/ai/query.

    Returns either:
      - {type: "tool_call", tool_name: "map_highlight", arguments: {...}}
        when question hits map keyword + known district
      - {type: "text_response", content: "..."} for general RAG answers
    """
    if not question:
        return _err("missing_arg", "question is required", tool="lvrland_query_sync")
    result = _request(
        f"{LVRLAND_BASE.rstrip('/')}/api/v1/ai/query",
        method="POST",
        body={"question": question},
        tool="lvrland_query_sync",
        timeout=60,
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response", tool="lvrland_query_sync")

    response_type = result.get("type")
    if response_type == "tool_call":
        return _wrap({
            "question": question,
            "type": "tool_call",
            "tool_name": result.get("tool_name", ""),
            "arguments": result.get("arguments", {}),
            "session_id": session_id,
        })
    # default: text_response
    return _wrap({
        "question": question,
        "type": "text_response",
        "content": result.get("content", ""),
        "session_id": session_id,
    })


# ── Tool 3: lvrland_price_trends ───────────────────────────
def lvrland_price_trends(districts: list[str] | str | None = None) -> str:
    """Price + volume trends by district (avg_prices, volumes, building_type_breakdown).

    `districts` accepts:
      - list[str]: ["中壢區", "桃園區"]
      - str: "中壢區,桃園區" (comma-separated, for CLI ergonomics)
      - None: falls back to LVRLAND_DEFAULT_DISTRICTS
    """
    if isinstance(districts, str):
        districts = [d.strip() for d in districts.split(",") if d.strip()]
    if not districts:
        districts = list(DEFAULT_DISTRICTS)
    if not districts:
        return _err(
            "missing_arg",
            "districts is empty and LVRLAND_DEFAULT_DISTRICTS not configured",
            tool="lvrland_price_trends",
        )

    result = _request(
        f"{LVRLAND_BASE.rstrip('/')}/api/v1/analytics/price-volume-trends",
        method="POST",
        body={"districts": districts},
        tool="lvrland_price_trends",
        timeout=30,
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response", tool="lvrland_price_trends")
    return _wrap({
        "districts": districts,
        "trends": result,
    })


# ── Health check ───────────────────────────────────────────
def _check_lvrland() -> bool:
    try:
        headers = {"Authorization": f"Bearer {LVRLAND_TOKEN}"} if LVRLAND_TOKEN else {}
        req = urllib.request.Request(f"{LVRLAND_BASE}/api/health", headers=headers)
        with urllib.request.urlopen(req, timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


# ── Hermes skill loader entry ──────────────────────────────
def register_all(registry: Any) -> int:
    """依 hermes-skill-contract-v2 §2.2 register_all 契約註冊 3 tools."""
    count = 0
    for fn, desc in [
        (lvrland_health,
         "LvrLand backend health check (containers / db / ollama / version)."),
        (lvrland_query_sync,
         "LvrLand natural-language query via /api/v1/ai/query (Groq+Ollama RAG); returns tool_call or text_response."),
        (lvrland_price_trends,
         "LvrLand district price + volume trends time series via /api/v1/analytics/price-volume-trends."),
    ]:
        registry.register(name=fn.__name__, description=desc,
                          handler=fn, check_fn=_check_lvrland)
        count += 1
    return count


# ── CLI for local testing ──────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: tools.py <tool_name> [args...]")
        sys.exit(1)
    tool = sys.argv[1]
    fn = globals().get(tool)
    if not callable(fn):
        print(f"unknown tool: {tool}")
        sys.exit(1)
    print(fn(*sys.argv[2:]))
