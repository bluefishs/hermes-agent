---
name: ck-pilemgmt-bridge
version: 0.1.0-stub
description: PileMgmt 業務查詢 bridge（樁管理：健康度 / NL query / celery 狀態）
author: CK Platform Team
license: MIT

prerequisites:
  env_vars:
    - PILE_BASE_URL
    - PILE_API_TOKEN
  optional_env_vars:
    - PILE_TIMEOUT_S
    - PILE_CELERY_FLOWER_URL
  services:
    - url: ${PILE_BASE_URL}/api/health
      name: ck_pilemgmt-backend

metadata:
  hermes:
    tags: [ck, pilemgmt, domain-bridge]
    homepage: http://localhost:8004
    related_skills: [ck-missive-bridge, ck-observability-bridge]
    min_version: "0.10.0"
---

# ck-pilemgmt-bridge

依 ADR-0023 規範。樁管理 (PileMgmt) domain agent 的 Hermes 自然語言入口。

**狀態**：stub-only skeleton（B1 Sprint Step 3）。3 tools 簽名與 frontmatter 已就位；
handler 待 CK_AaaP 採納 + PileMgmt 側加 `/api/ai/query` 端點後填實作。

## Tools 清單

| Tool | 狀態 | ADR-0023 |
|---|---|---|
| `pile_health` | ⏸ stub | Tool 1 |
| `pile_query_sync` | ⏸ stub（待 PileMgmt 加端點）| Tool 2 |
| `pile_celery_status` | ⏸ stub | Tool 3 |

## 紀律（taiwan.md 觀察者）

- ✅ 唯讀；不修改 PileMgmt DB
- ✅ Bearer token via PILE_API_TOKEN
- ❌ 不杜撰；端點 4xx 回清楚錯誤
- ❌ 不解讀業務含義 → 業務含義由使用者 / PileMgmt agent 自身解讀

## 環境變數

| 變數 | 必要 | 預設 |
|---|---|---|
| `PILE_BASE_URL` | ✅ | `http://host.docker.internal:8004` |
| `PILE_API_TOKEN` | ✅ | — |
| `PILE_TIMEOUT_S` | ❌ | `30` |
| `PILE_CELERY_FLOWER_URL` | ❌ | — |
