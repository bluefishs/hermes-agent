"""
ck-showcase-bridge tools — Hermes skill loader entry

依 ADR-0021 規範。8 tools 全實作；security_scan_run 與 SHOWCASE_SAFE_MODE 雙閘。
2026-04-25 retro 校準：Showcase 已遷入 AaaP platform/services/。

部署：CK_AaaP session 採納後複製到
  platform/services/docs/hermes-skills/ck-showcase-bridge/tools.py
runtime 安裝：~/.hermes/skills/ck-showcase-bridge/tools.py
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# ── Environment ────────────────────────────────────────────
SHOWCASE_BASE = os.environ.get("SHOWCASE_BASE_URL", "http://host.docker.internal:5200")
SHOWCASE_TOKEN = os.environ.get("SHOWCASE_API_TOKEN", "")
TIMEOUT_S = float(os.environ.get("SHOWCASE_TIMEOUT_S", "30"))
SAFE_MODE = os.environ.get("SHOWCASE_SAFE_MODE", "true").lower() == "true"


# ── Helpers ────────────────────────────────────────────────
def _err(code: str, msg: str, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "error": code,
        "tool": extra.pop("tool", ""),
        "message": msg,
        **extra,
    }
    return json.dumps(payload, ensure_ascii=False)


def _post(path: str, body: dict[str, Any], tool: str, timeout: float | None = None) -> Any:
    """POST JSON to Showcase API. Returns parsed JSON or _err string on failure."""
    url = f"{SHOWCASE_BASE.rstrip('/')}{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if SHOWCASE_TOKEN:
        headers["Authorization"] = f"Bearer {SHOWCASE_TOKEN}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout or TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="ignore")[:300]
        return _err("showcase_http_error", body_text, tool=tool, status=e.code, url=url)
    except urllib.error.URLError as e:
        return _err("showcase_unreachable", str(e.reason), tool=tool, url=url)


def _wrap(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


# ── Tool 1: showcase_managed_projects_list ─────────────────
def showcase_managed_projects_list(
    include_retired: bool = False,
    channel: str = "cli",
    session_id: str = "",
) -> str:
    """List 8 managed projects with metadata."""
    result = _post(
        "/api/overview/projects",
        {"include_retired": include_retired},
        tool="showcase_managed_projects_list",
    )
    if isinstance(result, str):
        return result
    projects = result.get("projects", []) if isinstance(result, dict) else []
    return _wrap({
        "include_retired": include_retired,
        "total": len(projects),
        "projects": projects,
    })


# ── Tool 2: showcase_adr_map_query ─────────────────────────
def showcase_adr_map_query(
    project_id: str,
    status_filter: str = "",
    limit: int = 10,
    channel: str = "cli",
    session_id: str = "",
) -> str:
    """Query ADR knowledge map for a managed project."""
    if not project_id:
        return _err("missing_arg", "project_id is required",
                    tool="showcase_adr_map_query")
    body: dict[str, Any] = {"project_id": project_id, "limit": limit}
    if status_filter:
        body["status_filter"] = status_filter
    result = _post("/api/adr-map/query", body, tool="showcase_adr_map_query")
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_adr_map_query")
    return _wrap({
        "project_id": project_id,
        "status_filter": status_filter or None,
        "limit": limit,
        "summary": result.get("summary", {}),
        "recent": result.get("recent", []),
    })


# ── Tool 3: showcase_governance_health ─────────────────────
def showcase_governance_health(project_id: str = "", channel: str = "cli", session_id: str = "") -> str:
    """Cross-project governance health overview (omit project_id for platform-wide)."""
    body: dict[str, Any] = {}
    if project_id:
        body["project_id"] = project_id
    result = _post("/api/overview/governance-health", body,
                   tool="showcase_governance_health")
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_governance_health")
    return _wrap({
        "project_id": project_id or None,
        "by_project": result.get("by_project", {}),
        "overall": result.get("overall", {}),
    })


# ── Tool 4: showcase_platform_metrics ──────────────────────
def showcase_platform_metrics(window: str = "30d", channel: str = "cli", session_id: str = "") -> str:
    """Platform-level metrics (ADRs / skills / agents / security trends)."""
    if window not in ("7d", "30d", "90d"):
        return _err("bad_arg",
                    f"window must be one of 7d/30d/90d (got {window})",
                    tool="showcase_platform_metrics")
    result = _post("/api/overview/platform-metrics", {"window": window},
                   tool="showcase_platform_metrics")
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_platform_metrics")
    return _wrap({
        "window": window,
        "metrics": result.get("metrics", {}),
        "generated_at": result.get("generated_at", ""),
    })


# ── Tool 5: showcase_skills_sync_status ────────────────────
def showcase_skills_sync_status(project_id: str, include_drift: bool = True) -> str:
    """Skills sync status (last pull / count / drift list) for one project."""
    if not project_id:
        return _err("missing_arg", "project_id is required",
                    tool="showcase_skills_sync_status")
    result = _post(
        "/api/skills/sync-status",
        {"project_id": project_id, "include_drift": include_drift},
        tool="showcase_skills_sync_status",
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_skills_sync_status")
    return _wrap({
        "project_id": project_id,
        "last_sync_at": result.get("last_sync_at", ""),
        "count": result.get("count", 0),
        "drift": result.get("drift", []) if include_drift else None,
    })


# ── Tool 6: showcase_agents_list ───────────────────────────
def showcase_agents_list(project_id: str, status_filter: str = "active") -> str:
    """List agents for a project; status_filter = active|all."""
    if not project_id:
        return _err("missing_arg", "project_id is required",
                    tool="showcase_agents_list")
    if status_filter not in ("active", "all"):
        return _err("bad_arg", "status_filter must be active|all",
                    tool="showcase_agents_list")
    result = _post(
        "/api/agents/list",
        {"project_id": project_id, "status_filter": status_filter},
        tool="showcase_agents_list",
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_agents_list")
    agents = result.get("agents", [])
    return _wrap({
        "project_id": project_id,
        "status_filter": status_filter,
        "total": len(agents),
        "agents": agents,
    })


# ── Tool 7: showcase_security_scan_run ─────────────────────
def showcase_security_scan_run(
    project_id: str,
    mode: str = "query",
    scan_type: str = "quick",
) -> str:
    """OWASP security scan. SAFE_MODE forces dry-run; mode='query' previews only."""
    if not project_id:
        return _err("missing_arg", "project_id is required",
                    tool="showcase_security_scan_run")
    if mode not in ("query", "run"):
        return _err("bad_arg", "mode must be query|run",
                    tool="showcase_security_scan_run")
    if scan_type not in ("quick", "full"):
        return _err("bad_arg", "scan_type must be quick|full",
                    tool="showcase_security_scan_run")

    if mode == "query" or SAFE_MODE:
        return _wrap({
            "dry_run": True,
            "reason": "SHOWCASE_SAFE_MODE=true" if SAFE_MODE else "mode=query",
            "would_scan": {"project_id": project_id, "scan_type": scan_type},
            "estimated_duration_s": 120 if scan_type == "full" else 30,
            "note": "set SHOWCASE_SAFE_MODE=false and pass mode='run' to actually scan",
        })

    result = _post(
        "/api/security/scan",
        {"project_id": project_id, "mode": "run", "scan_type": scan_type},
        tool="showcase_security_scan_run",
        timeout=60,
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_security_scan_run")
    return _wrap({
        "project_id": project_id,
        "scan_type": scan_type,
        "scan_id": result.get("scan_id", ""),
        "findings_count": len(result.get("findings", [])),
        "findings": result.get("findings", []),
    })


# ── Tool 8: showcase_sso_status ────────────────────────────
def showcase_sso_status(project_id: str) -> str:
    """SSO / Auth middleware status. 2026-04 Showcase SSO 尚未實作 → 多回 enabled=false."""
    if not project_id:
        return _err("missing_arg", "project_id is required",
                    tool="showcase_sso_status")
    result = _post(
        "/api/system-config/sso-status",
        {"project_id": project_id},
        tool="showcase_sso_status",
    )
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return _err("unexpected_response", "non-dict response",
                    tool="showcase_sso_status")
    return _wrap({
        "project_id": project_id,
        "enabled": bool(result.get("enabled", False)),
        "provider": result.get("provider", ""),
        "active_users": result.get("active_users", 0),
    })


# ── Health check ───────────────────────────────────────────
def _check_showcase() -> bool:
    try:
        with urllib.request.urlopen(f"{SHOWCASE_BASE}/api/health", timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


# ── Hermes skill loader entry ──────────────────────────────
def register_all(registry: Any) -> int:
    """依 hermes-skill-contract-v2 §2.2 register_all 契約註冊 8 tools."""
    count = 0
    for fn, desc in [
        (showcase_managed_projects_list,
         "List 8 CK managed projects with status / phase / homepage metadata."),
        (showcase_adr_map_query,
         "Query ADR knowledge map for a managed project (status filter + recent N)."),
        (showcase_governance_health,
         "Cross-project governance health overview; omit project_id for platform-wide."),
        (showcase_platform_metrics,
         "Platform-level metrics (ADRs / skills / agents / security trends; window 7d/30d/90d)."),
        (showcase_skills_sync_status,
         "Skills sync status (last pull, count, drift list) for one project."),
        (showcase_agents_list,
         "List agents (active|all) for a managed project."),
        (showcase_security_scan_run,
         "OWASP security scan; SAFE_MODE/mode=query forces dry-run; mode='run' triggers."),
        (showcase_sso_status,
         "SSO / Auth middleware status (provider, active users)."),
    ]:
        registry.register(name=fn.__name__, description=desc,
                          handler=fn, check_fn=_check_showcase)
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
