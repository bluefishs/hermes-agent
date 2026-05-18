# Sprint B 跨 Session 接力指引 — 2026-05-18

> 來源：[[architecture-retro-2026-05-18]] §10 Sprint B 啟動條件
> 範圍：本指引給 **CK_Missive / CK_AaaP / hermes-agent** session 操作員照表執行
> 設計目標：每一節貼絕對路徑 + 切到對應 session 即可進行
> 預估總工時：**1-2 週**（B-1/B-2/B-3/B-5 平行，B-4 等 Anthropic credit）

## 本檔分發狀態

| 來源 | 狀態 |
|---|---|
| 本機 filesystem `D:/CKProject/hermes-agent/docs/plans/sprint-b-cross-session-relay-2026-05-18.md` | ✅ 已就緒 |
| fork remote `bluefishs/hermes-agent` main | ✅ 待本 commit push |

## Sprint A 已收尾狀態速覽

| 項 | 狀態 |
|---|---|
| A-1 missive bridge MVP（Step 1-5） | ✅ |
| A-2 prometheus + Grafana hermes-gateway | ✅ |
| A-3 Missive `DEVELOPMENT_MODE` 反轉 | 🟡 edit done（CK_Missive session 接手 commit） |
| b 選 2：ADR-0030 Phase 1.5 | ✅ |
| c 4 STALE 文件 | ✅ |
| hermes-agent push fork/main | ✅ `367e2ff6f` |

**Sprint B 開始前必須先處理**：跨 repo uncommitted 落定（見本檔 §「先決條件」）

---

## 先決條件：跨 repo uncommitted commit（總工時 30 min）

| Repo | 檔案 | Commit 訊息建議 |
|---|---|---|
| **CK_AaaP** | `adrs/0030-...md` + `scripts/pgvector-schema-lint.sh` + `adrs/REGISTRY.md` | `feat(adr): ADR-0030 Phase 1.5 CONTINUATION-EXEMPT + lint 分支 + Registry 重生` |
| **CK_PileMgmt** | `backend/alembic/versions/20260505d_pgvector_alignment.py` | `chore(pgvector): add ADR-0030-CONTINUATION-EXEMPT marker (trigger=B / sunset=2026-11-05)` |
| **CK_Missive** | `backend/app/core/config.py` + `backend/main.py`（A-3 變更）+ 300+ 既存 uncommitted | 拆分 commit：A-3 單獨 commit `fix(config): DEVELOPMENT_MODE 預設反轉 + 公網部署 startup assert (Sprint A A-3)`；既存 300+ 重組需專屬 session 整理 |

> 注意：CK_Missive 既存 300+ uncommitted 是長期未整理的重構工作，非 Sprint A 引入。建議先 stash 後單獨 commit A-3 兩檔，再處理大批變更。

---

## Sprint B 任務矩陣

| # | 任務 | session | 工時 | 對應風險 | 阻斷關係 |
|---|---|---|---|---|---|
| **B-1** | Missive 三大熱點補 `selectinload` | CK_Missive | 1-2d | P1-4（hermes 接通後 503）| 獨立 |
| **B-2** | embedding `Semaphore` / LRU 大小 env 化 | CK_Missive | 0.5d | P1-4 | 獨立 |
| **B-3** | Alertmanager secondary receiver（Telegram bot 兜底） | CK_AaaP | 0.5-1d | P0-2 webhook SPOF | 獨立 |
| **B-4** | hermes-agent e2e 升級 mock → full LLM-driven | hermes-agent | 2-3d | P0-1 CI 守得住 | 卡 Anthropic credit |
| **B-5** | hermes-stack/.env 補 3 個 `*_BASE_URL` + 3 SKILL.md frontmatter | CK_AaaP + 3 repo | 0.5d | P0-1 完整收尾 | 獨立 |

**平行性**：B-1/B-2/B-3/B-5 完全獨立，可同時推進；B-4 等 credit。

---

## B-1：Missive N+1 熱點補 `selectinload`

### Session 啟動

```powershell
cd D:\CKProject\CK_Missive
claude
```

貼路徑：

```
請依 D:\CKProject\hermes-agent\docs\plans\sprint-b-cross-session-relay-2026-05-18.md
B-1 段執行：補 reminder_service.py / document/core.py / erp/expense_invoice.py 三大 N+1 熱點 selectinload。
```

### 預期變更

| 檔案 | 改動 |
|---|---|
| `backend/app/services/calendar/reminder_service.py` | 對 reminders 查詢加 `.options(selectinload(Reminder.user), selectinload(Reminder.document))` |
| `backend/app/services/document/core.py` | 對 documents 查詢加 `selectinload(Document.attachments, ...)` |
| `backend/app/services/erp/expense_invoice.py` | 對 invoices 查詢加 selectinload 對應 relationship |
| 對應 unit test | 補測試驗 N+1 不再發生（用 `assert query_count == expected`） |

### 通過標準

