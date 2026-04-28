---
name: ck-observability-bridge
version: 0.1.0
description: CK 平臺觀測棧橋接 — Loki 日誌、Prometheus 指標、Grafana 儀表板、Alertmanager 警報之自然語言聚合查詢。
author: CK Platform Team
license: MIT
metadata:
  hermes:
    tags: [CK, Observability, Loki, Prometheus, Grafana, Alertmanager, Monitoring]
    homepage: http://192.168.50.210:3001
prerequisites:
  env_vars: [OBS_LOKI_URL, OBS_PROMETHEUS_URL, OBS_GRAFANA_URL]
---

# CK Observability Bridge — Hermes Skill v0.1

把 CK 平臺 PLG 觀測棧（Loki / Promtail / Grafana / Prometheus / Alertmanager）
透過 Hermes 暴露為自然語言入口。

> **本 skill 為 source**（ADR-0022 規範；ADR-0025 分割策略說明為何 observability 從
> CK_DigitalTunnel 遷入 AaaP）。部署由 hermes-agent session 透過 install.sh 或
> docker compose cp 植入 `~/.hermes/skills/`。
>
> **注意**：Phase 3 DigitalTunnel 觀測棧未遷入 AaaP 前，`OBS_*_URL` 預設指向
> DigitalTunnel 自 host 位置；遷入後改指 `platform/observability/` 新網路的 endpoint。

## 架構

```
Hermes Agent
  └─ ck-observability-bridge skill
       ├─ tools.py         6 tools 動態註冊（或靜態 fallback）
       ├─ tool_spec.json   6 tools 契約
       └─ SKILL.md         prompt context
              │
              ▼
       PLG stack（目前 CK_DigitalTunnel host；Phase 3 後 platform/observability/）
       Loki / Prom / Grafana / Alertmanager
```

## 部署

```bash
bash install.sh [~/.hermes/skills/ck-observability-bridge]
# 或 docker compose cp ck-observability-bridge/ hermes-gateway:/opt/data/skills/
```

## 環境變數（對應 hermes-stack/.env.example § 5C，Phase 1 前置）

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `OBS_LOKI_URL` | ✅ | `http://host.docker.internal:3100` | Loki API |
| `OBS_PROMETHEUS_URL` | ✅ | `http://host.docker.internal:9090` | Prometheus API |
| `OBS_GRAFANA_URL` | ✅ | `http://host.docker.internal:3001` | Grafana base URL |
| `OBS_GRAFANA_TOKEN` | ❌ | — | dashboard URL 生成若需認證；silence 動作必要 |
| `OBS_ALERTMANAGER_URL` | ❌ | `http://host.docker.internal:9093` | |
| `OBS_TIMEOUT_S` | ❌ | `45` | 觀測查詢常較慢 |
| `OBS_SAFE_MODE` | ❌ | `true` | `true` 時 `alertmanager_silence(mode=run)` 回 dry-run |
| `OBS_DEFAULT_WINDOW` | ❌ | `1h` | |

## 6 Tools（ADR-0022）

| Hermes Tool | PLG 端點 | 用途 |
|---|---|---|
| `obs_loki_query` | `${OBS_LOKI_URL}/loki/api/v1/query_range` | LogQL 查詢（skill 翻譯 intent 為 selector）|
| `obs_prom_query` | `${OBS_PROMETHEUS_URL}/api/v1/query_range` | PromQL range query |
| `obs_grafana_dashboard_url` | `${OBS_GRAFANA_URL}/api/dashboards/uid/{uid}` | 產 dashboard 深連結 |
| `obs_alertmanager_silence` | `${OBS_ALERTMANAGER_URL}/api/v2/silences` | 臨時 silence（**SAFE_MODE 保護**）|
| `obs_container_health` | Prom container_* metrics | 列某 project_prefix 全 container 狀態 |
| `obs_alert_active` | `${OBS_ALERTMANAGER_URL}/api/v2/alerts` | 當前 firing / pending alerts |

## 名稱空間 / 錯誤處理

- tool 一律 `obs_` 前綴，避免與 `missive_*` / `showcase_*` / `pile_*` 碰撞
- HTTP 4xx → 回 `detail`（多為 LogQL syntax 錯）；skill 附 LogQL 提示
- HTTP 5xx → 單次重試 2s
- Timeout → 不重試；勸使用者縮小時間窗 / 加 filter
- **禁止**：不杜撰 metric / log 數值；空結果就回「該時間窗無匹配」

## 使用時機

**命中**：
- 日誌：「Missive 這小時有哪些 error」「PileMgmt container 記憶體趨勢」
- 指標：「最近 24h 平均 RPS」
- 警報：「現在什麼在響」
- Dashboard：「給我隧道專案觀測儀表板連結」

**不命中**：
- 業務查詢 → `missive_*` / `pile_*`
- 治理查詢 → `showcase_*`
- 一般對話 → Hermes 內建

## 安全守則

1. `obs_alertmanager_silence(mode=run)` 有副作用：**SAFE_MODE=true 時回 dry-run**
2. 無自動重試 silence 類動作（避免重複 silence 堆疊）
3. `OBS_GRAFANA_TOKEN` 若洩漏，silence / dashboard 創建權可被濫用 — 務必走 Docker Secrets（ADR-0017）

## 版本紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.1.0 | 2026-04-19 | ADR-0022 起草後 skill source；tools.py 待 hermes-agent session 實作 |

## 相關 ADR

- `CK_AaaP#0022` — skill 契約規範
- `CK_AaaP#0025` — DigitalTunnel 觀測棧分割策略（本 skill 的 URL 指向變動理由）
- `CK_AaaP#0019` — 觀測標準
- `CK_AaaP#0017` — Docker Secrets（OBS_GRAFANA_TOKEN 存放位置）
