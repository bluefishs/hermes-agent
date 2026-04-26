---
name: ck-observability-bridge
version: 0.1.0
description: 跨 PLG 觀測棧 (Loki/Prometheus/Grafana/Alertmanager) 自然語言查詢 skill
author: CK Platform Team
license: MIT

prerequisites:
  env_vars:
    - OBS_LOKI_URL
    - OBS_PROMETHEUS_URL
    - OBS_GRAFANA_URL
  optional_env_vars:
    - OBS_GRAFANA_TOKEN
    - OBS_ALERTMANAGER_URL
    - OBS_TIMEOUT_S
    - OBS_DEFAULT_WINDOW
    - OBS_SAFE_MODE
  services:
    - url: ${OBS_LOKI_URL}/ready
      name: ck-platform-loki
    - url: ${OBS_PROMETHEUS_URL}/-/ready
      name: ck-platform-prometheus

metadata:
  hermes:
    tags: [ck, observability, loki, prometheus, grafana, alertmanager, read-only]
    homepage: http://localhost:13000
    related_skills: [ck-missive-bridge]
    min_version: "0.10.0"
---

# ck-observability-bridge

CK 平臺觀測塔的自然語言查詢入口。把 PLG stack（Loki / Prometheus / Grafana /
Alertmanager）的查詢能力包裝為 Hermes tools，透過 Telegram / Web UI 一句話即可取得
觀測結果摘要 — 不再需要打開 Grafana 介面手寫 LogQL。

依 ADR-0022 規範；遵循 taiwan.md 觀察者紀律。

## 設計原則

1. **唯讀為主** — 觀測資料只查詢、不修改；`silence` 類動作需 `channel` + confirm
2. **Query 降噪** — LogQL / PromQL 對使用者隱藏；由 skill 翻譯 intent → 查詢語句
3. **結果摘要** — Loki / Prom 回傳資料常為大量時序，skill 負責挑 top-N / summarize
4. **Fallback ladder** — Grafana API → Loki API → 人類可讀錯誤（不杜撰）
5. **名稱空間** — 所有 tool 以 `obs_` 前綴

## 環境變數

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `OBS_LOKI_URL` | ✅ | `http://host.docker.internal:13100` | Loki API |
| `OBS_PROMETHEUS_URL` | ✅ | `http://host.docker.internal:19090` | Prometheus API |
| `OBS_GRAFANA_URL` | ✅ | `http://host.docker.internal:13000` | Grafana base URL |
| `OBS_GRAFANA_TOKEN` | ❌ | — | Grafana API token（含 silence / dashboard 動作時必要）|
| `OBS_ALERTMANAGER_URL` | ❌ | `http://host.docker.internal:19093` | Alertmanager API |
| `OBS_TIMEOUT_S` | ❌ | `45` | 觀測查詢常較慢；Loki 大範圍 query 需時 |
| `OBS_DEFAULT_WINDOW` | ❌ | `1h` | 預設時間窗（使用者未指定時）|
| `OBS_SAFE_MODE` | ❌ | `true` | true 時 silence 等危險動作只回 dry-run |

## Tools 清單

| Tool | 狀態 | 對應 ADR-0022 |
|---|---|---|
| `obs_loki_query` | ✅ implemented | Tool 1 |
| `obs_loki_errors` | ✅ implemented (extension) | retro §3.F 補強 |
| `obs_loki_briefing` | ✅ implemented (extension) | retro §3.F 補強 |
| `obs_prom_query` | ⏸ stub | Tool 2 |
| `obs_grafana_dashboard_url` | ⏸ stub | Tool 3 |
| `obs_alertmanager_silence` | ⏸ stub (SAFE_MODE) | Tool 4 |
| `obs_container_health` | ⏸ stub | Tool 5 |
| `obs_alert_active` | ⏸ stub | Tool 6 |

## 紀律（taiwan.md 觀察者）

- ✅ 只讀；不主動干預（不 auto-restart 容器、不 kill process）
- ✅ 不解讀業務含義（fmt 後交使用者或對應 agent）
- ✅ 不入 wiki 業務真相；僅入 ephemeral briefing
- ⚠️ PII filter：briefing 不顯示完整 stack trace 中可能含的 PII；用 `line[:160]` 截斷

## 驗收條件（依 ADR-0022 §驗收標準）

- [ ] `skills/ck-observability-bridge/` 於 hermes-agent session 建（本 skeleton）
- [ ] `OBS_*` 變數進 `hermes-stack/.env.example` § 5C
- [ ] Web UI 一句「現在有什麼警報」→ 回 Alertmanager active alerts
- [ ] Telegram 一句「Missive 這小時 error」→ 回 top 10 error log 摘要
- [ ] 故意關 Loki → skill 不 crash，回清楚錯誤
