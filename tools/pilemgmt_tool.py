"""PileMgmt bridge tool for ck-pilemgmt-bridge skill (ADR-0020 Phase 1, C-3.3).

Native tool covering the 2 implemented actions on CK_PileMgmt backend:

- ``pile_health`` -- ``GET /api/health`` (no auth)
- ``pile_celery_status`` -- ``POST /api/celery/status`` (Bearer token)

Skipped: ``ai_query`` — backend endpoint /api/ai/query is not implemented
yet per ck-pilemgmt-bridge-stub ADR note. Add when the backend ships.

Env vars:

- ``PILE_BASE_URL`` -- required; tool hidden when unset.
- ``PILE_API_TOKEN`` -- required for ``pile_celery_status`` only (per-call gate
  inside the handler; the toolset itself stays enabled whenever
  ``PILE_BASE_URL`` is set so the LLM can probe health without a token).
- ``PILE_TIMEOUT_SECONDS`` -- optional, default 30 (celery state may be slow).

See: docs/plans/hermes-tool-registration-research.md
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0

# Celery queue names are user-defined but practically ascii [a-zA-Z0-9_-].
import re as _re

_QUEUE_FILTER_RE = _re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _get_config() -> Dict[str, Any]:
    base = (os.getenv("PILE_BASE_URL") or "").rstrip("/")
    token = os.getenv("PILE_API_TOKEN", "")
    try:
        timeout = float(os.getenv("PILE_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT))
    except ValueError:
        timeout = _DEFAULT_TIMEOUT
    return {"base_url": base, "token": token, "timeout": timeout}


def _build_headers(token: str = "", json_body: bool = False) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if json_body:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _async_health() -> Dict[str, Any]:
    import aiohttp

    cfg = _get_config()
    if not cfg["base_url"]:
        raise RuntimeError("PILE_BASE_URL is not configured")

    url = f"{cfg['base_url']}/api/health"
    timeout = aiohttp.ClientTimeout(total=cfg["timeout"])
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_build_headers(), timeout=timeout) as resp:
            body_text = await resp.text()
            try:
                body = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                body = {"raw": body_text[:500]}
            return {
                "status_code": resp.status,
                "ok": 200 <= resp.status < 300,
                "body": body,
            }


async def _async_celery_status(queue_filter: Optional[str] = None) -> Dict[str, Any]:
    import aiohttp

    cfg = _get_config()
    if not cfg["base_url"]:
        raise RuntimeError("PILE_BASE_URL is not configured")
    if not cfg["token"]:
        raise RuntimeError("PILE_API_TOKEN is required for celery_status")

    url = f"{cfg['base_url']}/api/celery/status"
    body: Dict[str, Any] = {}
    if queue_filter:
        body["queue_filter"] = queue_filter

    timeout = aiohttp.ClientTimeout(total=cfg["timeout"])
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=_build_headers(cfg["token"], json_body=True),
            json=body,
            timeout=timeout,
        ) as resp:
            body_text = await resp.text()
            try:
                parsed = json.loads(body_text) if body_text else {}
            except json.JSONDecodeError:
                parsed = {"raw": body_text[:1000]}
            return {
                "status_code": resp.status,
                "ok": 200 <= resp.status < 300,
                "body": parsed,
            }


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=60)
    return asyncio.run(coro)


def _handle_health(args: dict, **kw) -> str:
    try:
        return tool_result(_run_async(_async_health()))
    except Exception as e:
        logger.error("pile_health error: %s", e)
        return tool_error(f"pile_health failed: {e}")


def _handle_celery_status(args: dict, **kw) -> str:
    queue_filter = args.get("queue_filter")
    if queue_filter is not None:
        queue_filter = str(queue_filter).strip()
        if queue_filter and not _QUEUE_FILTER_RE.match(queue_filter):
            return tool_error(f"Invalid queue_filter: {queue_filter!r}")
        if not queue_filter:
            queue_filter = None
    try:
        return tool_result(_run_async(_async_celery_status(queue_filter)))
    except Exception as e:
        logger.error("pile_celery_status error: %s", e)
        return tool_error(f"pile_celery_status failed: {e}")


def _check_pile_available() -> bool:
    return bool(os.getenv("PILE_BASE_URL"))


PILE_HEALTH_SCHEMA = {
    "name": "pile_health",
    "description": (
        "Probe the CK_PileMgmt backend liveness endpoint. Returns "
        "{status_code, ok, body}. Use this first before celery_status."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

PILE_CELERY_STATUS_SCHEMA = {
    "name": "pile_celery_status",
    "description": (
        "Get CK_PileMgmt Celery worker / queue status (active / scheduled / "
        "reserved tasks, worker liveness). Requires PILE_API_TOKEN; returns "
        "an error if the token is missing. Use this when the user asks about "
        "background job health on the Pile side."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "queue_filter": {
                "type": "string",
                "description": (
                    "Optional queue name (alphanumeric / . / _ / -). If "
                    "provided, the backend returns only that queue's status."
                ),
            },
        },
        "required": [],
    },
}


from tools.registry import registry, tool_error, tool_result

registry.register(
    name="pile_health",
    toolset="pilemgmt",
    schema=PILE_HEALTH_SCHEMA,
    handler=_handle_health,
    check_fn=_check_pile_available,
    requires_env=["PILE_BASE_URL"],
    emoji="🏗️",
)

registry.register(
    name="pile_celery_status",
    toolset="pilemgmt",
    schema=PILE_CELERY_STATUS_SCHEMA,
    handler=_handle_celery_status,
    check_fn=_check_pile_available,
    requires_env=["PILE_BASE_URL"],
    emoji="🏗️",
)
