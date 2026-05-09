"""Tests for gateway/metrics.py.

Exercises the public surface (context managers + render). Skips entirely
when prometheus_client is not installed so CI without the metrics extra
still runs green.
"""
from __future__ import annotations

import pytest

from gateway.metrics import (
    _HAS_PROMETHEUS,
    http_requests_total,
    render_metrics,
    status_class,
    time_http_request,
    time_tool_call,
    tool_calls_total,
)

pytestmark = pytest.mark.skipif(
    not _HAS_PROMETHEUS, reason="prometheus_client not installed"
)


def test_status_class_buckets():
    assert status_class(200) == "2xx"
    assert status_class(301) == "3xx"
    assert status_class(404) == "4xx"
    assert status_class(500) == "5xx"
    assert status_class(599) == "5xx"


def test_time_http_request_increments_counter_for_2xx():
    before = http_requests_total.labels(
        path="chat", method="POST", status_class="2xx"
    )._value.get()
    with time_http_request("chat") as ctx:
        ctx["status"] = 200
    after = http_requests_total.labels(
        path="chat", method="POST", status_class="2xx"
    )._value.get()
    assert after == before + 1


def test_time_http_request_records_500_on_exception():
    before = http_requests_total.labels(
        path="chat", method="POST", status_class="5xx"
    )._value.get()
    with pytest.raises(RuntimeError):
        with time_http_request("chat"):
            raise RuntimeError("boom")
    after = http_requests_total.labels(
        path="chat", method="POST", status_class="5xx"
    )._value.get()
    assert after == before + 1


def test_time_tool_call_records_ok_status():
    before = tool_calls_total.labels(tool="search", status="ok")._value.get()
    with time_tool_call("search"):
        pass
    after = tool_calls_total.labels(tool="search", status="ok")._value.get()
    assert after == before + 1


def test_time_tool_call_records_error_status_on_exception():
    before = tool_calls_total.labels(tool="search", status="error")._value.get()
    with pytest.raises(ValueError):
        with time_tool_call("search"):
            raise ValueError("nope")
    after = tool_calls_total.labels(tool="search", status="error")._value.get()
    assert after == before + 1


def test_time_tool_call_records_timeout_status_on_timeouterror():
    before = tool_calls_total.labels(tool="search", status="timeout")._value.get()
    with pytest.raises(TimeoutError):
        with time_tool_call("search"):
            raise TimeoutError("slow")
    after = tool_calls_total.labels(tool="search", status="timeout")._value.get()
    assert after == before + 1


def test_render_metrics_returns_prometheus_format():
    body, content_type = render_metrics()
    assert content_type.startswith("text/plain")
    assert b"ck_hermes_http_requests_total" in body
    assert b"ck_hermes_tool_calls_total" in body


def test_render_metrics_emits_help_and_type_lines():
    body, _ = render_metrics()
    text = body.decode("utf-8")
    assert "# HELP ck_hermes_http_requests_total" in text
    assert "# TYPE ck_hermes_http_requests_total counter" in text
