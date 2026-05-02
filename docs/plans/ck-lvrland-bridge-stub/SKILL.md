---
name: ck-lvrland-bridge
version: 0.1.0
description: CK_lvrland_Webmap 不動產實價登錄系統橋接 — health 檢測、NL 查詢、房價趨勢分析。
author: CK Platform Team
license: MIT
metadata:
  hermes:
    tags: [CK, LvrLand, RealEstate, GeoSpatial, Cadastral]
    homepage: https://lvrland.cksurvey.tw
prerequisites:
  env_vars: [LVRLAND_BASE_URL, LVRLAND_API_TOKEN]
---

# CK LvrLand Bridge — Hermes Skill v0.1

把 CK_lvrland_Webmap 不動產估價/實價登錄子系統透過 Hermes 暴露為自然語言查詢入口。
首版 3 tool 全部對應已上線 endpoint，**無需 PileMgmt 式 awaiting_backend 待補步驟**。

> **本 skill 為 source**（ADR-TBD 規範待 CK_AaaP 確立 ADR-0024）；實作檔 `tools.py` /
> `tool_spec.json` / `tests/` 於 hermes-agent session 撰寫，CK_AaaP session 採納為治理規範。

## 架構

```
Hermes Agent
  └─ ck-lvrland-bridge skill
       ├─ tools.py         3 tool functional（非 stub-only）
       ├─ tool_spec.json   3 tools 契約
       └─ SKILL.md         prompt context
              │
              ▼
       CK_lvrland_Webmap backend（lvrland-backend :8002）
       ├─ /api/v1/ai/query              ✅ 已上線
       ├─ /api/v1/analytics/price-volume-trends  ✅ 已上線
       └─ /api/health                  ✅ 已上線（推測 PileMgmt pattern）
```

## 部署

```bash
bash install.sh [~/.hermes/skills/ck-lvrland-bridge]
```

## 環境變數（對應 hermes-stack/.env.example § 5E，Phase 1 前置）

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `LVRLAND_BASE_URL` | ✅ | `http://host.docker.internal:8002` | LvrLand backend |
| `LVRLAND_API_TOKEN` | ❌ | — | Bearer token（若 LvrLand 啟用 auth） |
| `LVRLAND_TIMEOUT_S` | ❌ | `30` | |
| `LVRLAND_DEFAULT_DISTRICTS` | ❌ | `中壢區,桃園區` | 房價趨勢預設行政區（逗號分隔） |

## 3 Tools

| Hermes Tool | LvrLand 端點 | 用途 |
|---|---|---|
| `lvrland_health` | `POST /api/health/detail` 或 `GET /api/health` | container + DB + Ollama 連線活性 |
| `lvrland_query_sync` | `POST /api/v1/ai/query` | NL 查詢估價 / 行政區資料；含 `map_highlight` function call 結構化回傳 |
| `lvrland_price_trends` | `POST /api/v1/analytics/price-volume-trends` | 行政區房價/成交量時序資料 |

## 使用時機

**命中**：
- 「LvrLand 系統健康嗎」
- 「中壢區最近房價走勢」
- 「在地圖上顯示桃園區」（觸發 `map_highlight` function call）
- 「桃園市 8 個行政區的成交量比較」（→ price_trends with districts list）

**不命中**：
- 業務文件 / 公文 → `missive_*`
- 樁位 / 工程驗收 → `pile_*`
- 觀測日誌 / 指標 → `obs_*`
- 治理 / ADR / skills → `showcase_*` / `adr_query`

## 名稱空間 / 錯誤處理

- 所有 tool 一律 `lvrland_` 前綴
- 4xx / 5xx / timeout 處理同 ADR-0018 通用 fallback ladder
- `lvrland_query_sync` 回傳兩種結構：
  - `{type: "tool_call", tool_name: "map_highlight", arguments: {...}}`（行政區 + map keyword 命中）
  - `{type: "text_response", content: "..."}`（一般 RAG 回答）
- 不做空間 WKT / PostGIS query 首版（Phase 2 另 ADR）

## 與 PileMgmt-bridge 的差異

| 面向 | LvrLand-bridge | PileMgmt-bridge |
|---|---|---|
| `*_query_sync` endpoint | ✅ 已上線（`/api/v1/ai/query` Groq+Ollama） | ⚠️ awaiting_backend（PileMgmt 需新補） |
| 領域特色 tool | `price_trends`（房價量時序） | `celery_status`（任務佇列） |
| Auth | Bearer token（可選；LvrLand 預設 dev mode） | Bearer token（PILE_API_TOKEN 必要） |
| Function call 回傳 | ✅ map_highlight 等結構化 tool_call | — |

## 版本紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.1.0 | 2026-04-29 | B2 Sprint Phase 1 收尾；ADR-0024（待立）後 skill source |

## 相關 ADR

- `CK_AaaP#0024`（提案中） — 本 skill 契約規範
- `CK_AaaP#0020` — 平臺化總綱 Phase 1 四 bridge 之一
- `CK_AaaP#0018` — skill 契約 v2
