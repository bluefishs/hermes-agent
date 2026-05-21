# Architecture Retro Execution Plan — 2026-05-20（第三波）

> 來源：2026-05-20 用戶於 CK_Hermes session 請求架構覆盤後，授權「依前述規劃辦理（先做 plan）」
> 範圍：跨 repo，需於 root / CK_AaaP / CK_Missive / CK_Hermes(hermes-agent fork) 各 session 分頭執行
> 模式：**plan only，不動手** — 本檔列任務分群，由用戶逐項分派 session 執行
> 連結：
> - 既存 retro：[`architecture-retro-action-items-2026-05-15.md`](architecture-retro-action-items-2026-05-15.md)（含 05-15 / 05-16 / 05-18 三次連續更新）
> - Sprint A 接力：[`sprint-a-cross-session-relay-2026-05-18.md`](sprint-a-cross-session-relay-2026-05-18.md)
> - Sprint B 接力：[`sprint-b-cross-session-relay-2026-05-18.md`](sprint-b-cross-session-relay-2026-05-18.md)
> - 跨 session 待辦池：[`D:/CKProject/CK_AaaP/platform/CROSS_SESSION_BLOCKERS.md`](../../../CK_AaaP/platform/CROSS_SESSION_BLOCKERS.md)（持續追蹤主庫）

---

## 0. 本次覆盤定位

第三波覆盤（2026-05-20）的特殊性：

| 項目 | 第一波 05-15 | 第二波 05-18 | **第三波 05-20** |
|---|---|---|---|
| 觸發點 | 用戶 hermes-agent session 主動覆盤 | 用戶 hermes-agent session 第二次請求 + 「依前述規劃辦理」| 用戶 **CK_Hermes session**（fork 本體）請求架構覆盤 |
| 主軸 | 五層架構 + 8 個 P0/P1 風險 | Sprint A 收尾 + Sprint B 接力 | **結構性張力（T1-T5）+ 10 條建議** |
| 產出 | 8 風險 + 14 sprint 任務 | sprint-a/b 接力指引 | 本檔 |
| 卡關 | 6/8 風險跨 session | A-1 Step 6 + B-4 卡 Anthropic credit | **同**（credit 1+ 月） |

**第三波相對前兩波的新觀察**：
- 識別出 5 條結構性張力（T1-T5），不只是任務缺口
- 強調「架構決策被 billing portal 綁架」的制度風險（T1）
- 提出「ADR proposed 限期收斂」的紀律機制（對應 25 條 proposed 中 8 條 stagnant ≥ 30 天）
- 把 CK_Hermes fork 與 NousResearch upstream 同步策略獨立列項（前兩波未明示）

---

## 1. 與既存資產的關係矩陣

| 第三波建議 | 既存資產 | 補強路徑 |
|---|---|---|
| **P0-1** Anthropic credit escalation 制度化 | CROSS_SESSION_BLOCKERS.md P1-1 已列「用戶人工」| 補：48h decision rule + Ollama fallback 路線（新 ADR proposed？）|
| **P0-2** Missive 容器化 spike | sprint-b §「先決條件」CK_Missive 300+ uncommitted 待整理 | 補：spike-only 1-day evaluation 任務，不動 PM2 production |
| **P0-3** ADR proposed 限期收斂 | REGISTRY.md 8 條 stagnant 警示 | 補：明確 deadline + 收斂規則（補日期 / 拆 Phase / superseded）|
| **P1-4** shared-modules 採用率審計 | ADR-0034 proposed 自 2026-05-16 | 補：實際 grep 採用率 + 強制 import lint 計畫 |
| **P1-5** ADR-0040 Service Relocation Runbook + DR Drill | ADR-0040 proposed 自 2026-05-16 | 補：6 月底前完成一次 drill 的工時排程 |
| **P1-6** CF Tunnel 17→33% | CROSS_SESSION_BLOCKERS.md P0-1（30min user 操作）| 用戶操作指引文件已就緒於 cloudflare-setup.md，補：screenshot 序列 |
| **P2-7** CK_Hermes fork policy | 無既存資產 | 全新：寫 CK_FORK_POLICY.md |
| **P2-8** 資料層 schema isolation 顯式化 | ADR-0033 proposed 資料層彙整 | 補：schema 命名公約決策（新 ADR or 0033 §2）|
| **P2-9** 測試缺口 | sprint-b B-4 已涵蓋 hermes-agent e2e | 補：Agent orchestrator / Morning-Report / ezbid 三項排序 |
| **P2-10** 文件漂移 + 治理債 | check-doc-drift.sh 已有，cross_session_blockers 38 open | 補：每月固定 1 天清理排程化 |

---

## 2. 任務分群（按 session）

### 2.1 本檔可在 **CK_Hermes session** 完成的任務（session-internal）

| ID | 任務 | 工時 | 產出 | 依賴 |
|---|---|---|---|---|
| **H-1** | 寫 `CK_FORK_POLICY.md`（對應 P2-7）：定義 CK 增量改動原則（plugin/skill 機制優先）、weekly rebase 節奏、conflict 處理 SOP | 1-2h | `D:\CKProject\CK_Hermes\CK_FORK_POLICY.md` | 無 |
| **H-2** | 補 CK_Hermes 內 prometheus 埋點覆蓋率審計（接 prev Explore agent 提示「gateway/metrics.py 已定義但 api_server.py 實際埋點待查」）| 2-3h | `docs/plans/2026-05-20-metrics-coverage-audit.md` | 無 |
| **H-3** | 把第三波覆盤的 T1-T5 結構性張力寫成 wiki concept page（`~/.hermes/profiles/meta/wiki/concepts/architecture-retro-2026-05-20.md`）| 1h | wiki page | 無 |
| **H-4** | 本檔 commit + push fork/main（讓 plan 跨 session 可見）| 5min | git commit | 用戶授權 |

**H-1 ~ H-4 全部可於本 session 完成，不需切 session。**

### 2.2 需切到 **CK_AaaP session** 的任務

| ID | 任務 | 工時 | 對應建議 |
|---|---|---|---|
| **A-1** | CROSS_SESSION_BLOCKERS.md 新增「P0-A：48h Anthropic credit decision rule」條目 + Ollama fallback 路徑 | 30min | P0-1 |
| **A-2** | ADR proposed 收斂 spreadsheet：對 25 條 proposed 逐條判定（accept / supersede / 拆 Phase / 補日期），產出 `adrs/PROPOSED_TRIAGE_2026-05-20.md` | 4-6h | P0-3 |
| **A-3** | ADR-0034（shared-modules adoption）寫 Phase 1A 落地細節：採 editable install 或 submodule pin 二擇一 + migration playbook 範本 | 2-3h | P1-4 |
| **A-4** | ADR-0040（Service Relocation Runbook）寫 DR Drill scenario：模擬 `platform/observability/` 整層掛掉 → 量化 RTO/RPO | 4h | P1-5 |
| **A-5** | hermes-stack/.env 注入 4 個 `*_BASE_URL`（sprint-a 已列 B-5，仍未完成）| 30min | P0-1 closing |
| **A-6** | ADR 編號碰撞 pre-commit hook 落地（sprint-a C-5 仍 ⬜）| 1d | P2-10 |
| **A-7** | 文件漂移月度清理排程化（在 `.github/workflows/` 或 cron 加每月 1 日跑 check-doc-drift.sh + 自動建 issue）| 2h | P2-10 |

### 2.3 需切到 **CK_Missive session** 的任務

| ID | 任務 | 工時 | 對應建議 |
|---|---|---|---|
| **M-1** | **Missive 容器化 1-day spike**（P0-2 重點）：在 feature branch 包 Dockerfile + docker-compose.spike.yml → 測 PG 連線、auth flow、`/metrics` endpoint scrape | 1d | P0-2 |
| **M-2** | A-3 commit（`DEVELOPMENT_MODE=False` 反轉 + startup assert，sprint-a 已 edit 未 commit）| 30min | sprint-a 收尾 |
| **M-3** | shared-modules import 採用率審計（grep `from shared_modules` 與重複 local 實作）| 2-3h | P1-4 evidence |
| **M-4** | sprint-b B-1/B-2 落地（N+1 + embedding env 化）| 1.5-2d | sprint-b |
| **M-5** | 資料層 schema 命名公約決策（接 ADR-0033 §2 或新 ADR）：定義 `missive_*` / `lvrland_*` / `pile_*` 邊界 | 2-3h | P2-8 |

### 2.4 需切到 **root session（`D:\CKProject\`）** 的任務

| ID | 任務 | 工時 | 對應建議 |
|---|---|---|---|
| **R-1** | 跨 repo grep shared-modules 真實 import：`for repo in CK_*; do grep -rn "from shared_modules\|from auth_module\|from observability" $repo; done` → 產出採用率矩陣 | 2h | P1-4 |
| **R-2** | 跨 repo `CK_*/docker-compose*.yml` 收集 `image:` digest 狀態 → 對齊 ADR-0028 image SHA pin 進度 | 1h | P2-10 governance debt |
| **R-3** | CONVENTIONS.md §7 例外條款（sprint-a C-6）：允許 root session 做跨層整合 | 1h | P2-10 |

### 2.5 用戶人工（無法委派 session）

| ID | 任務 | 工時 | 對應建議 |
|---|---|---|---|
| **U-1** | Anthropic credit 充值或啟動 Ollama fallback 決策 | 1h | P0-1 終解 |
| **U-2** | CF Dashboard 綁 lvrland.cksurvey.tw（既存 CROSS_SESSION_BLOCKERS P0-1）| 30min | P1-6 |
| **U-3** | 本檔 + CK_FORK_POLICY.md commit 授權 | 5min | H-4 push |

---

## 3. 執行序列建議

### 第一波（本週內，平行）

```
CK_Hermes session  →  H-1 / H-2 / H-3 / H-4  (本 session 連續完成，5-7h)
用戶人工          →  U-1 啟動（credit 充值 OR ollama fallback 決策）
CK_AaaP session   →  A-1 + A-5（共 1h）
CK_Missive session →  M-2（30min commit）+ M-1 spike（1d）
```

### 第二波（待 U-1 與第一波收斂後）

```
CK_AaaP session   →  A-2（ADR proposed triage，4-6h）+ A-3 shared-modules Phase 1A（2-3h）
CK_Missive session →  M-3（shared-modules audit, 2-3h）+ M-4（sprint-b B-1/B-2, 1.5-2d）
root session       →  R-1（採用率矩陣, 2h）
```

### 第三波（月內收斂）

```
CK_AaaP session   →  A-4 DR Drill scenario + A-6 ADR collision hook + A-7 漂移 cron
CK_Missive session →  M-5 schema 命名公約
root session       →  R-2 / R-3
用戶人工           →  U-2 CF Dashboard
```

### 等待條件對照

| Sprint A 卡點 | Sprint B 卡點 | 第三波（本檔）卡點 |
|---|---|---|
| Step 6 user demo → U-1 | B-4 LLM-driven e2e → U-1 | A-2 / A-3 / A-4 寫作不卡，但 **A-2 收斂判斷涉及前兩波卡點同源**（credit + Phase 1 完整性）|

→ U-1 解 → 三波同時解凍。**U-1 是整體最大瓶頸**。

---

## 4. T1-T5 結構性張力 → 任務映射

| 張力 | 對應任務 | 解凍條件 |
|---|---|---|
| **T1** Hermes 控制平面 LLM credit 單點 | A-1（48h rule）+ U-1（充值或 fallback）| U-1 完成 |
| **T2** Missive PM2 ↔ Docker 觀測雙世界 | M-1（容器化 spike）+ A-7（漂移自動化補位）| M-1 spike 結果決定下一步 |
| **T3** shared-modules 標準化缺位 | A-3（Phase 1A）+ M-3（採用率）+ R-1（跨 repo 矩陣）| A-3 決策出 + R-1 證據齊 |
| **T4** ADR 編號碰撞 + proposed 堰塞 | A-2（triage）+ A-6（collision hook）| A-2 完成把 25 條降到 < 10 |
| **T5** docker-compose.platform.yml 部署單點 | A-4（DR Drill scenario）| Drill 跑一次 + RTO/RPO 記錄 |

---

## 5. 不在本計畫範圍（明確排除）

依用戶選擇「先做 plan 不動手」+ 既存 sprint-a/b 已涵蓋手作任務：

- **不重複** sprint-a/sprint-b 的逐步指令（B-1 selectinload 等）
- **不新增** ADR proposed（除非 A-2 triage 後決定為某現有 proposed 開 Phase 1）
- **不動** CK_Missive 既存 300+ uncommitted（sprint-b 已標註為需專屬 session 整理）
- **不啟動** Phase 4 服務模組化大改動（待 A-2/A-3/A-4 收斂後再評估）
- **不擴張** CK_Hermes fork 客製化點（H-1 政策反過來限制這件事）

---

## 6. 完成準則（DoD）

本計畫視為「完成」的條件：

1. 全部任務（H/A/M/R/U 共 ~22 項）狀態欄至少有一次更新（completed / in_progress / blocked / deferred）
2. T1-T5 中至少 3 條解凍（任務映射對應產出落地）
3. CROSS_SESSION_BLOCKERS.md 同步反映本計畫狀態
4. 本檔 §3 執行序列至少推進到「第二波」

預計總工時：**3-5 個 session 週**（含等待 U-1）

---

## 7. 啟動指令（給用戶）

各 session 接手時，貼以下 prompt 給 Claude：

### CK_Hermes session（本 session 連續執行）
```
請依 D:\CKProject\CK_Hermes\docs\plans\2026-05-20-architecture-retro-execution-plan.md
§2.1 H-1 ~ H-4 連續執行（fork policy + metrics 覆蓋率審計 + wiki page + push）。
```

### CK_AaaP session
```
請依 D:\CKProject\CK_Hermes\docs\plans\2026-05-20-architecture-retro-execution-plan.md
§2.2 任務優先序：A-1 → A-5 → A-2 → A-3 → A-4 → A-6 → A-7。
```

### CK_Missive session
```
請依 D:\CKProject\CK_Hermes\docs\plans\2026-05-20-architecture-retro-execution-plan.md
§2.3 任務優先序：M-2 → M-1 spike → M-3 → M-4 → M-5。
```

### root session（`D:\CKProject\`）
```
請依 D:\CKProject\CK_Hermes\docs\plans\2026-05-20-architecture-retro-execution-plan.md
§2.4 任務優先序：R-1 → R-2 → R-3。
```

---

## 8. 待用戶確認

在本 session 動手 H-1 ~ H-4 前，需用戶確認以下三項：

1. **是否同意本計畫的任務分群與序列？** 若有任務想調整優先級或刪除，請指明。
2. **U-1（Anthropic credit）是充值還是啟動 Ollama fallback？** 影響 T1 / Sprint A Step 6 / Sprint B B-4 全鏈解凍方向。
3. **H-1 ~ H-4 是否授權在本 session 立即執行？** 或僅停留在「plan 已產出」此步。

---

## 關聯
- 第一波 retro：[[architecture-retro-2026-05-15]]
- 第二波 retro：[[architecture-retro-2026-05-18]]
- 第三波 retro：[[architecture-retro-2026-05-20]]（H-3 待產出）
- CONVENTIONS §7：[`D:/CKProject/CK_AaaP/CONVENTIONS.md`](../../../CK_AaaP/CONVENTIONS.md)
- ADR REGISTRY：[`D:/CKProject/CK_AaaP/adrs/REGISTRY.md`](../../../CK_AaaP/adrs/REGISTRY.md)

---

## 9. v2 校準（2026-05-20 用戶授權後）

> 用戶 feedback：「任務分群與序列同意，以**不產生額外費用為主**，以**整合架構並確認流程是正確運行為主**，避免**分散虛功（目前有此情形）**」
> Memory：[[feedback-integration-over-scope]]

### 9.1 重定的優先軸

| 軸 | v1 | v2（校準後） |
|---|---|---|
| U-1 | Anthropic credit 充值 OR Ollama fallback 二擇一 | **Ollama fallback only**（零費用） |
| 第一波目標 | H-1/H-2/H-3/H-4 + A-1/A-5 + M-1/M-2 平行 | **「跑通 1 次真實端到端」** 優於一切其他 |
| 第二波 | A-2 triage + M-4 sprint-b | 延後到「真實端到端跑通」之後 |
| 文件型任務 | H-1 / A-4 / A-3 第一波並行 | **延後**到第二波（先別再產出新計畫文件） |

### 9.2 v2 第一波（本週，零費用，純整合）

| 序 | 任務 | 對應 v1 | session | 工時 | 驗收標準 |
|---|---|---|---|---|---|
| ① | **盤點本 session 可做的整合驗證**（讀代碼 / 跑 verify-bridges.py / 跑 mock e2e / 查 4 SKILL.md frontmatter `toolsets:` 欄位）| H-2 + 新 | CK_Hermes | 1-2h | 產出「整合斷點清單」 — 哪些是 hermes-agent 端真的不通、哪些是配置缺、哪些是用戶執行操作缺 |
| ② | **A-5 + 補 SKILL.md frontmatter**：hermes-stack/.env 注入 4 個 `*_BASE_URL` + 4 個 bridge SKILL.md 加 `toolsets:` | A-5 + sprint-b §「跨 repo」| CK_AaaP（含改 4 repo SKILL.md 在 CK_AaaP 本地下）| 1h | hermes-stack 啟動後 4 bridge 被 Hermes 自動載入 |
| ③ | **啟動 Ollama fallback path**：確認 hermes-stack 可指向 ck-ollama 而非 Anthropic | A-1 + U-1 改向 | CK_AaaP | 30-60min | gateway 不需 ANTHROPIC_API_KEY 也能對話 |
| ④ | **真實端到端跑通**：對 `localhost:9119` 對話「幫我看 Missive 還好嗎」→ Ollama LLM 觸發 `missive_health` tool → aiohttp 真打 `/health` → 結果繁中回 user | sprint-a Step 6 改 Ollama 版 | CK_AaaP（host）| 30min | **這是 T1 真實解凍訊號 — Hermes 第一次 user-facing value 落地** |
| ⑤ | **M-2 commit**：Missive `DEVELOPMENT_MODE=False` 反轉 commit | M-2 | CK_Missive | 30min | git commit + push |

**第一波 DoD**：④ 跑通 = T1 部分解凍 + Sprint A Step 6 補位 + Sprint B B-4 mock→real 升級

### 9.3 v2 第二波（第一波 ④ 跑通之後）

第一波跑通才繼續，避免「再加未整合的元件」：

| 序 | 任務 | 對應 v1 | session |
|---|---|---|---|
| ⑥ | M-1 Missive 容器化 spike（接通 /metrics）| M-1 | CK_Missive |
| ⑦ | R-1 + M-3 shared-modules 採用率事實審計（純 grep，不寫新計畫）| R-1 + M-3 | root + CK_Missive |
| ⑧ | H-1 CK_FORK_POLICY.md（順手寫，限制 fork 客製化擴張）| H-1 | CK_Hermes |
| ⑨ | H-3 wiki page 記錄第三波觀察 | H-3 | CK_Hermes |
| ⑩ | A-1 CROSS_SESSION_BLOCKERS 條目更新（記錄 Ollama fallback 啟動）| A-1 | CK_AaaP |

### 9.4 v2 延後到第三波或更晚（明確列「不立即做」）

| ID | 原因 |
|---|---|
| A-2 ADR proposed triage（25 條）| 文件型工程量大，先讓真實流程跑通再 triage |
| A-3 shared-modules Phase 1A | R-1/M-3 採用率審計出來才有 evidence 做決策 |
| A-4 DR Drill scenario | 設想型，待整合層穩定 |
| A-6 / A-7 治理 hook / cron | 治理層，待整合層穩定 |
| M-4 sprint-b B-1/B-2（N+1 + embedding env）| 效能調優，待真實負載出現再做 |
| M-5 schema 命名公約 | 待 lvrland/Pile 入 PG 才需要 |
| R-2 / R-3 | 整合穩定後再清治理債 |

### 9.5 用戶必動（v2 校準後）

| ID | 任務 | 工時 |
|---|---|---|
| U-Ollama | 確認 ck-ollama 容器 healthy + gemma4 + nomic-embed-text 模型已 pull | 5min |
| U-2 | CF Dashboard 綁 lvrland.cksurvey.tw（不變）| 30min |
| U-Authorize | 授權第一波 ② ③ ④ ⑤ 跨 session 執行 | 確認即可 |

### 9.6 v2 執行原則

1. **不開新 ADR**（除非第一波 ④ 跑通後發現需記錄）
2. **不寫新計畫文件**（除非整合驗證後發現新斷點）
3. **複用既存**：sprint-a/sprint-b 接力指令、CROSS_SESSION_BLOCKERS、verify-bridges.py、mock e2e、hermes-stack runbook
4. **每一輪驗收先問「這條把哪個斷點接通了？」** 答不出來 = 分散虛功，跳過

### 9.7 等待用戶下一步

本 session（CK_Hermes）可立即執行第一波 **①**（純讀取與本地驗證，零費用、零跨 session）。是否授權立即進行？

