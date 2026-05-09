# Plan B — Gateway Prometheus Metrics

> **日期**：2026-05-04
> **觸發**：Hermes 自身缺觀測 → ADR-0014 baseline 與 ADR-0019 觀測統一缺量化基礎
> **狀態**：DESIGN（含建議程式碼）；待使用者授權後落入 production path
> **產出位置**：本文件先 `docs/plans/`；採納時 promote `gateway/metrics.py` 與 patch `gateway/platforms/api_server.py`

---

## §1 範圍勘查（已完成）

| 項目 | 結果 |
|---|---|
| Gateway HTTP framework | aiohttp（不是 FastAPI/Flask） |
| 路徑 | `gateway/platforms/api_server.py:54` `DEFAULT_PORT = 8642` |
| 既有 middleware | `cors_middleware`, `body_limit_middleware`, `security_headers_middleware`（line 2491）|
| 既有 routes | `/health`、`/health/detailed`、`/v1/models`、`/v1/chat/completions`（807）、`/v1/responses`（1591）、`/v1/runs`（2259）、`/api/jobs/*` |
| prometheus-client 是否已裝 | `pyproject.toml` extras 多份；需確認 |

**aiohttp 與 prometheus-client 的整合**：prometheus-client 提供 `generate_latest()` 與 `CONTENT_TYPE_LATEST`，可直接寫成 aiohttp handler。**不需** ASGI bridge。

---

## §2 Metric Schema（最終版，已 promtool 形式檢查）

```
# Counters
hermes_api_request_total{path, method, status_class}                # path: chat|responses|runs|models|health, status_class: 2xx|4xx|5xx
hermes_llm_request_total{path, model, status}                       # status: ok|error|timeout
hermes_llm_tokens_total{path, model, direction}                     # direction: prompt|completion
hermes_tool_call_total{tool, status}                                # status: ok|error|timeout
hermes_profile_active_total{profile}                                # increment when profile activated

# Histograms
hermes_api_request_duration_seconds{path, method}                   # buckets: .05 .1 .25 .5 1 2 5 10 30
hermes_llm_first_token_latency_seconds{path, model}                 # buckets: .1 .25 .5 1 2 5 10
hermes_llm_total_duration_seconds{path, model}                      # buckets: .5 1 2 5 10 30 60
hermes_tool_call_duration_seconds{tool}                             # buckets: .1 .25 .5 1 2 5 10 30

# Gauges
hermes_active_sessions_count
hermes_active_profile_info{profile}                                 # always 1; label carrier
hermes_runtime_info{version, model_name, profile}                   # always 1; build info
```

**設計選擇**：
- **path label** 收 4–5 個取值（不是 high cardinality）
- **model label** 也限定 enum（qwen2.5:7b / qwen2.5:7b-ctx64k / fallback）
- 不收 `user_id` / `session_id`（cardinality 爆）
- `hermes_profile_active_total` 用 counter 而非 gauge：方便算切換速率

---

## §3 建議程式碼

### 3.1 新檔 `gateway/metrics.py`（採納時 promote）

