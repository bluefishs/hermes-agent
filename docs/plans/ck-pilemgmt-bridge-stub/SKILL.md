---
name: ck-pilemgmt-bridge
version: 0.1.0
description: CK_PileMgmt 樁管理系統橋接 — health 檢測、NL 查詢、Celery 狀態。
author: CK Platform Team
license: MIT
metadata:
  hermes:
    tags: [CK, PileMgmt, Piles, Celery, Geospatial]
    homepage: https://pile.cksurvey.tw
prerequisites:
  env_vars: [PILE_BASE_URL, PILE_API_TOKEN]
---

# CK PileMgmt Bridge — Hermes Skill v0.1

把 CK_PileMgmt 樁管理子系統透過 Hermes 暴露為自然語言查詢入口。首版只做 3 個最小 tool，
PileMgmt 補 `/api/ai/query` 端點後可啟 `pile_query_sync`。

> **本 skill 為 source**（ADR-0023 規範）；實作檔 `tools.py` / `install.sh` / `tests/`
> 於 hermes-agent session 撰寫。
>
> **注意**：2026-04 當前 PileMgmt 無 `/api/ai/query` endpoint；`pile_query_sync` 必要時先
> 停用（fallback tool_spec 只含 health + celery_status 二 tool），待 PileMgmt 補後再啟。

## 架構

```
Hermes Agent
  └─ ck-pilemgmt-bridge skill
       ├─ tools.py         動態註冊或靜態 2-3 tool
       ├─ tool_spec.json   3 tools 契約
       └─ SKILL.md         prompt context
              │
              ▼
       CK_PileMgmt backend（ck_pilemgmt-backend :8004）
```

## 部署

```bash
bash install.sh [~/.hermes/skills/ck-pilemgmt-bridge]
```

## 環境變數（對應 hermes-stack/.env.example § 5D，Phase 1 前置）

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `PILE_BASE_URL` | ✅ | `http://host.docker.internal:8004` | PileMgmt API |
| `PILE_API_TOKEN` | ✅ | — | Bearer token |
| `PILE_TIMEOUT_S` | ❌ | `30` | |
| `PILE_CELERY_FLOWER_URL` | ❌ | — | Flower UI fallback（若 PileMgmt 無 /api/celery/status）|

## 3 Tools（ADR-0023）

| Hermes Tool | PileMgmt 端點 | 用途 |
|---|---|---|
| `pile_health` | `POST /api/health/detail` | 5 container + DB + Celery worker 活性 |
| `pile_query_sync` | `POST /api/ai/query`（**PileMgmt 需新補**）| NL 案件 / 樁位 / 驗收查詢 |
| `pile_celery_status` | `POST /api/celery/status` 或 Flower | Active / scheduled / reserved tasks |

## 使用時機

**命中**：
- 「PileMgmt 現在健康嗎」
- 「PM-2026-012 的樁位狀態」（需 query_sync）
- 「PileMgmt celery 在跑什麼」
- 「這週未驗收樁數」（需 query_sync）

**不命中**：
- 業務文件 / 公文 → `missive_*`
- 觀測日誌 / 指標 → `obs_*`
- 治理查詢 → `showcase_*`

## 名稱空間 / 錯誤處理

- 所有 tool 一律 `pile_` 前綴
- 4xx / 5xx / timeout 處理同 ADR-0018 通用 fallback ladder
- **空間查詢（PostGIS WKT）暫不入首版**（複雜度高，Phase 2 另 ADR）

## 版本紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.1.0 | 2026-04-19 | ADR-0023 後 skill source；tools.py 待 hermes-agent session |

## 相關 ADR

- `CK_AaaP#0023` — 本 skill 契約規範
- `CK_AaaP#0020` — 平臺化總綱 Phase 1 四 bridge 之一
- `CK_AaaP#0018` — skill 契約 v2
