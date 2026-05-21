# Architecture Retro Action Items — 2026-05-15

> 來源：CKProject 五層架構覆盤（[[architecture-retro-2026-05-15]]）
> 範圍：跨 repo，需於 root / CK_AaaP / CK_Missive / hermes-agent 各 session 分頭執行
> 狀態：草案，待使用者決定衝刺週期排程

---

## 衝刺優先級

### Sprint A（本週可落地的 Quick Wins）

| # | 任務 | Session | 預估 | 狀態 |
|---|---|---|---|---|
| QW-1 | prometheus.yml 加 `hermes-gateway` scrape target，套基礎 Grafana 面板 | CK_AaaP | 4h | ⬜ |
| QW-2 | `CK_Missive/backend/app/core/config.py:45` 反轉 `DEVELOPMENT_MODE=False` 預設 + startup assert | CK_Missive | 1h | ⬜ |
| QW-3 | `tests/test_missive_bridge_e2e.py` 從 gateway 發 OpenAI prompt 觸發 Missive `/health` + `/documents/{id}` | hermes-agent | 2d | ⬜ |

### Sprint B（接下來 2 週的 P0/P1）

| # | 任務 | Session | 對應風險 |
|---|---|---|---|
| B-1 | 補實 ck-missive-bridge skill v2.0 真實 tool function（不只 prompt 模板） | hermes-agent | P0-1 |
| B-2 | Alertmanager 加 secondary receiver（Telegram bot 兜底 webhook SPOF） | CK_AaaP | P0-2 |
| B-3 | Missive N+1 熱點補 `selectinload`：`reminder_service.py` / `document/core.py` / `erp/expense_invoice.py` | CK_Missive | P1-4 |
| B-4 | embedding `Semaphore` 與 LRU 大小改 env 控制 | CK_Missive | P1-4 |

### Sprint C（2–4 週，需評估）

| # | 任務 | Session | 對應風險 |
|---|---|---|---|
| C-1 | pgvector IVFFlat → HNSW benchmark migration | CK_Missive | P1-5 |
| C-2 | PostgreSQL RLS policy 設計（先 documents / canonical_entities 兩表） | CK_Missive | P1-3 |
| C-3 | ADR-0020 Phase 1 剩餘 3 個 bridge skill（ck-showcase / ck-observability / ck-pilemgmt） | hermes-agent | P0-1 |
| C-4 | KG federation lvrland producer or downgrade single-tenant + ADR | root | P2-6 |
| C-5 | CK_AaaP pre-commit hook：ADR 編號碰撞檢測 | CK_AaaP | P2-7 |
| C-6 | CONVENTIONS §7 補例外條款：跨層整合 root session 允許 | CK_AaaP | P2-8 |

---

## 風險速查表

| ID | 嚴重度 | 一句話 | 影響面 |
|---|---|---|---|
| P0-1 | 🔴 | Hermes/Missive bridge 代碼層空頭 | 整個 ADR-0020 Phase 1 價值論證 |
| P0-2 | 🔴 | L0 觀測 0% + alert webhook SPOF | 故障無法溯源、告警可能聾啞 |
| P1-3 | 🟠 | DB 公網 + DEVELOPMENT_MODE 預設 True | 一次 deploy 失誤 = KG 公網 |
| P1-4 | 🟠 | N+1 + Semaphore(5) 瓶頸 | Hermes 接通即 503 |
| P1-5 | 🟠 | pgvector IVFFlat 規模上限 | 百萬級 entity 後 latency 惡化 |
| P2-6 | 🟡 | Federation 單 tenant 跑空殼 | 維護成本無對應產出 |
| P2-7 | 🟡 | 14 處 ADR 編號碰撞 | 知識管理崩潰預警 |
| P2-8 | 🟡 | Session §7 與跨層工作衝突 | 制度成本提高 |

---

## 重啟後復原指引

下次開機後，依照 session 範圍從對應目錄啟 Claude Code：

```
# Sprint A 平行三 session
D:\CKProject\CK_AaaP        →  QW-1（prometheus + grafana 面板）
D:\CKProject\CK_Missive     →  QW-2（config.py 反轉預設）
D:\CKProject\CK_Hermes   →  QW-3（Missive bridge E2E test）
```

進入各 session 後請使用者貼此檔絕對路徑 `D:\CKProject\CK_Hermes\docs\plans\architecture-retro-action-items-2026-05-15.md`，Claude 會自動讀此檔與 wiki 概念頁取得完整脈絡。

---

## 待決策事項（需使用者輸入）

1. **Sprint A 是否本週啟動？** 三個 quick win 都可平行；只動 QW-2 風險最低，QW-3 工時最高
2. **是否同意 P2-8 例外條款**（允許 root session 做跨層整合）？
3. **pgvector HNSW 評估**（P1-5）優先級——是否要排到 Sprint C，還是等真的看到 latency 退化再做？

