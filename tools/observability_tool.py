"""Observability bridge tool for ck-observability-bridge skill (ADR-0020 Phase 1, C-3.1).

Native multi-backend tool registering the 4 highest-ROI actions across the
CK_DigitalTunnel observability stack:

- ``prometheus_query`` -- Prometheus instant query (``GET /api/v1/query``).
- ``loki_query_range`` -- Loki LogQL range query (``GET /loki/api/v1/query_range``).
- ``grafana_health`` -- Grafana liveness (``GET /api/health``).
- ``alerts_active`` -- Alertmanager active alerts (``GET /api/v2/alerts``).

Each backend has an independent env var. A tool is exposed via the registry
only when its backend env is set, so partial deployments (e.g. Prom + Loki
only) Just Work.

Env vars:

- ``OBSERVABILITY_PROMETHEUS_URL``
- ``OBSERVABILITY_LOKI_URL``
- ``OBSERVABILITY_GRAFANA_URL`` (+ optional ``OBSERVABILITY_GRAFANA_USER`` /
  ``OBSERVABILITY_GRAFANA_PASS`` for basic auth)
- ``OBSERVABILITY_ALERTMANAGER_URL``
- ``OBSERVABILITY_TIMEOUT_SECONDS`` (optional, default 15)

Plain HTTP is allowed (native tools are not gated by hermes-runtime tirith
plain-HTTP blocks; the hermes-stack docker-compose ships internal
``http://host.docker.internal:N`` URLs by design).

See: docs/plans/hermes-tool-registration-research.md
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _get_timeout() -> float:
    try:
        return float(os.getenv("OBSERVABILITY_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT))
    except ValueError:
        return _DEFAULT_TIMEOUT


def _base(env_name: str) -> str:
    return (os.getenv(env_name) or "").rstrip("/")


def _grafana_basic_auth_header() -> Optional[str]:
    user = os.getenv("OBSERVABILITY_GRAFANA_USER", "")
    password = os.getenv("OBSERVABILITY_GRAFANA_PASS", "")
    if not (user and password):
        return None
    import base64

    cred = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {cred}"


def _common_headers(extra_auth: Optional[str] = None) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if extra_auth:
        headers["Authorization"] = extra_auth
    return headers


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


async def _async_http_get(
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import aiohttp

    timeout = aiohttp.ClientTimeout(total=_get_timeout())
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params, timeout=timeout) as resp:
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


async def _async_prometheus_query(query: str, time: Optional[str] = None) -> Dict[str, Any]:
    base = _base("OBSERVABILITY_PROMETHEUS_URL")
    if not base:
        raise RuntimeError("OBSERVABILITY_PROMETHEUS_URL is not configured")
    params: Dict[str, Any] = {"query": query}
    if time:
        params["time"] = time
    return await _async_http_get(f"{base}/api/v1/query", _common_headers(), params)


async def _async_loki_query_range(
    query: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: Optional[int] = None,
    step: Optional[str] = None,
) -> Dict[str, Any]:
    base = _base("OBSERVABILITY_LOKI_URL")
    if not base:
        raise RuntimeError("OBSERVABILITY_LOKI_URL is not configured")
    params: Dict[str, Any] = {"query": query}
    if start is not None:
        params["start"] = start
    if end is not None:
        params["end"] = end
    if limit is not None:
        params["limit"] = limit
    if step is not None:
        params["step"] = step
    return await _async_http_get(f"{base}/loki/api/v1/query_range", _common_headers(), params)


async def _async_grafana_health() -> Dict[str, Any]:
    base = _base("OBSERVABILITY_GRAFANA_URL")
    if not base:
        raise RuntimeError("OBSERVABILITY_GRAFANA_URL is not configured")
    return await _async_http_get(
        f"{base}/api/health", _common_headers(_grafana_basic_auth_header())
    )


async def _async_alerts_active(
    active: Optional[bool] = None,
    silenced: Optional[bool] = None,
) -> Dict[str, Any]:
    base = _base("OBSERVABILITY_ALERTMANAGER_URL")
    if not base:
        raise RuntimeError("OBSERVABILITY_ALERTMANAGER_URL is not configured")
    params: Dict[str, Any] = {}
    if active is not None:
        params["active"] = "true" if active else "false"
    if silenced is not None:
        params["silenced"] = "true" if silenced else "false"
    return await _async_http_get(
        f"{base}/api/v2/alerts", _common_headers(), params or None
    )


# ---------------------------------------------------------------------------
# Sync handler wrappers
# ---------------------------------------------------------------------------


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


def _handle_prometheus_query(args: dict, **kw) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return tool_error("Missing required parameter: query")
    time = args.get("time")
    try:
        result = _run_async(_async_prometheus_query(query, time))
        return tool_result(result)
    except Exception as e:
        logger.error("prometheus_query error: %s", e)
        return tool_error(f"prometheus_query failed: {e}")


def _handle_loki_query_range(args: dict, **kw) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return tool_error("Missing required parameter: query")
    try:
        result = _run_async(
            _async_loki_query_range(
                query,
                start=args.get("start"),
                end=args.get("end"),
                limit=args.get("limit"),
                step=args.get("step"),
            )
        )
        return tool_result(result)
    except Exception as e:
        logger.error("loki_query_range error: %s", e)
        return tool_error(f"loki_query_range failed: {e}")


def _handle_grafana_health(args: dict, **kw) -> str:
    try:
        result = _run_async(_async_grafana_health())
        return tool_result(result)
    except Exception as e:
        logger.error("grafana_health error: %s", e)
        return tool_error(f"grafana_health failed: {e}")


def _handle_alerts_active(args: dict, **kw) -> str:
    try:
        result = _run_async(
            _async_alerts_active(
                active=args.get("active"),
                silenced=args.get("silenced"),
            )
        )
        return tool_result(result)
    except Exception as e:
        logger.error("alerts_active error: %s", e)
        return tool_error(f"alerts_active failed: {e}")


# ---------------------------------------------------------------------------
# Per-backend availability gates
# ---------------------------------------------------------------------------


def _check_prom() -> bool:
    return bool(os.getenv("OBSERVABILITY_PROMETHEUS_URL"))


def _check_loki() -> bool:
    return bool(os.getenv("OBSERVABILITY_LOKI_URL"))


def _check_grafana() -> bool:
    return bool(os.getenv("OBSERVABILITY_GRAFANA_URL"))


def _check_alert() -> bool:
    return bool(os.getenv("OBSERVABILITY_ALERTMANAGER_URL"))


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------


PROMETHEUS_QUERY_SCHEMA = {
    "name": "prometheus_query",
    "description": (
        "Run an instant Prometheus query against the CKProject observability "
        "stack. Returns {status_code, ok, body} where body is the parsed "
        "Prometheus query response (data.result is a list of vector samples). "
        "Use this for current metric values like 'up{job=\"hermes-gateway\"}' "
        "or 'rate(ck_hermes_requests_total[5m])'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "PromQL expression (e.g. 'up{job=\"hermes-gateway\"}').",
            },
            "time": {
                "type": "string",
                "description": (
                    "Optional evaluation timestamp. RFC3339 (e.g. "
                    "'2026-05-16T10:00:00Z') or unix seconds. Omit for now."
                ),
            },
        },
        "required": ["query"],
    },
}

LOKI_QUERY_RANGE_SCHEMA = {
    "name": "loki_query_range",
    "description": (
        "Run a Loki LogQL range query for log-line aggregation. Returns "
        "{status_code, ok, body} where body is the parsed Loki response. "
        "Use this to inspect recent container logs by label, e.g. "
        "'{container=\"hermes-gateway\"} |= \"error\"'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "LogQL expression (e.g. '{container=\"hermes-gateway\"}').",
            },
            "start": {
                "type": "string",
                "description": "Start time (RFC3339 or nanosecond unix). Optional.",
            },
            "end": {
                "type": "string",
                "description": "End time (RFC3339 or nanosecond unix). Optional.",
            },
            "limit": {
                "type": "integer",
                "description": "Max log lines to return (Loki caps at ~5000). Optional.",
            },
            "step": {
                "type": "string",
                "description": "Aggregation step for metric queries (e.g. '30s'). Optional.",
            },
        },
        "required": ["query"],
    },
}

GRAFANA_HEALTH_SCHEMA = {
    "name": "grafana_health",
    "description": (
        "Probe the Grafana ``/api/health`` endpoint. Returns "
        "{status_code, ok, body:{database, version, commit}}. Use this to "
        "confirm Grafana is reachable before suggesting dashboard URLs."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

ALERTS_ACTIVE_SCHEMA = {
    "name": "alerts_active",
    "description": (
        "List Alertmanager alerts (``GET /api/v2/alerts``). Returns "
        "{status_code, ok, body} where body is a list of alert objects "
        "(labels / annotations / startsAt / state). Use this when the user "
        "asks 'what's firing' or 'any active alerts'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "active": {
                "type": "boolean",
                "description": "If True, include only active (firing) alerts.",
            },
            "silenced": {
                "type": "boolean",
                "description": "If False, exclude silenced alerts.",
            },
        },
        "required": [],
    },
}


from tools.registry import registry, tool_error, tool_result

registry.register(
    name="prometheus_query",
    toolset="observability",
    schema=PROMETHEUS_QUERY_SCHEMA,
    handler=_handle_prometheus_query,
    check_fn=_check_prom,
    requires_env=["OBSERVABILITY_PROMETHEUS_URL"],
    emoji="📊",
)

registry.register(
    name="loki_query_range",
    toolset="observability",
    schema=LOKI_QUERY_RANGE_SCHEMA,
    handler=_handle_loki_query_range,
    check_fn=_check_loki,
    requires_env=["OBSERVABILITY_LOKI_URL"],
    emoji="📜",
)

registry.register(
    name="grafana_health",
    toolset="observability",
    schema=GRAFANA_HEALTH_SCHEMA,
    handler=_handle_grafana_health,
    check_fn=_check_grafana,
    requires_env=["OBSERVABILITY_GRAFANA_URL"],
    emoji="📈",
)

registry.register(
    name="alerts_active",
    toolset="observability",
    schema=ALERTS_ACTIVE_SCHEMA,
    handler=_handle_alerts_active,
    check_fn=_check_alert,
    requires_env=["OBSERVABILITY_ALERTMANAGER_URL"],
    emoji="🚨",
)
