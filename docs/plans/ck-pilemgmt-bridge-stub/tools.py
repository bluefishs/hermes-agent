"""
ck-pilemgmt-bridge tools — stub-only skeleton (B1 Sprint Step 3)

依 ADR-0023 規範。3 tools 簽名 + register_all 就位；handler 為 stub。
CK_AaaP 採納時填 handler；參考 ck-missive-bridge v2.0 模式。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

PILE_BASE = os.environ.get("PILE_BASE_URL", "http://host.docker.internal:8004")
PILE_TOKEN = os.environ.get("PILE_API_TOKEN", "")
TIMEOUT_S = float(os.environ.get("PILE_TIMEOUT_S", "30"))


def _err(code: str, msg: str, **extra) -> str:
    return json.dumps({"error": code, "message": msg, **extra}, ensure_ascii=False)


def _stub(tool: str) -> str:
    return _err("not_implemented",
                f"{tool} is stub; ADR-0023 handler pending. CK_AaaP adoption + PileMgmt API alignment required.",
                tool=tool, base_url=PILE_BASE)


def pile_health() -> str:
    """Tool 1: PileMgmt backend 健康度（目前 stub）。"""
    return _stub("pile_health")


def pile_query_sync(question: str, channel: str = "hermes") -> str:
    """Tool 2: 自然語言查詢 PileMgmt（stub；需 PileMgmt 側加 /api/ai/query 端點）。"""
    return _stub("pile_query_sync")


def pile_celery_status() -> str:
    """Tool 3: PileMgmt celery worker 狀態（stub）。"""
    return _stub("pile_celery_status")


def _check_pile() -> bool:
    try:
        req = urllib.request.Request(f"{PILE_BASE}/api/health",
                                     headers={"Authorization": f"Bearer {PILE_TOKEN}"} if PILE_TOKEN else {})
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def register_all(registry) -> int:
    count = 0
    for fn, desc in [
        (pile_health, "PileMgmt backend health detail (STUB; ADR-0023 Tool 1)."),
        (pile_query_sync, "PileMgmt natural language query (STUB; ADR-0023 Tool 2)."),
        (pile_celery_status, "PileMgmt celery worker queue status (STUB; ADR-0023 Tool 3)."),
    ]:
        registry.register(name=fn.__name__, description=desc, handler=fn, check_fn=_check_pile)
        count += 1
    return count


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: tools.py <tool>")
        sys.exit(1)
    fn = globals().get(sys.argv[1])
    if not callable(fn):
        sys.exit(1)
    print(fn(*sys.argv[2:]))