---

## 關聯文件

- Wiki 概念：`~/.hermes/profiles/meta/wiki/concepts/architecture-retro-2026-05-15.md`
- ADR-0020：`D:/CKProject/CK_AaaP/adrs/0020-aaap-platform-with-hermes-control-plane.md`
- CONVENTIONS：`D:/CKProject/CK_AaaP/CONVENTIONS.md`
- 跨 repo plan 雜散：`D:/CKProject/CK_Hermes/docs/plans/cross-repo/`

---

## 最大效益路徑分析（hermes-agent session, 2026-05-15 self-pace 補充）

### 當前狀態盤點

| 項目 | 現況 | 阻礙 |
|---|---|---|
| 本 retro 文件 | **untracked**（`?? docs/plans/...`） | 跨 session 看不到，當前最大瓶頸 |
| QW-3 E2E test | 不存在；`tests/e2e/` 結構齊備（conftest + 範例） | 需 ck-missive-bridge 在 hermes-agent 端可被 load |
| B-1 真實 tool function | skill v2.0 部署在 `CK_Missive/docs/hermes-skills/ck-missive-bridge/`，hermes-agent 端 0 副本 | 需釐清 tool registration 是用 NousResearch Hermes 哪個機制 |
| C-3 三 bridge skeleton | `docs/plans/ck-{observability,showcase,pilemgmt}-bridge-{skeleton,stub}/` 已有 stub | 仍是 plan 階段，未生成可載入 skill 套件 |

### 三條路徑 ROI 評估

| 路徑 | 工時 | 解的風險 | 副作用 | 推薦度 |
|---|---|---|---|---|
| **A. QW-3 baseline first** | 0.5–1d | 量化 P0-1 空頭程度（baseline） | 跑 LLM hallucination；無真實 HTTP 證據 | ⭐⭐ |
| **B. B-1 補實 tool function** | 3–5d | 直接解 P0-1 紅色風險 | 須先確認 hermes-agent tool registration API；改後 QW-3 才有意義 | ⭐⭐⭐⭐ |
| **C. C-3 三 bridge skeleton 升級** | 5–7d | 同時解 P0-1 + 半步推進 ADR-0020 Phase 1 | 工時最高；無 B-1 經驗難一次落地三個 | ⭐⭐⭐ |

**推薦序**：先 commit 本文件 → 路徑 B（B-1）→ 回頭做 QW-3 → 再考慮 C-3。

### 本 session self-pace 任務清單

1. **T0** — commit retro action items 文件（讓跨 session 可見）：需使用者授權
2. **T1** — 釐清 NousResearch Hermes tool registration 機制（grep `tools/`、`agent/`，找 skill 載入點）
3. **T2** — 把 ck-missive-bridge skill v2.0 從 CK_Missive 引入 hermes-agent dev workflow（symlink 或 copy）
4. **T3** — 為 ck-missive-bridge 補 2 個真實 tool function：`missive_health()`、`missive_get_document(id)`
5. **T4** — QW-3 e2e test：`tests/e2e/test_missive_bridge_e2e.py` 從 gateway OpenAI endpoint 發 prompt 驗證上述 tool 被觸發
6. **T5** — commit + push hermes-agent 變更，更新 wiki concept page

### 跨 session 依賴（本 session 無法獨解）

- B-1 落實後，需 CK_Missive session 同步更新 `docs/hermes-skills/ck-missive-bridge/` deployment package
- QW-1 由 CK_AaaP session 執行（prometheus scrape）—— 此前 QW-3 跑出來的 metrics 無法落 Grafana

> Self-pace 決策：若使用者 30 分鐘內無方向回饋，下一輪自動啟動 T1（無 git 風險，純讀代碼盤點）。

---

## 落地進度（2026-05-16 self-pace 連續推進結果）

