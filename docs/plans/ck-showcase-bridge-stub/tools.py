"""
ck-showcase-bridge tools — stub-only skeleton (B1 Sprint Step 4)

依 ADR-0021 規範。8 tools 簽名 + register_all 就位；handler 為 stub。
2026-04-25 retro 校準：對應 AaaP rebrand（Showcase repo 已遷入 AaaP platform/services/）。
"""
from __future__ import annotations

import json
import os

SHOWCASE_BASE = os.environ.get("SHOWCASE_BASE_URL", "http://host.docker.internal:5200")
SHOWCASE_TOKEN = os.environ.get("SHOWCASE_API_TOKEN", "")
TIMEOUT_S = float(os.environ.get("SHOWCASE_TIMEOUT_S", "30"))
SAFE_MODE = os.environ.get("SHOWCASE_SAFE_MODE", "true").lower() == "true"


def _err(code: str, msg: str, **extra) -> str:
    return json.dumps({"error": code, "message": msg, **extra}, ensure_ascii=False)


def _stub(tool: str) -> str:
    return _err("not_implemented",
                f"{tool} is stub; ADR-0021 handler pending; CK_AaaP adoption fills handler.",
                tool=tool, base_url=SHOWCASE_BASE)


def showcase_skills_sync_status(project_id: str, include_drift: bool = True) -> str:
    """Tool 1: 跨專案 skill 同步狀態（stub）。"""
    return _stub("showcase_skills_sync_status")


def showcase_agents_list(project_id: str, status_filter: str = "all") -> str:
    """Tool 2: 列出某專案 agent（stub）。"""
    return _stub("showcase_agents_list")


def showcase_security_scan_run(project_id: str, mode: str = "query", scan_type: str = "quick") -> str:
    """Tool 3: 安全掃描（SAFE_MODE 下 mode=run 改 dry-run）。"""
    if mode == "run" and SAFE_MODE:
        return json.dumps({
            "dry_run": True,
            "would_scan": {"project_id": project_id, "scan_type": scan_type},
            "estimated_duration_s": 120 if scan_type == "full" else 30,
            "note": "SHOWCASE_SAFE_MODE=true; set false + confirm to run",
        }, ensure_ascii=False)
    return _stub("showcase_security_scan_run")


def showcase_adr_map_query(project_id: str) -> str:
    """Tool 4: 治理 ADR 地圖查詢（stub；建議與 ck-adr-query 整合）。"""
    return _stub("showcase_adr_map_query")


def showcase_managed_projects_list() -> str:
    """Tool 5: 9 受管專案清單（stub）。"""
    return _stub("showcase_managed_projects_list")


def showcase_sso_status() -> str:
    """Tool 6: SSO 整合狀態（stub）。"""
    return _stub("showcase_sso_status")


def showcase_governance_health() -> str:
    """Tool 7: 治理健康度總覽（stub；對應 4 塔覆蓋率 dashboard）。"""
    return _stub("showcase_governance_health")


def showcase_platform_metrics() -> str:
    """Tool 8: 平臺指標總覽（stub）。"""
    return _stub("showcase_platform_metrics")


def _check_showcase() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{SHOWCASE_BASE}/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def register_all(registry) -> int:
    count = 0
    for fn, desc in [
        (showcase_skills_sync_status, "Cross-project skill sync status (STUB; ADR-0021 Tool 1)."),
        (showcase_agents_list, "List agents in a project (STUB; Tool 2)."),
        (showcase_security_scan_run, "Run security scan (SAFE_MODE dry-run by default; Tool 3)."),
        (showcase_adr_map_query, "Query governance ADR map (STUB; Tool 4)."),
        (showcase_managed_projects_list, "List 9 managed projects (STUB; Tool 5)."),
        (showcase_sso_status, "SSO integration status (STUB; Tool 6)."),
        (showcase_governance_health, "Governance health overview / 4-tower coverage (STUB; Tool 7)."),
        (showcase_platform_metrics, "Platform metrics overview (STUB; Tool 8)."),
    ]:
        registry.register(name=fn.__name__, description=desc, handler=fn, check_fn=_check_showcase)
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
