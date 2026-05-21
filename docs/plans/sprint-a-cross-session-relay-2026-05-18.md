# Sprint A 跨 Session 接力指引 — 2026-05-18

> 來源：[[architecture-retro-2026-05-18]]
> 範圍：本指引給 **CK_AaaP / CK_Missive / 本機 shell** session 操作員照表執行
> 設計目標：每一節貼絕對路徑 + 切到對應 session 即可進行；hermes-agent session 無權跨目錄 commit
> 預估總工時：**6 小時**（三段可平行）

## 本檔分發狀態

| 來源 | 狀態 |
|---|---|
| 本機 filesystem `D:/CKProject/CK_Hermes/docs/plans/sprint-a-cross-session-relay-2026-05-18.md` | ✅ **已就緒**（commit `367e2ff6f` 本地落地）|
| fork remote `bluefishs/hermes-agent` main | ⬜ 待 push（被 pre-push enforcement 阻斷，**與本 commit 無關**：跨 repo ADR registry STALE + pgvector schema FAIL + 4 STALE CLAUDE.md/MEMORY.md）|

**操作員執行 Sprint A 不需要 fork/main 同步**——直接從本機 `D:/` 讀檔即可。push 修通後再 sync 是分開的作業。

---

## Sprint A 任務矩陣

| # | 任務 | session | 工時 | 阻斷關係 |
|---|---|---|---|---|
| **A-1** | 30 分鐘 cookbook Phase 1（missive bridge 端到端 demo） | CK_AaaP + 本機 | 30 min | 需 A-2 之前的部分（hermes-stack .env / SOUL.md）|
| **A-2** | prometheus.yml 加 hermes-gateway scrape + Grafana 面板 | CK_AaaP | 4h | 獨立 |
| **A-3** | Missive `config.py:45` 反轉 `DEVELOPMENT_MODE=False` + startup assert | CK_Missive | 1h | 獨立 |

**平行性**：A-2 / A-3 完全獨立；A-1 與 A-2 共享 CK_AaaP session，但 A-1 工序 ≤ 30 min 可先做。

---

## A-1：30 分鐘 cookbook Phase 1（missive bridge 端到端）

### Session 啟動

```bash
# 切到 CK_AaaP session
cd D:\CKProject\CK_AaaP
claude code .
```

貼路徑給 Claude：

```
請依 D:\CKProject\CK_Hermes\docs\plans\hermes-integration-demo-path-2026-05-16.md
執行 Phase 1（missive bridge MVP）的 Step 1 至 Step 6。
```

### 預期執行步驟

| Step | 動作 | 預期輸出 |
|---|---|---|
| 1 | 注入 `MISSIVE_BASE_URL` 到 `runbooks/hermes-stack/.env` | `.env` 含 `MISSIVE_BASE_URL=http://host.docker.internal:8002` |
| 2 | 套 meta SOUL template（從 `hermes-agent/docs/plans/soul-templates/meta.soul.md` 複製到 `~/.hermes/profiles/meta/SOUL.md`） | meta SOUL 啟用 |
| 3 | 在 CK_Missive 端的 SKILL.md（或 hermes-skill package）加 frontmatter `toolsets: [missive]` | SKILL.md 含 toolsets |
| 4 | `docker compose up -d --build`（hermes-stack 三容器） | hermes-web :9119 / hermes-gateway :8642 / open-webui :3000 都 healthy |
| 5 | 跑 `python D:/CKProject/CK_Hermes/scripts/verify-bridges.py --bridge missive` | `[OK] missive_health: http://host.docker.internal:8002/health → 200` |
| 6 | 開瀏覽器 → http://localhost:9119 對話「幫我看 Missive 還好嗎」 | LLM 觸發 `missive_health` tool → 真實回應 Missive 狀態 |

### 通過標準

- 6 個 step 全 ✅
- Step 6 的對話紀錄能看到 tool_call 觸發

### 卡點處理

- 若 LLM 推理層無 Anthropic credit → 跳到 A-1 暫停，先做 Plan B：Ollama 本地 gemma 模型
- 若 `host.docker.internal` 不可達（Linux）→ 改用 host IP 或加 `extra_hosts` 到 docker-compose.yml

---

## A-2：Prometheus + Grafana hermes-gateway 觀測

### Session 啟動

```bash
cd D:\CKProject\CK_AaaP
claude code .
```

貼路徑給 Claude：

```
請依 D:\CKProject\CK_Hermes\docs\plans\architecture-retro-action-items-2026-05-15.md QW-1
執行 prometheus.yml 加 hermes-gateway scrape + 基礎 Grafana 面板。
```

