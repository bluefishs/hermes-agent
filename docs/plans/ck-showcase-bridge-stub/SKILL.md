---
name: ck-showcase-bridge
version: 0.1.0
description: CK_Showcase 治理 API 橋接 — 8 受管專案治理面板（Skills/Agents/Security/ADR-map/SSO/Health/Metrics）。透過 Showcase FastAPI 聚合查詢，Hermes 為自然語言入口。
author: CK Platform Team
license: MIT
metadata:
  hermes:
    tags: [CK, Showcase, Governance, Skills, Agents, Security, ADR]
    homepage: https://showcase.cksurvey.tw
prerequisites:
  env_vars: [SHOWCASE_BASE_URL, SHOWCASE_API_TOKEN]
---

# CK Showcase Bridge — Hermes Skill v0.1

把 CK_Showcase 治理面板（8 受管專案 / Skills / Agents / Security / ADR-map）透過 Hermes 自然語言暴露，
Telegram / Web UI / CLI 一句話即可聚合跨專案治理狀態。

> **本 skill 為 source**（ADR-0020 Phase 2 整合後置於 `platform/services/docs/hermes-skills/`）。
> 部署由 hermes-agent session 透過 `install.sh` 或 `docker compose cp` 植入 `~/.hermes/skills/`。

## 架構

```
Hermes Agent（L0 助理層）
  └─ ck-showcase-bridge skill
       ├─ tools.py         動態註冊 Showcase tools manifest（或 8 tools 靜態）
       ├─ tool_spec.json   fallback 靜態 tool spec（8 tools）
       └─ SKILL.md         本文（prompt context 注入）
              │
              ▼
       CK_AaaP/platform/services（L2 治理 API）
       ${SHOWCASE_BASE_URL}/api/...
```

## 部署

```bash
# 方法一：install.sh（待 hermes-agent session 撰寫）
bash install.sh [~/.hermes/skills/ck-showcase-bridge]

# 方法二：Docker（hermes-stack compose）
docker compose cp ck-showcase-bridge/ hermes-gateway:/opt/data/skills/ck-showcase-bridge/
```

## 環境變數（對應 `runbooks/hermes-stack/.env.example` 5B 區段）

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `SHOWCASE_BASE_URL` | ✅ | `http://host.docker.internal:5200` | Showcase backend URL（Phase 3 統一 compose 後改 `http://showcase-api:5200`；公網用 `https://showcase.cksurvey.tw`）|
| `SHOWCASE_API_TOKEN` | ✅ | — | Bearer token（Showcase 管理員發放；2026-04 當前 Showcase 無 SSO，預留介面）|
| `SHOWCASE_TIMEOUT_S` | ❌ | `30` | 治理查詢逾時（秒）|
| `SHOWCASE_SAFE_MODE` | ❌ | `true` | `true` 時禁止 `showcase_security_scan_run(mode=run)` 真跑，改回 dry-run 預估 |

## 工具清單（8 tools，依 ADR-0021）

| Hermes Tool | Showcase 端點 | 用途 |
|---|---|---|
| `showcase_skills_sync_status` | `POST /api/skills/sync-status` | 查某受管專案 Skills 同步狀態 + drift 清單 |
| `showcase_agents_list` | `POST /api/agents/list` | 列某受管專案 agents 狀態 |
| `showcase_security_scan_run` | `POST /api/security/scan` | 觸發/查詢 OWASP 掃描（mode=run/query，SAFE_MODE 可抑制） |
| `showcase_adr_map_query` | `POST /api/adr-map/query` | 查某受管專案 ADR 知識地圖（狀態 / 最近 N 條） |
| `showcase_managed_projects_list` | `POST /api/overview/projects` | 列 8 受管專案基本資訊（id / repo / URL / status / health） |
| `showcase_sso_status` | `POST /api/system-config/sso-status` | 查某受管專案 SSO 狀態（2026-04 尚未實作，先回 phase 2 待） |
| `showcase_governance_health` | `POST /api/overview/governance-health` | 跨專案治理健康度摘要 |
| `showcase_platform_metrics` | `POST /api/overview/platform-metrics` | 平臺級指標（ADR / skills / agents / security findings 7/30/90d trend） |

## Demo 優先順位

Phase 1 demo 建議先實作 **4 個** tools（覆蓋最廣情境）：
1. `showcase_managed_projects_list` — 列所有受管專案
2. `showcase_adr_map_query` — ADR 在途量
3. `showcase_governance_health` — 跨專案健康度
4. `showcase_platform_metrics` — 30 天趨勢

其餘 4 個（sync_status / agents_list / security_scan_run / sso_status）以 `tool_spec.json` 規劃，hermes-agent session 逐步補。

## 使用時機

**命中**（呼叫 Showcase tool）：
- 治理查詢：「Missive 的 skills 最近一次同步」「Showcase ADR 在途數」
- 跨專案摘要：「列出所有受管專案健康度」「最近 30 天 ADR 成長」
- 安全掃描：「跑一次 Missive OWASP 掃描」（SAFE_MODE 時回 dry-run）

**不命中**（交其他 skill 處理）：
- 業務查詢（公文、案件、ERP）→ `ck-missive-bridge`
- 觀測日誌 / 指標 → 未來 `ck-observability-bridge`
- 一般閒聊、網頁搜尋 → Hermes 內建

## 呼叫規範

1. **Showcase 為治理唯一來源** — 涉及 skills/agents/security/ADR 治理事實，必定呼叫 Showcase tool
2. **查詢優先、動作謹慎** — `security_scan_run(mode=run)` 必有 `SHOWCASE_SAFE_MODE` 保護
3. **名稱空間隔離** — 所有 tool 以 `showcase_` 前綴，避免與 `missive_*` 碰撞
4. **不杜撰治理數據** — Showcase 掛了即告知使用者，不回退猜測
5. **channel / session_id 傳遞** — 供 Showcase 側追溯

## 錯誤處理

| 錯誤碼 | 回應策略 |
|---|---|
| 200 | 正常解析 |
| 4xx client error | 不重試；回 `detail` 給使用者 |
| 5xx | 單次重試（指數回退 1s）；仍失敗放棄 |
| Timeout | 不重試；告知「Showcase 回應逾時」 |
| 連線拒絕 | 判斷 `SHOWCASE_BASE_URL` 是否正確 |

**禁止**：
- ❌ 單一 tool 失敗不得 crash 整個 skill
- ❌ `security_scan_run` 絕不自動重試（可能觸發兩次掃描）
- ❌ 不杜撰治理數據

## 範例對話流

```
User → Hermes（Telegram）: 列出所有受管專案目前的健康度
Hermes → tool_call: showcase_governance_health()
Showcase → { overall_score: 0.82, by_project: [{id:"missive", score:0.9}, ...] }
Hermes → User: 當前平臺治理整體健康度 82%...

User: 最近 30 天 ADR 怎麼變化？
Hermes → tool_call: showcase_platform_metrics(window="30d")
Showcase → { metrics: { adrs: { total: 81, proposed: 4, accepted: 75 } } }
Hermes → User: 近 30 天新增 6 條 ADR，其中 4 條 proposed...
```

## 版本紀錄

| 版本 | 日期 | 變更 |
|---|---|---|
| 0.1.0 | 2026-04-18 | ADR-0021 起草 + skill source 建立（hermes-agent session 待實作 tools.py / tests/） |

## 相關 ADR

- `CK_AaaP#0021` — 本 skill 契約規範（8 tools + retry/fallback）
- `CK_AaaP#0020` — AaaP 平臺化總綱（Phase 1 擴 4 bridge skills）
- `CK_AaaP#0018` — Hermes skill 契約 v2
- `CK_Missive#0014` — Hermes 遷移計劃（ck-missive-bridge 為本 skill 範本）