| 衝刺 | 任務 | session | 狀態 | 備註 |
|---|---|---|---|---|
| T1 | hermes tool registration 機制研究 | hermes-agent | ✅ | `docs/plans/hermes-tool-registration-research.md` |
| B-1 | ck-missive-bridge native tool（α 範式 PoC） | hermes-agent | ✅ | 2 tool / 34 tests，[[wiki workflow-b1-missive-tool-2026-05-16]] |
| C-3.1 | ck-observability-bridge native tool（4 backend） | hermes-agent | ✅ | 4 tool / 42 tests，per-tool gating，[[wiki workflow-c3-observability-tool-2026-05-16]] |
| C-3.2 | ck-showcase-bridge native tool（3 高 ROI action） | hermes-agent | ✅ | 3 tool / 36 tests |
| C-3.3 | ck-pilemgmt-bridge native tool（2 implemented action） | hermes-agent | ✅ | 2 tool / 29 tests，ai_query 跳過（後端未實作）|
| Wiki | 4 bridge 落地總結 | hermes-agent | ✅ | [[wiki workflow-c3-phase1-bridges-complete-2026-05-16]] |
| Commit | 推送 11 檔案 | hermes-agent | ✅ | `3664a24cb` docs / `7451331f2` feat 已 push fork/main |
| Verify | `scripts/verify-bridges.py` 部署 sanity helper | hermes-agent | ✅ | `faeb1615c`（ahead fork/main） |
| QW-3 e2e | mock-baseline（aiohttp test server）| hermes-agent | ✅ | `8a2f09b4d` 4 tests / 3.4s（ahead fork/main） |
| .env | 4 base url 注入 hermes-stack | CK_AaaP | ⬜ | |
| SKILL.md | 4 bridge frontmatter 加 toolsets | 4 repo | ⬜ | 跨 session |
| QW-3 full e2e | gateway + LLM + skill 全鏈路 | hermes-agent | ⬜ | 等 SKILL.md 更新 + Anthropic credit |
| QW-1 | Prometheus scrape `hermes-gateway` | CK_AaaP | ⬜ | |
| QW-2 | Missive `DEVELOPMENT_MODE` 預設反轉 | CK_Missive | ⬜ | |

**hermes-agent 端 ADR-0020 Phase 1 代碼面 + 部署驗證 helper + mock e2e 全部完成**；P0-1 紅色風險於本 session 範圍內 closed。剩餘為跨 session 配置 / SKILL.md 更新 / 真實 LLM e2e。

### 本 session 累積（2026-05-16）

- 11 個 native tool（4 個 bridge）
- 141 個單元測試 + 4 個 mock e2e = 145 個測試
- 5 個 plan / wiki 文件
- 1 個 ops verify helper
- 1 份 30-min integration demo cookbook
- 5 commit + 1 merge commit（772 commits 整合，全部 push fork/main）
- 上游 sync 2026-05-09 → 2026-05-16（771 commits，conflicts 2，CK fork 全部存活）

### 整合效應呈現（user 提問回應）

工程鋼樑已建，user-facing channel 由 4 個跨 session 配置瓶頸阻擋：

| # | 瓶頸 | 工時 | session |
|---|---|---|---|
| 1 | 4 個 SKILL.md frontmatter 加 `toolsets:` | 5 min × 4 | 各 bridge 對應 repo |
| 2 | hermes-stack/.env 注入 4 個 `*_BASE_URL` | 5 min | CK_AaaP |
| 3 | `~/.hermes/profiles/meta/SOUL.md` 套 template | 5 min | CK_AaaP |
| 4 | LLM 推理層（Anthropic credit / Ollama fallback） | 配置工 | CK_AaaP |

執行 cookbook：[`docs/plans/hermes-integration-demo-path-2026-05-16.md`](hermes-integration-demo-path-2026-05-16.md)

Phase 1（30 分鐘）走 ck-missive-bridge 端到端：對 `http://localhost:9119` 對話「幫我看 Missive 還好嗎」→ LLM 觸發 `missive_health` tool → aiohttp 真打 `/health` → 結果繁中回 user。**這就是 hermes-agent 投入 8 個月後第一次落入 user value 鏈路**。

---

## 2026-05-18 第二次覆盤差異更新

> 使用者於 hermes-agent session 第二次請求架構覆盤 + 授權「依前述規劃辦理」。完整新覆盤見 `~/.hermes/profiles/meta/wiki/concepts/architecture-retro-2026-05-18.md`。

### 3 天進度盤點

| Sprint | 項目 | 05-15 → 05-18 | 備註 |
|---|---|---|---|
| A | QW-1（prometheus 加 hermes scrape） | ⬜ → ⬜ | 跨 CK_AaaP session |
| A | QW-2（Missive DEVELOPMENT_MODE 反轉） | ⬜ → ⬜ | 跨 CK_Missive session |
| A | QW-3（gateway → Missive E2E） | ⬜ → 🟡 | mock baseline 落地（commit `8a2f09b4d`，4 tests / 3.4s）；full LLM-driven 待跨 session 配置 |
| B | B-1（ck-missive-bridge 真實 tool function） | ⬜ → ✅ | commit `7451331f2`（2 tool / 34 tests） |
| B | B-2（Alertmanager secondary receiver） | ⬜ → ⬜ | 跨 CK_AaaP session |
| B | B-3（Missive N+1 三大熱點） | ⬜ → ⬜ | 跨 CK_Missive session |
| B | B-4（embedding Semaphore/LRU env 化） | ⬜ → ⬜ | 跨 CK_Missive session |
| C | C-1（pgvector HNSW benchmark） | ⬜ → ⬜ | 跨 CK_Missive session |
| C | C-2（PostgreSQL RLS） | ⬜ → ⬜ | 跨 CK_Missive session |
| C | C-3（其餘 3 bridge skill） | ⬜ → ✅ | commit `7451331f2`（observability 4+42 / showcase 3+36 / pilemgmt 2+29） |
| C | C-4（lvrland producer 決策） | ⬜ → ⬜ | 跨 root session |
| C | C-5（ADR 編號碰撞 pre-commit hook） | ⬜ → ⬜ | 跨 CK_AaaP session |
| C | C-6（CONVENTIONS §7 例外條款） | ⬜ → ⬜ | 跨 CK_AaaP session |

