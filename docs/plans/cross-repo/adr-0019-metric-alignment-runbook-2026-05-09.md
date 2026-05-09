# Cross-Repo Runbook — ADR-0019 Metric 命名對齊

> **起草**：hermes-agent session @ 2026-05-09
> **執行**：CK_AaaP session（主場）+ CK_Missive session（dual-emit phase）
> **狀態**：DRAFT — 待 CK_AaaP 採納為正式 runbook

---

## §1 背景

ADR-0019（CK_AaaP `adrs/0019-observability-standards.md`，proposed 2026-04-16）統一 5 repo 的 Prometheus 命名為 `ck_<project>_<subsystem>_<name>_<unit>`。當前狀態：

| Repo | Metric 前綴現況 | 對齊行動 |
|---|---|---|
| hermes-agent | ✅ `ck_hermes_*` 已落地（plan-b 2026-05-09） | 完成 |
| CK_Missive | 部分用 `prometheus_middleware.py` 既有命名（未 ck_ 前綴） | 本 runbook §3 |
| CK_DigitalTunnel | Lua + Promtail，命名混雜 | 本 runbook §4 |
| CK_PileMgmt | 觀測模組已落地 | 本 runbook §5 |
| CK_KMapAdvisor | 觀測模組已落地（main.py 整合擱置） | 本 runbook §5 |

---

## §2 強制 5 項（ADR-0019 §X）

每個 repo 的 service 至少要暴露：

```
ck_<project>_http_requests_total{path,method,status_class}
ck_<project>_http_request_duration_seconds{path,method}     histogram
ck_<project>_db_pool_active                                 gauge
ck_<project>_process_rss_bytes                              gauge
ck_<project>_info{version,...}                              gauge=1 label carrier
```

領域選配示例：
- Missive: `ck_missive_kg_entities_total`, `ck_missive_doc_chunks_total`
- Hermes: `ck_hermes_agent_turns_total`, `ck_hermes_tool_calls_total{tool,status}`
- Pile: `ck_pile_yolov8_inference_seconds_bucket`

---

## §3 CK_Missive 對齊步驟（CK_Missive session）

1. **盤點**：`grep -rn "Counter\|Histogram\|Gauge" backend/app/core/*metrics*.py` 列出所有 metric 名。
2. **加 alias 階段（Dual-emit，2 週）**：
   ```python
   from prometheus_client import Counter
   _legacy = Counter("missive_http_requests_total", ...)
   _v2 = Counter("ck_missive_http_requests_total", ...)
   def inc(...):
       _legacy.labels(...).inc(); _v2.labels(...).inc()
   ```
   兩名同時 emit，給 Grafana dashboard 漸進切換時間。
3. **更新 dashboard JSON**：將 panel query 從舊名改 `ck_missive_*`。
4. **2 週後刪 legacy**：刪 `_legacy` Counter，僅留 v2。
5. **alembic 不需動**（只是運行時 metric 名）。

---

## §4 CK_DigitalTunnel 對齊（DT session 或 CK_AaaP）

- **Promtail label**：`labelmap` rules 加 `ck_dt_*` 前綴。
- **Loki LogQL**：`{ck_project="ck-platform-node-exporter"}` → `{ck_project="ck_platform"}`（兼用 dual emission）。
- **Lua 自定 metric**（若有）：rename 至 `ck_dt_*`。

---

## §5 CK_PileMgmt / CK_KMapAdvisor 對齊（各 repo session）

- 兩個觀測模組為新建，命名直接用 `ck_pile_*` / `ck_kmap_*` 起手不需 dual-emit。
- KMapAdvisor 整合擱置 — 整合恢復時順道命名對齊。

---

## §6 hermes-agent 已交付（參考）

```
gateway/metrics.py             # 12 metrics ck_hermes_*
gateway/platforms/api_server.py  # metrics_middleware auto-instrument
tests/gateway/test_metrics.py    # 8 cases
```

---

## §7 CK_AaaP 採納 checklist

- [ ] 本 runbook promote 至 `runbooks/observability/adr-0019-rollout.md`
- [ ] ADR-0019 status: proposed → accepted（補一句「ck_hermes_* 2026-05-09 已驗收」）
- [ ] Prometheus scrape config 加 hermes-gateway:8642/metrics
- [ ] Grafana：建 `Hermes Gateway Overview` dashboard JSON
- [ ] 5 repo 完成 dual-emit 後，2 週切換期 sunset legacy

---

## §8 接力協議

| Step | Session | Owner |
|---|---|---|
| Runbook 採納 | CK_AaaP | platform |
| Missive dual-emit | CK_Missive | backend |
| DT label rename | CK_AaaP/DT | observability |
| Pile/KMap 直命名 | 各 repo | 各 owner |
| Grafana JSON | CK_AaaP | platform |
| Sunset legacy | 各 repo | 各 owner |