### 預期變更

| 檔案 | 變更 |
|---|---|
| `CK_AaaP/platform/observability/prometheus/prometheus.yml` | 新增 scrape job `hermes-gateway`，target `host.docker.internal:8642`，metrics_path `/metrics`，scrape_interval 15s |
| `CK_AaaP/platform/observability/grafana/dashboards/hermes-gateway.json` | 新建面板：request rate / latency p50/p95/p99 / 5xx rate / tokens-per-min |
| 重啟 prometheus + grafana 容器 | scrape target 顯示 UP |

### 通過標準

- Prometheus UI → Status → Targets → `hermes-gateway` UP
- Grafana 開新面板能看到 `ck_hermes_requests_total` 等指標
- 30 min 內有資料點

### 對應風險解除

- L0 觀測 0% → 50%
- P0-2「L0 觀測零覆蓋」紅色降黃

---

## A-3：Missive DEVELOPMENT_MODE 反轉預設

### Session 啟動

```bash
cd D:\CKProject\CK_Missive
claude code .
```

貼路徑給 Claude：

```
請依 D:\CKProject\CK_Hermes\docs\plans\architecture-retro-action-items-2026-05-15.md QW-2
執行 backend/app/core/config.py:45 反轉 DEVELOPMENT_MODE=False 預設 + startup assert。
```

### 預期變更

| 檔案 | 變更 |
|---|---|
| `CK_Missive/backend/app/core/config.py:45` | `DEVELOPMENT_MODE: bool = False`（原 True） |
| `CK_Missive/backend/app/main.py` startup hook | 偵測 `DEVELOPMENT_MODE=True` + `CF_TUNNEL_ENABLED=true` 同存 → `sys.exit(1)` 並 log critical |
| 補對應測試 | unit test 驗 assertion 觸發 |
| .env / .env.example | 明確標 `DEVELOPMENT_MODE=False  # 生產環境必須 false，本地開發改 true` |

### 通過標準

- 既有測試全綠
- 新測試覆蓋雙條件觸發 assertion
- 本地 dev workflow 不受影響（`.env` 顯式設 True 即可）

### 對應風險解除

- P1-3「DB 公網 + RLS 缺位 + DEVELOPMENT_MODE 預設 True」橙色降黃
- 一次 .env 失誤 ≠ KG 公網全表

---

## 完成後動作（任一 session）

跑通 Sprint A 後，請於對應 session 寫 commit 並回填進度到：

```
D:\CKProject\CK_Hermes\docs\plans\architecture-retro-action-items-2026-05-15.md
```

把 QW-1 / QW-2 / QW-3-full 從 ⬜ 改 ✅，並追加完成日期 + commit hash。

並在 hermes-agent session 補一筆 wiki log（`~/.hermes/profiles/meta/wiki/log.md`）：

```
- `2026-05-XX` SPRINT-A-DONE QW-1/QW-2/QW-3 全部通過。Phase 1 cookbook 跑通對 missive 端到端 — hermes-agent 8 個月工程首次落入 user value 鏈路。
```

---

## 卡關決策樹

```
跑 A-1 → LLM 推理層無 credit？
  ├─ 是 → 啟 Ollama 本地 gemma fallback（已配置）
  │       └─ gemma 推理品質太差，無法觸發 tool？
  │           └─ 升級 Anthropic credit 商務決策（觸發跨層討論）
  └─ 否 → 繼續

跑 A-2 → prometheus.yml 既有結構不熟？
  ├─ 是 → 讀 CK_DigitalTunnel 既有 prometheus.yml 為樣本
  └─ 否 → 繼續

跑 A-3 → 既有測試大量斷裂？
  ├─ 是 → 改 .env.development 顯式設 True，保留 dev workflow
  └─ 否 → 繼續
```

---

## 不在本 Sprint 範圍（明確排除）

- **不**做 Phase 2 / Phase 3 規劃
- **不**開新 ADR
- **不**升級 native tool α 範式
- **不**動 N+1 / HNSW / RLS（留 Sprint B/C）

---

## 關聯文件

- 詳細 cookbook：`D:/CKProject/CK_Hermes/docs/plans/hermes-integration-demo-path-2026-05-16.md`
- 整體 retro：`~/.hermes/profiles/meta/wiki/concepts/architecture-retro-2026-05-18.md`
- 上一份 action items：`D:/CKProject/CK_Hermes/docs/plans/architecture-retro-action-items-2026-05-15.md`
- 4 bridge 工程交付：`~/.hermes/profiles/meta/wiki/concepts/workflow-c3-phase1-bridges-complete-2026-05-16.md`
