"""Prometheus metrics for hermes-agent gateway.

Naming aligns with ADR-0019 (CK_AaaP) ck_<project>_<subsystem>_<name>_<unit>.
Boundary: pure collectors + helpers. Actual emission lives in api_server.py.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


_REGISTRY = CollectorRegistry() if _HAS_PROMETHEUS else None

if _HAS_PROMETHEUS:
    http_requests_total = Counter(
        "ck_hermes_http_requests_total",
        "Total API requests received",
        ["path", "method", "status_class"],
        registry=_REGISTRY,
    )
    http_request_duration_seconds = Histogram(
        "ck_hermes_http_request_duration_seconds",
        "API request duration",
        ["path", "method"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
        registry=_REGISTRY,
    )
    llm_requests_total = Counter(
        "ck_hermes_llm_requests_total",
        "LLM upstream requests",
        ["path", "model", "status"],
        registry=_REGISTRY,
    )
    llm_tokens_total = Counter(
        "ck_hermes_llm_tokens_total",
        "LLM tokens by direction",
        ["path", "model", "direction"],
        registry=_REGISTRY,
    )
    llm_first_token_latency_seconds = Histogram(
        "ck_hermes_llm_first_token_latency_seconds",
        "Time to first token from LLM",
        ["path", "model"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
        registry=_REGISTRY,
    )
    llm_total_duration_seconds = Histogram(
        "ck_hermes_llm_total_duration_seconds",
        "Total LLM call duration including streaming",
        ["path", "model"],
        buckets=(0.5, 1, 2, 5, 10, 30, 60),
        registry=_REGISTRY,
    )
    tool_calls_total = Counter(
        "ck_hermes_tool_calls_total",
        "Tool invocations",
        ["tool", "status"],
        registry=_REGISTRY,
    )
    tool_call_duration_seconds = Histogram(
        "ck_hermes_tool_call_duration_seconds",
        "Tool call duration",
        ["tool"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
        registry=_REGISTRY,
    )
    profile_activations_total = Counter(
        "ck_hermes_profile_activations_total",
        "Profile activation events",
        ["profile"],
        registry=_REGISTRY,
    )
    active_sessions = Gauge(
        "ck_hermes_active_sessions",
        "Currently active sessions",
        registry=_REGISTRY,
    )
    active_profile_info = Gauge(
        "ck_hermes_active_profile_info",
        "Active profile (label carrier; value always 1)",
        ["profile"],
        registry=_REGISTRY,
    )
    info = Gauge(
        "ck_hermes_info",
        "Build/runtime info (label carrier; value always 1)",
        ["version", "model_name", "profile"],
        registry=_REGISTRY,
    )


def status_class(http_status: int) -> str:
    if http_status < 300:
        return "2xx"
    if http_status < 400:
        return "3xx"
    if http_status < 500:
        return "4xx"
    return "5xx"


@contextmanager
def time_http_request(path: str, method: str = "POST") -> Iterator[dict]:
    """Time an HTTP request, emit counter + histogram on exit.

    The caller may set ctx["status"] before exiting to record the actual code;
    on uncaught exception we record 500.
    """
    if not _HAS_PROMETHEUS:
        yield {}
        return
    ctx: dict = {"status": 200}
    start = time.perf_counter()
    try:
        yield ctx
    except Exception:
        ctx["status"] = 500
        raise
    finally:
        elapsed = time.perf_counter() - start
        http_request_duration_seconds.labels(path=path, method=method).observe(elapsed)
        http_requests_total.labels(
            path=path, method=method, status_class=status_class(ctx["status"])
        ).inc()


@contextmanager
def time_tool_call(tool: str) -> Iterator[dict]:
    """Time a tool invocation; sets status=ok|error|timeout based on exception."""
    if not _HAS_PROMETHEUS:
        yield {}
        return
    ctx: dict = {"status": "ok"}
    start = time.perf_counter()
    try:
        yield ctx
    except TimeoutError:
        ctx["status"] = "timeout"
        raise
    except Exception:
        ctx["status"] = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        tool_call_duration_seconds.labels(tool=tool).observe(elapsed)
        tool_calls_total.labels(tool=tool, status=ctx["status"]).inc()


def render_metrics() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics handler.

    When prometheus_client is unavailable we return a stub so /metrics keeps
    answering 200 (avoids breaking scrapers; loud comment line is human-readable).
    """
    if not _HAS_PROMETHEUS:
        return b"# prometheus_client not installed\n", "text/plain"
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST
