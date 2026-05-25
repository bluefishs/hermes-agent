"""Platform context tool for ck-platform-context skill (ADR-CK-003 v2).

Registers an LLM-callable tool that lets Hermes answer AaaP SSOT meta
questions natively instead of relying on the AaaP Chat backend's
system_prompt injection or (worse) bloating SOUL.md.

Background: 2026-05-22 SOUL injection of SSOT context bloated the
hermes-agent prompt by +1.2KB → Hermes path went from 51s to >120s
timeout. Lesson: SSOT-style data should be reachable via dynamic tool
dispatch, not embedded in every chat's system context.

This tool calls the AaaP backend's existing ``POST /api/overview/
integration-status`` endpoint and returns a compact, LLM-friendly text
summary of the platform (meta + 8 managed projects + tower mapping).

Configuration via env vars:

- ``AAAP_BASE_URL`` -- required; tool is hidden when unset
  (e.g. ``http://host.docker.internal:5201``). Trailing slash tolerated.
- ``AAAP_API_TOKEN`` -- optional bearer token (reserved; AaaP backend
  currently has no auth on this endpoint).
- ``AAAP_TIMEOUT_SECONDS`` -- optional, defaults to 10.

See: docs/plans/lesson-l21-hermes-runtime-dispatching-2026-05-22.md §2.5
     docs/plans/CROSS_SESSION_NEXT_3.md v2.2 #1
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0


def _get_config() -> Dict[str, Any]:
    """Read AaaP config from env at call time (so tests can monkeypatch)."""
    base_url = (os.getenv("AAAP_BASE_URL") or "").rstrip("/")
    token = os.getenv("AAAP_API_TOKEN", "")
    try:
        timeout = float(os.getenv("AAAP_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT))
    except ValueError:
        timeout = _DEFAULT_TIMEOUT
    return {"base_url": base_url, "token": token, "timeout": timeout}


def _build_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _async_fetch_integration_status() -> Dict[str, Any]:
    """POST AaaP /api/overview/integration-status (returns full SSOT projects)."""
    import aiohttp

    cfg = _get_config()
    if not cfg["base_url"]:
        raise RuntimeError("AAAP_BASE_URL is not configured")

    url = f"{cfg['base_url']}/api/overview/integration-status"
    timeout = aiohttp.ClientTimeout(total=cfg["timeout"])
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json={}, headers=_build_headers(cfg["token"]), timeout=timeout
        ) as resp:
            body_text = await resp.text()
            if not (200 <= resp.status < 300):
                raise RuntimeError(
                    f"AaaP /integration-status returned HTTP {resp.status}: {body_text[:300]}"
                )
            try:
                return json.loads(body_text)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"AaaP response not JSON: {e}; body[:300]={body_text[:300]!r}")


def _format_ssot_summary(data: Dict[str, Any], query: str = "") -> str:
    """Format SSOT integration-status response as LLM-friendly text.

    - If query is empty: include meta + tower mapping + all 8 projects (compact).
    - If query is set: include meta + only matching projects (substring match
      on name, case-insensitive); omit tower mapping to keep response focused.
    """
    projects = data.get("projects") or []
    overall = data.get("overall_health")
    active_count = data.get("active_count")
    total_count = data.get("total_count")
    towers = data.get("towers") or {}

    q = (query or "").strip().lower()
    if q:
        projects = [p for p in projects if q in (p.get("name") or "").lower()]

    lines = []
    lines.append("=== CK_AaaP 平臺（SSOT v1.6.1）===")
    if overall is not None:
        lines.append(
            f"整合健康度: {overall}  ({active_count}/{total_count} active projects)"
        )

    if not q and towers:
        lines.append("")
        lines.append("四塔覆蓋率:")
        # towers shape: {tower_name: {coverage, projects, ...}}; defensive read
        for tower_name in ("governance", "observability", "control_plane", "gateway"):
            t = towers.get(tower_name) or {}
            cov = t.get("coverage")
            cov_str = f"{cov}" if cov is not None else "?"
            lines.append(f"  - {tower_name}: {cov_str}")

    lines.append("")
    if q:
        lines.append(f"=== 符合 query={query!r} 的專案（{len(projects)} 筆）===")
    else:
        lines.append(f"=== {len(projects)} 個 SSOT 列管專案 ===")

    if not projects:
        lines.append("  （無符合條目）")
    else:
        for p in projects:
            name = p.get("name", "?")
            desc = (p.get("description") or "").strip()
            st = p.get("integration_status") or {}
            phase = st.get("phase", "?")
            mat = st.get("maturity", "?")
            bridge = st.get("hermes_bridge", "?")
            sub = p.get("subdomain_planned") or "—"
            cf = st.get("cf_tunnel", "—")
            lines.append(
                f"- {name} [{phase}/{mat}] subdomain={sub} cf={cf} bridge={bridge}"
            )
            if desc:
                # Truncate long descriptions to keep prompt size sane
                lines.append(f"    {desc[:160]}")

    lines.append("")
    lines.append(
        "注: SSOT 是治理層 source of truth；live 業務數據（DB 用量 / commit 紀錄 / "
        "即時 metrics）需另呼叫 domain bridge tool 或觀測塔 API。"
    )
    return "\n".join(lines)


def _run_async(coro):
    """Run an async coroutine from sync context, handling both standalone and
    inside-running-loop cases (mirrors missive_tool._run_async)."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    return asyncio.run(coro)


def _handle_get_ssot_context(args: dict, **kw) -> str:
    """Tool handler: fetch + format SSOT summary."""
    query = str(args.get("query") or "").strip()
    try:
        data = _run_async(_async_fetch_integration_status())
        summary = _format_ssot_summary(data, query=query)
        return tool_result({"summary": summary, "projects_returned": len(
            [p for p in (data.get("projects") or [])
             if not query or query.lower() in (p.get("name") or "").lower()]
        )})
    except Exception as e:
        logger.error("aaap_get_ssot_context error: %s", e)
        return tool_error(f"aaap_get_ssot_context failed: {e}")


def _check_aaap_available() -> bool:
    """Toolset is available only when AAAP_BASE_URL is set."""
    return bool(os.getenv("AAAP_BASE_URL"))


AAAP_GET_SSOT_CONTEXT_SCHEMA = {
    "name": "aaap_get_ssot_context",
    "description": (
        "Fetch the CK_AaaP platform SSOT integration-status: 8 managed projects, "
        "their phase/maturity/subdomain/hermes_bridge, plus overall health and "
        "four-tower coverage. Use this whenever the user asks about: managed "
        "projects (列管系統 / 受管專案), platform towers (四塔), bridge skills "
        "across projects, or any cross-project meta question. Returns a compact "
        "text summary; for live business data (DB usage, commit history, real-"
        "time metrics) use the domain-specific bridge tool instead."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Optional substring filter on project name "
                    "(case-insensitive). Leave empty to get all 8 projects "
                    "plus tower mapping."
                ),
            },
        },
        "required": [],
    },
}


from tools.registry import registry, tool_error, tool_result

registry.register(
    name="aaap_get_ssot_context",
    toolset="aaap",
    schema=AAAP_GET_SSOT_CONTEXT_SCHEMA,
    handler=_handle_get_ssot_context,
    check_fn=_check_aaap_available,
    requires_env=["AAAP_BASE_URL"],
    emoji="🏛️",
)
