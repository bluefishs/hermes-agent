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
D:\CKProject\hermes-agent   →  QW-3（Missive bridge E2E test）
```

進入各 session 後請使用者貼此檔絕對路徑 `D:\CKProject\hermes-agent\docs\plans\architecture-retro-action-items-2026-05-15.md`，Claude 會自動讀此檔與 wiki 概念頁取得完整脈絡。

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
- 跨 repo plan 雜散：`D:/CKProject/hermes-agent/docs/plans/cross-repo/`

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
| Commit | 推送 11 檔案 | hermes-agent | ⬜ | 待使用者授權 |
| .env | 4 base url 注入 hermes-stack | CK_AaaP | ⬜ | |
| SKILL.md | 4 bridge frontmatter 加 toolsets | 4 repo | ⬜ | 跨 session |
| QW-3 e2e | 取代 prompt-template baseline | hermes-agent | ⬜ | 等上述完成 |
| QW-1 | Prometheus scrape `hermes-gateway` | CK_AaaP | ⬜ | |
| QW-2 | Missive `DEVELOPMENT_MODE` 預設反轉 | CK_Missive | ⬜ | |

**hermes-agent 端 ADR-0020 Phase 1 代碼面 100% 完成**；P0-1 紅色風險於本 session 範圍內 closed。剩餘為跨 session 配置 / SKILL.md 更新 / e2e 驗證。
