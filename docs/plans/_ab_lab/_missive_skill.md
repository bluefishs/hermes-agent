---
name: ck-missive-bridge
version: 2.0.0
description: CK_Missive 後端全功能橋接 — 公文、承攬案件、知識圖譜、RAG 語意搜尋、統計、行事曆。透過 Missive public API 取得領域資料，Hermes 為唯一前端入口。
author: CK_Missive Team
license: MIT
metadata:
  hermes:
    tags: [CK, Missive, Documents, Projects, KnowledgeGraph, RAG, ERP]
    homepage: https://missive.cksurvey.tw
prerequisites:
  env_vars: [MISSIVE_API_TOKEN, MISSIVE_BASE_URL]
---

# CK Missive Bridge — Hermes Skill v2.0

將 Hermes Agent 作為 **CK 數位助理前端**，所有領域查詢委派給 CK_Missive backend 處理。

## 架構

```
Hermes Agent（L0 助理層）
  └─ ck-missive-bridge skill
       ├─ tools.py         動態從 Missive manifest 註冊所有 tool
       ├─ tool_spec.json   fallback 靜態 tool spec
       └─ SKILL.md         本文（prompt context 注入）
              │
              ▼
       CK_Missive（L2 服務層）
       https://missive.cksurvey.tw/api/...
```

## 部署

```bash
# 方法一：install.sh
bash install.sh [~/.hermes/skills/ck-missive-bridge]

# 方法二：Docker（hermes-stack compose）
# config.yaml 已配，skill 由 volume 自動掛載
docker compose cp ck-missive-bridge/ hermes-gateway:/opt/data/skills/ck-missive-bridge/
```

## 環境變數

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `MISSIVE_BASE_URL` | ✅ | `http://host.docker.internal:8001` | Missive backend URL（Docker 內用 `host.docker.internal`；CF Tunnel 用 `https://missive.cksurvey.tw`） |
| `MISSIVE_API_TOKEN` | ✅ | — | Bearer token（Missive 管理員發放，或 X-Service-Token） |
| `MISSIVE_TIMEOUT_S` | ❌ | `60` | 單次請求逾時（秒） |

## 工具清單

### 動態模式（推薦）

`tools.py` 啟動時向 `POST /api/ai/agent/tools` 取得 manifest，自動註冊所有 tool。
目前 Missive 提供的 tool：

| Hermes Tool 名稱 | Missive 端點 | 用途 |
|---|---|---|
| `missive_document_search` | `/api/ai/rag/query` | 公文 RAG 語意搜尋（pgvector 768D） |
| `missive_dispatch_search` | `/api/ai/agent/query_sync` | 通用領域查詢（公文 + 案件 + ERP） |
| `missive_entity_search` | `/api/ai/graph/entity` | KG 實體搜尋（normalized） |
| `missive_entity_detail` | `/api/ai/graph/entity` | KG 實體詳情 + 別名 |
| `missive_semantic_similar` | `/api/ai/rag/query` | 語意相似文件搜尋 |
| `missive_system_statistics` | `/api/ai/agent/query_sync` | 系統概況統計 |
| `missive_federated_search` | `/api/ai/federation/search` | KG 跨域聯邦搜尋 |
| `missive_federated_contribute` | `/api/ai/federation/contribute` | KG 跨域貢獻實體 |

### 靜態 fallback

若 manifest 不可達，使用 `tool_spec.json` 的 `query_missive` 單一入口。

## 使用時機

**命中**（呼叫 Missive tool）：
- 公文查詢：「XX 機關昨天發的文」「案號 CK2026001 狀態」
- 承攬案件：「乾坤承攬的桃園工程進度」「未開票報價金額」
- 知識圖譜：「XX 公司近半年相關公文」「找出 A 公司和 B 機關的關係」
- 標案搜尋：「今日 PCC 標案有哪些與乾坤相關」
- 統計概況：「本月新增幾件公文」「承攬案件總覽」
- 行事曆：「下週截止的公文」

**不命中**（Hermes 內建處理）：
- 日程備忘、一般閒聊、網頁搜尋
- 純計算、時區換算、單位轉換
- 程式開發、code review

## 呼叫規範

1. **Missive 是唯一事實來源** — 涉及公文/案件/工程/標案，必定先呼叫 Missive tool
2. **一次一呼叫** — 避免同輪多次呼叫（延遲敏感）
3. **保留 session_id** — 傳入 Hermes session id，Missive 側 agent_trace 可串接
4. **失敗回退** — 逾時或 5xx 時告知使用者，不杜撰答案
5. **追溯可查** — 回答附上文件編號/案號/查詢條件

## KG 查詢指引

知識圖譜相關需求的 tool 選擇：

| 需求 | 優先 tool | 備註 |
|---|---|---|
| 搜尋人名/公司/機關 | `missive_entity_search` | 模糊搜尋 + normalized |
| 查某實體的關聯 | `missive_entity_detail` | 含 neighbors + aliases |
| 找兩實體間關係 | `missive_dispatch_search` | 問 "A 和 B 的關係" |
| 跨域搜尋（含 LvrLand） | `missive_federated_search` | KG 聯邦 |
| 語意近似文件 | `missive_semantic_similar` | pgvector cosine |

## 錯誤處理

| 錯誤碼 | 回應策略 |
|---|---|
| 504 timeout | 「查詢逾時，請稍後再試」 |
| 500 internal | 「後端暫時異常，已記錄」 |
| 401/403 | 「通道認證失效，請聯繫管理員」 |
| 網路錯誤 | 重試 1 次後仍失敗 → 告知使用者 |
| manifest 不可達 | fallback 到 `query_missive` 單一入口 |

## 範例對話流

```
User → Hermes（Telegram）: 案號 CK2026003 最新狀態？
Hermes → tool_call: missive_dispatch_search(question="案號 CK2026003 最新狀態")
Missive → { answer: "案號 CK2026003 目前於施工中...", sources: [...] }
Hermes → User: 案號 CK2026003 目前於施工中，最新公文為...

User: 跟這個案子相關的公司有哪些？
Hermes → tool_call: missive_entity_search(query="CK2026003")
Missive → { entities: [{name: "桃園市政府水務局", type: "government"}, ...] }
Hermes → User: 透過知識圖譜查詢，CK2026003 關聯的實體有...
```

## 版本紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-04-16 | 擴充 KG / RAG / federation tool；加入部署指引與 Docker 支援 |
| 1.0.0 | 2026-04-15 | 初版：query_missive 單一入口 + manifest 動態註冊 |
