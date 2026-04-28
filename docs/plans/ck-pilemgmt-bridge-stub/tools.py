"""
ck-pilemgmt-bridge tools — Hermes skill loader entry

依 ADR-0023 規範。3 tools 全實作。
pile_query_sync 在 PileMgmt 補 /api/ai/query 端點前回 backend_endpoint_missing
（404 結構化錯誤 + 提示），不阻擋其他 tool 上線。

部署：CK_AaaP session 採納後複製到
  platform/services/docs/hermes-skills/ck-pilemgmt-bridge/tools.py
runtime 安裝：~/.hermes/skills/ck-pilemgmt-bridge/tools.py
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# ── Environment ────────────────────────────────────────────
PILE_BASE = os.environ.get("PILE_BASE_URL", "http://host.docker.internal:8004")
PILE_TOKEN = os.environ.get("PILE_API_TOKEN", "")
TIMEOUT_S = float(os.environ.get("PILE_TIMEOUT_S", "30"))
FLOWER_URL = os.environ.get("PILE_CELERY_FLOWER_URL", "")


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
    """Issue HTTP request with PILE_TOKEN bearer auth. Returns parsed JSON or _err string."""
    headers: dict[str, str] = {"Accept": "application/json"}
    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if PILE_TOKEN:
        headers["Authorization"] = f"Bearer {PILE_TOKEN}"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="ignore")[:300]
        if e.code == 404:
            return _err("backend_endpoint_missing",
                        f"PileMgmt has not exposed {url}; see ADR-0023 Tool 2 status.",
                        tool=tool, status=404, url=url, hint=body_text)
        return _err("pile_http_error", body_text, tool=tool, status=e.code, url=url)
    except urllib.error.URLError as e:
        return _err("pile_unreachable", str(e.reason), tool=tool, url=url)


# ── Tool 1: pile_health ────────────────────────────────────
def pile_health(channel: str = "cli", session_id: str = "") -> str:
    """List PileMgmt container/DB/celery health."""
    result = _request(
        f"{PILE_BASE.rstrip('/')}/api/health/detail",
        method="POST",
        body={},
        tool="pile_health",
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response", tool="pile_health")
    return _wrap({
        "status": result.get("status", "unknown"),
        "containers": result.get("containers", []),
        "db": result.get("db", {}),
        "celery": result.get("celery", {}),
        "version": result.get("version", ""),
    })


# ── Tool 2: pile_query_sync ────────────────────────────────
def pile_query_sync(question: str, channel: str = "hermes", session_id: str = "") -> str:
    """Natural-language query to PileMgmt /api/ai/query (returns 404 hint until backend ships)."""
    if not question:
        return _err("missing_arg", "question is required", tool="pile_query_sync")
    result = _request(
        f"{PILE_BASE.rstrip('/')}/api/ai/query",
        method="POST",
        body={"question": question, "channel": channel, "session_id": session_id},
        tool="pile_query_sync",
        timeout=60,
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="pile_query_sync")
    return _wrap({
        "question": question,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "session_id": session_id,
    })


# ── Tool 3: pile_celery_status ─────────────────────────────
def pile_celery_status(queue_filter: str = "") -> str:
    """Celery job aggregate. Falls back to Flower /api/tasks when primary endpoint is missing."""
    result = _request(
        f"{PILE_BASE.rstrip('/')}/api/celery/status",
        method="POST",
        body={"queue_filter": queue_filter},
        tool="pile_celery_status",
    )
    if isinstance(result, dict):
        return _wrap({
            "source": "pile_celery_endpoint",
            "queue_filter": queue_filter or None,
            "active": result.get("active", []),
            "scheduled": result.get("scheduled", []),
            "reserved": result.get("reserved", []),
            "workers": result.get("workers", []),
        })

    # primary failed; try Flower fallback if configured
    if FLOWER_URL:
        flower_result = _request(
            f"{FLOWER_URL.rstrip('/')}/api/tasks",
            method="GET",
            body=None,
            tool="pile_celery_status",
        )
        if isinstance(flower_result, dict):
            tasks = list(flower_result.values())
            active = [t for t in tasks if t.get("state") == "STARTED"]
            scheduled = [t for t in tasks if t.get("state") == "RECEIVED"]
            return _wrap({
                "source": "flower_fallback",
                "queue_filter": queue_filter or None,
                "active": active,
                "scheduled": scheduled,
                "reserved": [],
                "workers": [],
                "note": "Flower fallback used; primary /api/celery/status not reachable",
            })

    # both failed; surface primary error
    return result  # type: ignore[no-any-return]


# ── Health check ───────────────────────────────────────────
def _check_pile() -> bool:
    try:
        headers = {"Authorization": f"Bearer {PILE_TOKEN}"} if PILE_TOKEN else {}
        req = urllib.request.Request(f"{PILE_BASE}/api/health", headers=headers)
        with urllib.request.urlopen(req, timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


# ── Hermes skill loader entry ──────────────────────────────
def register_all(registry: Any) -> int:
    """依 hermes-skill-contract-v2 §2.2 register_all 契約註冊 3 tools."""
    count = 0
    for fn, desc in [
        (pile_health,
         "PileMgmt backend health detail (containers / db / celery / version)."),
        (pile_query_sync,
         "PileMgmt natural-language query via /api/ai/query (returns 404 hint until backend exposes it)."),
        (pile_celery_status,
         "Celery job aggregate (active/scheduled/reserved); falls back to Flower /api/tasks."),
    ]:
        registry.register(name=fn.__name__, description=desc,
                          handler=fn, check_fn=_check_pile)
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
