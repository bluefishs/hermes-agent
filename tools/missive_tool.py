"""Missive bridge tool for ck-missive-bridge skill (ADR-0020 Phase 1, B-1).

Registers two LLM-callable tools that the ck-missive-bridge skill instructs
the model to call when answering questions backed by CK_Missive:

- ``missive_health`` -- probe CK_Missive ``GET /health`` for liveness + service
  versions. No parameters.
- ``missive_get_document`` -- fetch a single document via
  ``GET /api/v1/documents/{document_id}``.

Configuration via env vars:

- ``MISSIVE_BASE_URL`` -- required; tool is hidden when unset
  (e.g. ``http://localhost:8002``). Trailing slash tolerated.
- ``MISSIVE_API_TOKEN`` -- optional bearer token. If set, sent as
  ``Authorization: Bearer <token>``.
- ``MISSIVE_TIMEOUT_SECONDS`` -- optional, defaults to 15.

See: docs/plans/hermes-tool-registration-research.md
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Path-traversal / SSRF guard. CK_Missive ids in practice are short alnum/uuid;
# refuse anything with slashes, dots, or unicode so the
# /api/v1/documents/{id} URL cannot be reshaped.
_DOCUMENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

_DEFAULT_TIMEOUT = 15.0


def _get_config() -> Dict[str, Any]:
    """Read Missive config from env at call time (so tests can monkeypatch)."""
    base_url = (os.getenv("MISSIVE_BASE_URL") or "").rstrip("/")
    token = os.getenv("MISSIVE_API_TOKEN", "")
    try:
        timeout = float(os.getenv("MISSIVE_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT))
    except ValueError:
        timeout = _DEFAULT_TIMEOUT
    return {"base_url": base_url, "token": token, "timeout": timeout}


def _build_headers(token: str) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _async_health() -> Dict[str, Any]:
    """Probe ``GET /health`` on the configured Missive instance."""
    import aiohttp

    cfg = _get_config()
    if not cfg["base_url"]:
        raise RuntimeError("MISSIVE_BASE_URL is not configured")

    url = f"{cfg['base_url']}/health"
    timeout = aiohttp.ClientTimeout(total=cfg["timeout"])
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_build_headers(cfg["token"]), timeout=timeout) as resp:
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


async def _async_get_document(document_id: str) -> Dict[str, Any]:
    """Fetch a single Missive document by id."""
    import aiohttp

    cfg = _get_config()
    if not cfg["base_url"]:
        raise RuntimeError("MISSIVE_BASE_URL is not configured")

    url = f"{cfg['base_url']}/api/v1/documents/{document_id}"
    timeout = aiohttp.ClientTimeout(total=cfg["timeout"])
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_build_headers(cfg["token"]), timeout=timeout) as resp:
            if resp.status == 404:
                return {"status_code": 404, "ok": False, "error": "document_not_found"}
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


def _run_async(coro):
    """Run an async coroutine from a sync tool handler."""
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
        result = _run_async(_async_health())
        return tool_result(result)
    except Exception as e:
        logger.error("missive_health error: %s", e)
        return tool_error(f"missive_health failed: {e}")


def _handle_get_document(args: dict, **kw) -> str:
    document_id = (args.get("document_id") or "").strip()
    if not document_id:
        return tool_error("Missing required parameter: document_id")
    if not _DOCUMENT_ID_RE.match(document_id):
        return tool_error(f"Invalid document_id format: {document_id!r}")
    try:
        result = _run_async(_async_get_document(document_id))
        return tool_result(result)
    except Exception as e:
        logger.error("missive_get_document error: %s", e)
        return tool_error(f"missive_get_document failed: {e}")


def _check_missive_available() -> bool:
    """Toolset is available only when MISSIVE_BASE_URL is set."""
    return bool(os.getenv("MISSIVE_BASE_URL"))


MISSIVE_HEALTH_SCHEMA = {
    "name": "missive_health",
    "description": (
        "Probe the CK_Missive backend liveness endpoint. Returns HTTP status "
        "code and the parsed /health JSON body (typically {status, services, "
        "version}). Use this first when the user asks if Missive is reachable "
        "before attempting document queries."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MISSIVE_GET_DOCUMENT_SCHEMA = {
    "name": "missive_get_document",
    "description": (
        "Fetch a single CK_Missive document by id. Returns the raw document "
        "JSON when found (status 200), or {status_code: 404, error: "
        "'document_not_found'} when missing. Use this after the user names a "
        "specific document id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": (
                    "The Missive document id (alphanumeric / dash / underscore, "
                    "1-128 chars). Slashes, dots, and unicode are rejected."
                ),
            },
        },
        "required": ["document_id"],
    },
}


from tools.registry import registry, tool_error, tool_result

registry.register(
    name="missive_health",
    toolset="missive",
    schema=MISSIVE_HEALTH_SCHEMA,
    handler=_handle_health,
    check_fn=_check_missive_available,
    requires_env=["MISSIVE_BASE_URL"],
    emoji="📨",
)

registry.register(
    name="missive_get_document",
    toolset="missive",
    schema=MISSIVE_GET_DOCUMENT_SCHEMA,
    handler=_handle_get_document,
    check_fn=_check_missive_available,
    requires_env=["MISSIVE_BASE_URL"],
    emoji="📨",
)