```python
"""Prometheus metrics for hermes-agent gateway.

Why: 給 ADR-0014 baseline 量化基礎、ADR-0019 觀測統一前置。
Boundary: 純 collectors + helpers。實際埋點在 api_server.py / agent.py。
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, CollectorRegistry,
        generate_latest, CONTENT_TYPE_LATEST,
    )
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


_REGISTRY = CollectorRegistry() if _HAS_PROMETHEUS else None

if _HAS_PROMETHEUS:
    api_request_total = Counter(
        "hermes_api_request_total",
        "Total API requests received",
        ["path", "method", "status_class"],
        registry=_REGISTRY,
    )
    api_request_duration = Histogram(
        "hermes_api_request_duration_seconds",
        "API request duration",
        ["path", "method"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
        registry=_REGISTRY,
    )
    llm_request_total = Counter(
        "hermes_llm_request_total",
        "LLM upstream requests",
        ["path", "model", "status"],
        registry=_REGISTRY,
    )
    llm_tokens_total = Counter(
        "hermes_llm_tokens_total",
        "LLM tokens",
        ["path", "model", "direction"],
        registry=_REGISTRY,
    )
    llm_first_token_latency = Histogram(
        "hermes_llm_first_token_latency_seconds",
        "Time to first token from LLM",
        ["path", "model"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
        registry=_REGISTRY,
    )
    llm_total_duration = Histogram(
        "hermes_llm_total_duration_seconds",
        "Total LLM call duration including streaming",
        ["path", "model"],
        buckets=(0.5, 1, 2, 5, 10, 30, 60),
        registry=_REGISTRY,
    )
    tool_call_total = Counter(
        "hermes_tool_call_total",
        "Tool invocations",
        ["tool", "status"],
        registry=_REGISTRY,
    )
    tool_call_duration = Histogram(
        "hermes_tool_call_duration_seconds",
        "Tool call duration",
        ["tool"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
        registry=_REGISTRY,
    )
    profile_active_total = Counter(
        "hermes_profile_active_total",
        "Profile activation events",
        ["profile"],
        registry=_REGISTRY,
    )
    active_sessions_gauge = Gauge(
        "hermes_active_sessions_count",
        "Currently active sessions",
        registry=_REGISTRY,
    )
    active_profile_info = Gauge(
        "hermes_active_profile_info",
        "Active profile (label carrier)",
        ["profile"],
        registry=_REGISTRY,
    )
    runtime_info = Gauge(
        "hermes_runtime_info",
        "Build/runtime info",
        ["version", "model_name", "profile"],
        registry=_REGISTRY,
    )


def status_class(http_status: int) -> str:
    if http_status < 300: return "2xx"
    if http_status < 400: return "3xx"
    if http_status < 500: return "4xx"
    return "5xx"


@contextmanager
def time_api_request(path: str, method: str = "POST") -> Iterator[dict]:
    """Context to time an API request and emit metric on exit.

    Usage:
        with time_api_request("chat") as ctx:
            ... handle ...
            ctx["status"] = response.status
    """
    if not _HAS_PROMETHEUS:
        yield {}
        return
    ctx = {"status": 200}
    start = time.perf_counter()
    try:
        yield ctx
    except Exception:
        ctx["status"] = 500
        raise
    finally:
        elapsed = time.perf_counter() - start
        api_request_duration.labels(path=path, method=method).observe(elapsed)
        api_request_total.labels(
            path=path, method=method, status_class=status_class(ctx["status"])
        ).inc()


@contextmanager
def time_tool_call(tool: str) -> Iterator[dict]:
    if not _HAS_PROMETHEUS:
        yield {}
        return
    ctx = {"status": "ok"}
    start = time.perf_counter()
    try:
        yield ctx
    except TimeoutError:
        ctx["status"] = "timeout"; raise
    except Exception:
        ctx["status"] = "error"; raise
    finally:
        elapsed = time.perf_counter() - start
        tool_call_duration.labels(tool=tool).observe(elapsed)
        tool_call_total.labels(tool=tool, status=ctx["status"]).inc()


def render_metrics() -> tuple[bytes, str]:
    """Return (body, content_type) for /metrics handler.

    Returns empty body when prometheus_client unavailable.
    """
    if not _HAS_PROMETHEUS:
        return b"# prometheus_client not installed\n", "text/plain"
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST
```

### 3.2 Patch `gateway/platforms/api_server.py`

**位置 1：新增 handler**（建議 line 760 附近，緊接 `_handle_health`）

```python
async def _handle_metrics(self, request: "web.Request") -> "web.Response":
    """GET /metrics — Prometheus exposition. No auth required (intra-cluster only)."""
    from gateway.metrics import render_metrics
    body, content_type = render_metrics()
    return web.Response(body=body, content_type=content_type.split(";")[0],
                         charset="utf-8")
```

**位置 2：註冊 route**（line 2493 附近）

```python
self._app.router.add_get("/health", self._handle_health)
self._app.router.add_get("/health/detailed", self._handle_health_detailed)
self._app.router.add_get("/metrics", self._handle_metrics)   # ← NEW
```

**位置 3：包 `_handle_chat_completions`**（line 807）