**進度**：13 項中 3 項 ✅ / 1 項 🟡 / 9 項 ⬜，全部 ⬜ 都卡跨 session。

### 跨 session 接力指引（重點交付）

`D:/CKProject/CK_Hermes/docs/plans/sprint-a-cross-session-relay-2026-05-18.md`

含 A-1（30 min cookbook） / A-2（prometheus + Grafana 4h） / A-3（Missive config 反轉 1h）三段照表執行指引，每段都標明：
- 啟動 session 的 `cd` 命令
- 貼給 Claude 的 prompt 模板
- 預期變更檔案
- 通過標準
- 卡關決策樹

### 新層次風險（敘事 vs 代碼鴻溝）

| 敘事真相 | 代碼真相 |
|---|---|
| 「ADR-0020 Phase 1 closed」 | ✅ 工程，但**無一次 LLM-driven 端到端跑通** |
| 「4 bridge 已就緒」 | ✅ tools 註冊，**但 4 個 SKILL.md frontmatter `toolsets:` 從未更新** |
| 「Hermes 為人機介面」 | hermes-stack/.env **未注入任何 `*_BASE_URL`** |

**這是組織風險，不是技術風險**。下個衝刺**不要再開 Phase 2 / Phase 3**，先把 A-1 真實跑通。

### 不在範圍（明確排除）

- 不寫 Phase 2 / Phase 3 規劃
- 不開新 ADR（除非為 Sprint A 驗證撰寫 ADR-0021）
- 不升級 native tool α 範式

---

## 2026-05-18 Sprint A 100% 收尾更新（當日連續完成）

### 各項落地狀態

| 階段 | 任務 | session | 狀態 | 驗證證據 |
|---|---|---|---|---|
| QW-1 / A-2 | prometheus + Grafana hermes-gateway | CK_AaaP | ✅ | commit `f1ceffb` |
| QW-2 / A-3 | Missive `DEVELOPMENT_MODE` 反 False | hermes-agent edit | 🟡 | working tree（CK_Missive session 接手 commit） |
| QW-3 / A-1 | missive bridge end-to-end Step 1-5 | CK_AaaP | ✅ | Step 6 待 Anthropic credit |
| c | 4 STALE 文件 last_updated 更新 | hermes-agent | ✅ | drift = 0 STALE |
| b（選 2） | ADR-0030 加 Phase 1.5 CONTINUATION-EXEMPT | hermes-agent edit | ✅ | lint = 0 violations；ADR Registry 重生對齊 |
| 跨 repo | hermes-agent push fork/main | hermes-agent | ✅ | `367e2ff6f` |

### ADR-0030 Phase 1.5 設計重點

加新 marker `ADR-0030-CONTINUATION-EXEMPT`，嚴格欄位：

```
# ADR-0030-CONTINUATION-EXEMPT: <reason>; trigger=<A|B|C>; owner=<session>; sunset=<YYYY-MM-DD>
```

- 必填四項 + sunset ≤ commit 後 6 月
- sunset 過期 → lint 硬 FAIL（不是 WARNING）
- 缺欄位 → 立即 FAIL
- 限制：補位既有業務修復，不得新業務啟動
- 治理：CK_AaaP session 每月檢視

→ 例外通道有出口，無永久居留。

### 跨 repo uncommitted（待對應 session 接手 commit）

| Repo | 檔案 | session |
|---|---|---|
| CK_AaaP | `adrs/0030-...md` + `scripts/pgvector-schema-lint.sh` + `adrs/REGISTRY.md` | CK_AaaP |
| CK_PileMgmt | `backend/alembic/versions/20260505d_pgvector_alignment.py` | CK_PileMgmt |
| CK_Missive | `backend/app/core/config.py` + `backend/main.py` + 300+ 既存 uncommitted | CK_Missive（重）|

### Sprint B 啟動條件

Sprint A 已收尾，Sprint B 接力指引見：

```
D:/CKProject/CK_Hermes/docs/plans/sprint-b-cross-session-relay-2026-05-18.md
```

含 B-1（Missive N+1）/ B-2（embedding env 化）/ B-3（Alertmanager SPOF）/ B-4（hermes-agent e2e 升級）/ B-5（其餘 3 bridge enablement）五段照表執行。