- 三大熱點查詢 query count 從 N+1 降至 1+N
- pytest 全綠
- 跑 e2e 模擬 50 concurrent 查詢，p95 latency 改善 > 30%

### 對應風險解除

- P1-4 hermes 接通後並發 503 → 大幅降低

---

## B-2：Embedding Semaphore / LRU env 化

### Session 啟動

```powershell
cd D:\CKProject\CK_Missive
claude
```

貼路徑：

```
請依 D:\CKProject\hermes-agent\docs\plans\sprint-b-cross-session-relay-2026-05-18.md
B-2 段執行：embedding pipeline Semaphore(5) 與 LRU 500 改 env 控制。
```

### 預期變更

| 檔案 | 改動 |
|---|---|
| `backend/app/services/ai/embedding/pipeline.py`（或同等位置）| `asyncio.Semaphore(int(os.getenv("EMBEDDING_CONCURRENCY", "5")))` |
| 同上 | `@lru_cache(maxsize=int(os.getenv("EMBEDDING_LRU_SIZE", "500")))` |
| `.env.example` | 加 `EMBEDDING_CONCURRENCY=5` + `EMBEDDING_LRU_SIZE=500` |
| 對應 unit test | 補 env 解析測試 |

### 通過標準

- env 變數可調 concurrency 與 cache size
- 既有測試全綠
- 文檔（CLAUDE.md 或 ARCHITECTURE.md）標明調參指引

---

## B-3：Alertmanager Secondary Receiver

### Session 啟動

```powershell
cd D:\CKProject\CK_AaaP
claude
```

貼路徑：

```
請依 D:\CKProject\hermes-agent\docs\plans\sprint-b-cross-session-relay-2026-05-18.md
B-3 段執行：Alertmanager 加 Telegram bot secondary receiver，解 25 條 alert 全打單一 webhook SPOF。
```

### 預期變更

| 檔案 | 改動 |
|---|---|
| `platform/observability/alertmanager/alertmanager.yml` | 加 Telegram receiver；route 用 `routes:` 樹分流 critical → 兩 receiver / warning → 單一 |
| `runbooks/hermes-stack/.env` 或 alertmanager 自己的 .env | `TELEGRAM_ALERT_BOT_TOKEN` + `TELEGRAM_ALERT_CHAT_ID` |
| 重啟 alertmanager 容器 | 測 alert 觸發兩 receiver 都收到 |

### 通過標準

- 模擬一條 critical alert（如 hermes-gateway down）
- 確認既有 ck-tunnel-api webhook 收到 + Telegram 也收到
- alertmanager UI 看 route tree 正確

### 對應風險解除

- P0-2 webhook SPOF → 多通道兜底

---

## B-4：Hermes-agent E2E 升級（mock → full LLM-driven）

### 卡點：Anthropic Credit

B-4 需 LLM 推理層真實跑通。當前狀態：
- Anthropic credit 卡 1+ 月待充值
- Ollama 本地 gemma 可 fallback，但推理品質對 tool_use 是否堪用未驗

### Session 啟動

```powershell
cd D:\CKProject\hermes-agent
claude
```

貼路徑：

```
請依 D:\CKProject\hermes-agent\docs\plans\sprint-b-cross-session-relay-2026-05-18.md
B-4 段執行：tests/e2e/test_missive_bridge_e2e.py 升級 mock → full LLM-driven。
若 Anthropic credit 不可用，先用 Ollama gemma fallback 驗證可行性。
```

### 預期執行步驟

1. **檢驗 Ollama tool_use 能力**：用 ck-ollama gemma4 跑一個簡單 tool_use prompt，確認模型確實會發 tool_call JSON
2. **架構選擇**：
   - 若 Ollama 可用 → 升 e2e 為 Ollama-driven，與 mock baseline 並列為兩條 CI lane
   - 若 Ollama 不可用 → 寫 fixture 等 credit，commit 架構 skeleton
3. **升級 e2e**：
   - 新 test：`test_missive_health_via_llm_e2e`
   - LLM 收到 system prompt（含 missive_health tool schema） + user prompt「Missive 還好嗎」
   - 驗 LLM 發 tool_call、registry 真實 dispatch、aiohttp 真打 socket
4. **CI 整合**：
   - mock-baseline lane 永遠跑（無外依賴）
   - llm-driven lane gate 在 env 變數（`HERMES_E2E_LLM_PROVIDER=anthropic|ollama|skip`）
   - 預設 skip，CI / 開發者主動開

### 通過標準

- mock-baseline 4 tests 仍綠
- llm-driven 至少 1 test 在 Ollama 或 Anthropic 上跑通
- README / SKILL.md 標明 e2e 兩 lane

### 對應風險解除

- P0-1 紅色「敘事 vs 代碼鴻溝」→ CI 守得住

---

## B-5：其餘 3 Bridge Enablement

### Session 啟動

```powershell
cd D:\CKProject\CK_AaaP
claude
```

貼路徑：