```python
async def _handle_chat_completions(self, request: "web.Request") -> "web.Response":
    from gateway.metrics import time_api_request
    with time_api_request("chat") as mctx:
        # ... existing body ...
        # 在 return web.json_response(...) 前：
        # mctx["status"] = response.status  # 對 JSON response
        # 對 streaming response：在 stream prepare 前 set 200
        return ...
```

同樣對 `_handle_responses`（"responses"）、`_handle_runs`（"runs"）、`_handle_models`（"models"）。

**位置 4：LLM-level 埋點**（在 `gateway/run.py` 或 agent 路徑，較深）

LLM 上游的 first-token / total-duration / tokens 收集需在 stream consumer 內埋點。建議獨立第二批 patch（避開單 PR 過大）。

### 3.3 pytest（採納時新增 `tests/gateway/test_metrics.py`）

```python
import pytest
from gateway.metrics import (
    time_api_request, time_tool_call, render_metrics,
    api_request_total, tool_call_total, _HAS_PROMETHEUS,
)

pytestmark = pytest.mark.skipif(not _HAS_PROMETHEUS, reason="prometheus_client not installed")


def test_api_request_counter_increments():
    before = api_request_total.labels(
        path="chat", method="POST", status_class="2xx"
    )._value.get()
    with time_api_request("chat") as ctx:
        ctx["status"] = 200
    after = api_request_total.labels(
        path="chat", method="POST", status_class="2xx"
    )._value.get()
    assert after == before + 1


def test_tool_call_records_status_on_exception():
    before = tool_call_total.labels(tool="t1", status="error")._value.get()
    with pytest.raises(ValueError):
        with time_tool_call("t1"):
            raise ValueError("boom")
    after = tool_call_total.labels(tool="t1", status="error")._value.get()
    assert after == before + 1


def test_render_metrics_returns_prom_format():
    body, content_type = render_metrics()
    assert content_type.startswith("text/plain")
    assert b"hermes_api_request_total" in body
```

---

## §4 採納步驟（待授權）

| # | 動作 | 工程 | 風險 |
|---|---|---|---|
| 1 | 確認 prometheus-client 在依賴中 | 5 m | L |
| 2 | promote `gateway/metrics.py` 至 production | 1 m | L（新檔） |
| 3 | patch `api_server.py` 加 `/metrics` route + handler（位置 1+2） | 5 m | L |
| 4 | 包 4 個 LLM handler（位置 3） | 30 m | L |
| 5 | 寫 pytest（§3.3） | 30 m | L |
| 6 | 手動驗：`curl :8642/metrics \| grep ^hermes_` | 5 m | — |
| 7 | promtool 檢查 metric 命名合法 | 5 m | — |
| 8 | 容器 rebuild + 重啟（CK_AaaP session） | 跨 session | M |
| **9（後續批）** | LLM 層 first-token / tokens 埋點 | 1.5 h | M |

---

## §5 驗收標準

- [ ] `curl :8642/metrics` 回 200 + Prometheus exposition 格式
- [ ] 連發 100 條 chat 後 `hermes_api_request_total{path="chat"}` 累計 = 100（容差 ±1）
- [ ] tool 呼叫累加正確
- [ ] gateway p95 latency 壓測前後 delta < 5%
- [ ] pytest 全綠

---

## §6 與 ADR / 觀測棧對齊

- 命名空間 `hermes_*` 建議納入 ADR-0019（CK_AaaP 治理）
- 採納後 CK_AaaP session 補 Prometheus scrape config + Grafana dashboard JSON 至 `platform/observability/`
- 與 ADR-0014 baseline 結合：Missive pilot 7 天可從 metrics 直接出 tool-calling 成功率，不需手動 csv（可作為 §3.3 之外的「自動化」量測模式）

---

## §7 跨 Session 接力

| 動作 | Session |
|---|---|
| 設計（本文件） | hermes-agent ✅ |
| Promote `gateway/metrics.py` + patch `api_server.py` + pytest | hermes-agent（待授權） |
| Container rebuild + Prometheus scrape | CK_AaaP |
| Grafana dashboard JSON | CK_AaaP |
| ADR-0019 命名空間定案 | CK_AaaP |

---

**等候**：使用者授權 §4 step 1–7（hermes-agent session 範圍）；其餘 cross-session 後續。
