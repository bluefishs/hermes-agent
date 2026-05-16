"""Showcase bridge tool for ck-showcase-bridge skill (ADR-0020 Phase 1, C-3.2).

Native tool covering the 3 highest-ROI actions of CK_Showcase governance API:

- ``showcase_health`` -- ``GET /api/health``
- ``showcase_managed_projects`` -- ``POST /api/overview/projects`` (no body args)
- ``showcase_governance_health`` -- ``POST /api/overview/governance-health``
  (per project_id)

Env vars:

- ``SHOWCASE_BASE_URL`` -- required; tool hidden when unset.
- ``SHOWCASE_API_TOKEN`` -- optional bearer.
- ``SHOWCASE_TIMEOUT_SECONDS`` -- optional, defaults 15.

CK_Showcase is also planned to migrate into CK_AaaP/platform/services
(ADR-0020 Phase 2); when that happens, only the env value changes —
schemas and handlers remain stable.

See: docs/plans/hermes-tool-registration-research.md
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Project ids in CK_Showcase governance are repo names like "ck_missive",
# "ck_aaap"; constrain to lowercase alphanumeric + underscore + dash to
# prevent path injection when echoed back into URLs by future endpoints.
_PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

_DEFAULT_TIMEOUT = 15.0


def _get_config() -> Dict[str, Any]:
    base = (os.getenv("SHOWCASE_BASE_URL") or "").rstrip("/")
    token = os.getenv("SHOWCASE_API_TOKEN", "")
    try:
        timeout = float(os.getenv("SHOWCASE_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT))
    except ValueError:
        timeout = _DEFAULT_TIMEOUT
    return {"base_url": base, "token": token, "timeout": timeout}


def _build_headers(token: str, json_body: bool = False) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if json_body:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _async_http(
    method: str,
    path: str,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import aiohttp

    cfg = _get_config()
    if not cfg["base_url"]:
        raise RuntimeError("SHOWCASE_BASE_URL is not configured")

    url = f"{cfg['base_url']}{path}"
    timeout = aiohttp.ClientTimeout(total=cfg["timeout"])
    headers = _build_headers(cfg["token"], json_body=json_body is not None)

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url, headers=headers, json=json_body, timeout=timeout
        ) as resp:
            body_text = await resp.text()
            try:
                body = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                body = {"raw": body_text[:1000]}
            return {
                "status_code": resp.status,
                "ok": 200 <= resp.status < 300,
                "body": body,
            }


async def _async_health() -> Dict[str, Any]:
    return await _async_http("GET", "/api/health")


async def _async_managed_projects() -> Dict[str, Any]:
    return await _async_http("POST", "/api/overview/projects", json_body={})


async def _async_governance_health(project_id: str) -> Dict[str, Any]:
    return await _async_http(
        "POST",
        "/api/overview/governance-health",
        json_body={"project_id": project_id},
    )


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    return asyncio.run(coro)


def _handle_health(args: dict, **kw) -> str:
    try:
        return tool_result(_run_async(_async_health()))
    except Exception as e:
        logger.error("showcase_health error: %s", e)
        return tool_error(f"showcase_health failed: {e}")


def _handle_managed_projects(args: dict, **kw) -> str:
    try:
        return tool_result(_run_async(_async_managed_projects()))
    except Exception as e:
        logger.error("showcase_managed_projects error: %s", e)
        return tool_error(f"showcase_managed_projects failed: {e}")


def _handle_governance_health(args: dict, **kw) -> str:
    project_id = (args.get("project_id") or "").strip()
    if not project_id:
        return tool_error("Missing required parameter: project_id")
    if not _PROJECT_ID_RE.match(project_id):
        return tool_error(f"Invalid project_id format: {project_id!r}")
    try:
        return tool_result(_run_async(_async_governance_health(project_id)))
    except Exception as e:
        logger.error("showcase_governance_health error: %s", e)
        return tool_error(f"showcase_governance_health failed: {e}")


def _check_showcase_available() -> bool:
    return bool(os.getenv("SHOWCASE_BASE_URL"))


SHOWCASE_HEALTH_SCHEMA = {
    "name": "showcase_health",
    "description": (
        "Probe the CK_Showcase governance API liveness endpoint. Returns "
        "{status_code, ok, body}. Use this first to confirm Showcase is "
        "reachable before listing managed projects or querying governance."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SHOWCASE_MANAGED_PROJECTS_SCHEMA = {
    "name": "showcase_managed_projects",
    "description": (
        "List all repos managed by CK_Showcase governance (e.g. ck_missive, "
        "ck_aaap, ck_lvrland_webmap). Returns the parsed JSON list under "
        "body. Use this when the user asks 'what projects do we have' or "
        "needs a project_id to feed into showcase_governance_health."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SHOWCASE_GOVERNANCE_HEALTH_SCHEMA = {
    "name": "showcase_governance_health",
    "description": (
        "Query per-project governance health (ADR coverage, doc drift, "
        "skill sync state) by project_id. Use after showcase_managed_projects "
        "tells you which ids are valid."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": (
                    "Repo name (lowercase, e.g. 'ck_missive'). Letters, "
                    "digits, underscore, dash only; 1-64 chars."
                ),
            },
        },
        "required": ["project_id"],
    },
}


from tools.registry import registry, tool_error, tool_result

registry.register(
    name="showcase_health",
    toolset="showcase",
    schema=SHOWCASE_HEALTH_SCHEMA,
    handler=_handle_health,
    check_fn=_check_showcase_available,
    requires_env=["SHOWCASE_BASE_URL"],
    emoji="🪟",
)

registry.register(
    name="showcase_managed_projects",
    toolset="showcase",
    schema=SHOWCASE_MANAGED_PROJECTS_SCHEMA,
    handler=_handle_managed_projects,
    check_fn=_check_showcase_available,
    requires_env=["SHOWCASE_BASE_URL"],
    emoji="🪟",
)

registry.register(
    name="showcase_governance_health",
    toolset="showcase",
    schema=SHOWCASE_GOVERNANCE_HEALTH_SCHEMA,
    handler=_handle_governance_health,
    check_fn=_check_showcase_available,
    requires_env=["SHOWCASE_BASE_URL"],
    emoji="🪟",
)