```
請依 D:\CKProject\hermes-agent\docs\plans\sprint-b-cross-session-relay-2026-05-18.md
B-5 段執行：hermes-stack/.env 補 observability/showcase/pile 3 個 BASE_URL，並協同 3 個 repo session 更新 SKILL.md frontmatter。
```

### 預期變更（CK_AaaP）

`runbooks/hermes-stack/.env` 反 comment：

```diff
- # OBSERVABILITY_PROMETHEUS_URL=http://host.docker.internal:19090
- # OBSERVABILITY_LOKI_URL=http://host.docker.internal:13100
- # OBSERVABILITY_GRAFANA_URL=http://host.docker.internal:13000
- # OBSERVABILITY_ALERTMANAGER_URL=http://host.docker.internal:19093
- # SHOWCASE_BASE_URL=http://host.docker.internal:5200
- # PILE_BASE_URL=http://host.docker.internal:8004
+ OBSERVABILITY_PROMETHEUS_URL=http://host.docker.internal:19090
+ OBSERVABILITY_LOKI_URL=http://host.docker.internal:13100
+ OBSERVABILITY_GRAFANA_URL=http://host.docker.internal:13000
+ OBSERVABILITY_ALERTMANAGER_URL=http://host.docker.internal:19093
+ SHOWCASE_BASE_URL=http://host.docker.internal:5200
+ PILE_BASE_URL=http://host.docker.internal:8004
```

### 跨 repo SKILL.md 更新（3 個）

| 對應 repo | SKILL.md 位置 | frontmatter 加 |
|---|---|---|
| 觀測棧（CK_AaaP 內） | `platform/observability/.../SKILL.md` 或 `runbooks/hermes-stack/...` | `toolsets: [observability]` |
| CK_Showcase（已 archived，現於 CK_AaaP/platform/services） | `platform/services/.../ck-showcase-bridge/SKILL.md` | `toolsets: [showcase]` |
| CK_PileMgmt | `docs/hermes-skills/ck-pilemgmt-bridge/SKILL.md` | `toolsets: [pilemgmt]` |

### 驗證

```bash
python D:/CKProject/hermes-agent/scripts/verify-bridges.py
```

預期：7 probe 全 OK（missive + observability 4 + showcase + pile = 7）

### 對應風險解除

- P0-1 完整收尾：4 bridge 全部從「工程就緒」進階至「LLM 可用」

---

## 完成後動作

跑通 Sprint B 各項後，請於對應 session 回填進度到：

```
D:\CKProject\hermes-agent\docs\plans\architecture-retro-action-items-2026-05-15.md
```

並在 hermes-agent session 補 wiki log（`~/.hermes/profiles/meta/wiki/log.md`）：

```
- `2026-05-XX` SPRINT-B-DONE B-1/B-2/B-3/B-5 完成。Sprint A+B 全收尾，平台 4 bridge 全可用。
- `2026-05-XX` SPRINT-B-4-PENDING B-4 卡 Anthropic credit；Ollama fallback 驗證結果 = <pass|fail>。
```

---

## 卡關決策樹

```
B-4 LLM 推理層
  ├─ Anthropic credit 充值 → 直接跑 anthropic-driven e2e
  ├─ Ollama gemma tool_use 可用 → ollama-driven e2e（首選）
  └─ 都不行 → commit 架構 skeleton + skip flag，等 credit

B-3 alertmanager
  ├─ Telegram bot 帳號可用 → 直接配置
  └─ Telegram 不可用 → 改 Discord webhook 或 email（次選）

B-5 4 bridge 啟用
  ├─ 對應 backend 都跑 → verify-bridges.py 7/7
  └─ 部分 backend 未跑 → SKIP 該 probe，分階段啟
```

---

## 不在 Sprint B 範圍（明確排除）

- 不做 pgvector HNSW migration（留 Sprint C）
- 不做 PostgreSQL RLS（留 Sprint C）
- 不做 ADR-0020 Phase 2 / Phase 3 規劃
- 不開新 ADR（除非 Sprint B 驗證觸發）

---

## 關聯文件

- 第二次架構覆盤：`~/.hermes/profiles/meta/wiki/concepts/architecture-retro-2026-05-18.md`
- Sprint A 接力指引（已完成）：`D:/CKProject/hermes-agent/docs/plans/sprint-a-cross-session-relay-2026-05-18.md`
- 整體 action items：`D:/CKProject/hermes-agent/docs/plans/architecture-retro-action-items-2026-05-15.md`
- ADR-0030 Phase 1.5：`D:/CKProject/CK_AaaP/adrs/0030-embedding-dimension-unification-roadmap.md`
- 4 bridge 工程交付：`~/.hermes/profiles/meta/wiki/concepts/workflow-c3-phase1-bridges-complete-2026-05-16.md`
- 30 min cookbook：`D:/CKProject/hermes-agent/docs/plans/hermes-integration-demo-path-2026-05-16.md`
