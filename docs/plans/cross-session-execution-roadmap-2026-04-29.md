# Cross-Session 執行路線圖

> **日期**：2026-04-29
> **來源**：架構覆盤輸出（hermes-agent session）+ 路線 B 校正
> **目的**：把覆盤的 10 條建議按 session 分組、列依賴鏈、給每條進入點 commit 模板，未來不論哪個 session 啟動都能直接從這份找下一動作
> **狀態**：active roadmap，每條完成後在表格勾掉

## 覆盤後校正的事實

1. **Hermes credit 非阻塞** — 當前已 Groq primary + Ollama fallback，零成本（見 `hermes-model-baseline-route-b-2026-04-29.md`）
2. **B2 Sprint A.1–A.4 + C.1–C.2 已落地** — 4 bridge skill 中 3 個（observability/showcase/pile）已實作
3. **lvrland-bridge stub 2026-04-29 補齊** — Phase 1 skill 矩陣 4/4 完整待 CK_AaaP 採納（見 `ck-lvrland-bridge-stub/`）
4. **SOUL 治理 C.1 報告** — 等 CK_AaaP session 執行「選項 1 精準版」Step 1（見 `c1-soul-status-2026-04-28.md`）

## Session 分流（依 CONVENTIONS §7）

| Session 啟動點 | 主管範圍 |
|---|---|
| **`D:\CKProject\`** | 跨 repo meta、整合驗收、跨 repo commit |
| **`D:\CKProject\CK_AaaP\`** | 治理 / ADR / Runbook / hermes-stack / 跨 repo 規範 |
| **`D:\CKProject\hermes-agent\`** | hermes Python / skill / SOUL（本 session） |
| **`D:\CKProject\CK_Missive\`** | Missive 業務代碼、shadow logger、KG |
| **`D:\CKProject\CK_lvrland_Webmap\`** | LvrLand 業務代碼 |
| **`D:\CKProject\CK_PileMgmt\`** | PileMgmt 業務代碼 |
| **用戶** | 商業/成本/路線決策 |

## 10 條建議按 session × 優先序排列

### P0 — 阻塞 / 必須先動

| # | 建議 | Session | 工時 | 依賴 | 進入點 commit 模板 |
|---|---|---|---|---|---|
| 1 | **Hermes 模型路線決策**（A / B-強化 / C） | 用戶 | 5 min | — | （口頭/批註） |
| 2 | **C.1 SOUL 治理 Step 1**（搬坤哥回 Missive、套 meta.soul.md） | CK_AaaP | 30 min | — | `feat(soul): apply meta.soul.md to hermes-stack runtime; relocate Missive Muse to CK_Missive (per C.1)` |
| 3 | **C.1 SOUL 治理 Step 2**（host SOUL 套用 + container restart） | hermes-agent | 5 min | #2 | `feat(soul): activate host meta SOUL + sync to runtime containers` |

### P1 — 結構性整合

| # | 建議 | Session | 工時 | 依賴 | 進入點 commit 模板 |
|---|---|---|---|---|---|
| 4 | **lvrland-bridge spec ADR-0024** + skill 採納 | CK_AaaP | 1.5h | hermes-agent stub（已就位） | `feat(adrs): ADR-0024 ck-lvrland-bridge skill contract` + `feat(skill): adopt ck-lvrland-bridge stub from hermes-agent` |
| 5 | **lvrland-bridge tests + install.sh** | hermes-agent | 1.5h | #4（可平行起跑） | `feat(skill): B2 Sprint A.5 — ck-lvrland-bridge 3 tool 實作 + N tests` |
| 6 | **路線 B 強化版執行**（Anthropic escalate config + secrets） | CK_AaaP | 30 min | #1=B | `feat(hermes-stack): add anthropic escalate model config (route B-enhanced)` |
| 7 | **escalate_model 機制驗證 / skill-side 邏輯** | hermes-agent | 1h | #6 | `feat(skill): per-request model escalate via skill-side complexity heuristic` |
| 8 | **shadow baseline 加 model_tag 欄位** | CK_Missive | 1h | #6 | `feat(checks): shadow-baseline-report 加 model_tag 分流統計` |
| 9 | **ADR-0027 pgvector 策略落地** | CK_AaaP + CK_Missive | 2h | — | `feat(adrs): ADR-0027 pgvector index policy (ivfflat lists=100, probes=10)` + `feat(db): apply pgvector ivfflat to embedding tables` |
| 10 | **ADR-0019 觀測統一 structlog + metric prefix** | 各業務 repo（Missive 先） | 2h × 3 | — | `feat(observability): structlog JSON formatter + ck_<svc>_<metric> prefix per ADR-0019` |

### P2 — 平臺收口

| # | 建議 | Session | 工時 | 依賴 | 進入點 commit 模板 |
|---|---|---|---|---|---|
| 11 | **資料層 3-PG 分級評估與 ADR** | CK_AaaP | 3h | — | `docs(adrs): ADR-002X data layer 3-tier consolidation (core/lvrland/pile)` |
| 12 | **CF Tunnel lvrland subdomain 上線** | CK_AaaP + CK_lvrland | 2h | LvrLand 公網就緒 | `feat(cloudflare): bind lvrland.cksurvey.tw to ck-lvrland-backend` |
| 13 | **CF Tunnel pile / hermes / tunnel subdomain** | CK_AaaP + 各 repo | 2h × 3 | #12 | `feat(cloudflare): bind {pile,hermes,tunnel}.cksurvey.tw` |
| 14 | **Docker Secrets 安全硬化（Missive Phase 2）** | CK_Missive | 4h | ADR-0017 Phase 1B 已部署 | `feat(security): migrate Missive secrets to Docker Secrets (ADR-0017 Phase 2)` |
| 15 | **ADR 季度結算機制 + 90 天 stale 警示** | CK_AaaP | 1h | — | `feat(governance): ADR registry stale warning + quarterly sweep script` |

### P3 — 平臺最終態（ADR-0020）

| # | 建議 | Session | 工時 | 依賴 | 進入點 commit 模板 |
|---|---|---|---|---|---|
| 16 | **Showcase 治理 API 遷入 CK_AaaP/platform/services/** | CK_AaaP | 1 週 | #11、#15 | `feat(platform): migrate showcase governance API into AaaP platform/services` |
| 17 | **DigitalTunnel 觀測棧併入 docker-compose.platform.yml** | CK_AaaP | 1 週 | #16 | `feat(platform): integrate observability stack into platform compose` |
| 18 | **`git clone CK_AaaP && docker compose up -d` 一鍵驗收** | 根 session | 半天 | #16、#17 | `chore(release): platform v1.0 single-command bootstrap` |

## 依賴鏈視覺化

```
[#1 用戶決策] ─┐
               ├─► [#6 escalate config] ─► [#7 skill-side 邏輯] ─► [#8 baseline tag]
               │                                                     │
[#2 SOUL CK_AaaP] ──► [#3 SOUL hermes-agent] ─────────────────────┐ │
                                                                   ▼ ▼
                                                            7 天 baseline 驗收
                                                                   │
                                                                   ▼
                                                            ADR-0014 GO/NO-GO
                                                                   │
[#4 lvrland ADR-0024] ─► [#5 tests/install] ─────────────────────► │
                                                                   │
[#9 pgvector ADR-0027] ─────────────────────────────────────────► │
[#10 觀測統一 structlog] ───────────────────────────────────────► │
                                                                   ▼
                                                            Phase 1 完整收尾
                                                                   │
[#11 資料層 ADR] ─► [#16 Showcase 遷入] ─► [#17 觀測併入] ─► [#18 一鍵啟動]
                                                                   │
[#12 CF lvrland] ─► [#13 CF pile/hermes/tunnel] ──────────────────►│
                                                                   ▼
                                                            ADR-0020 最終態
[#14 Docker Secrets Phase 2] ────────────────────────────────────► │
[#15 ADR 季度結算] ──────────────────────────────────────────────► │
```

## 立即可動清單（不需用戶決策）

以下不需 #1 決策即可推進：

- **#3** 等 #2 完成即可動（hermes-agent session）
- **#4 + #5** 已有 stub，CK_AaaP 與 hermes-agent 可平行
- **#9** pgvector 與模型路線無關
- **#10** 觀測統一可由各業務 repo 平行推進
- **#15** ADR 治理機制純文件
- **#12** CF Tunnel 可獨立進行（不等 Hermes 路線）

**最小路徑**：1 → 2 → 3 → 4 → 5 → ADR-0014 GO → 其餘平行。

## 每 session 啟動「下一動作」決策樹

當你切到某個 session，先問：

```
你切到 hermes-agent session？
  → 看 P1 #5 / #7（escalate skill-side）；P0 #3（SOUL Step 2，等 CK_AaaP 先做 #2）

你切到 CK_AaaP session？
  → P0 #2（SOUL Step 1）優先；其次 P1 #4（ADR-0024）/ #6（escalate config）
  → 或 P2 #11 / P2 #15（治理類，無依賴）

你切到 CK_Missive session？
  → P1 #8（shadow baseline）/ #10（structlog）/ P2 #14（Docker Secrets）

你切到 CK_lvrland / CK_PileMgmt session？
  → P1 #10（structlog）/ P2 #12 / #13（CF Tunnel 上線）

你切到根 D:\CKProject\ session？
  → P3 #18（一鍵啟動驗收，等 #16/#17 完成）

你（用戶）？
  → P0 #1（路線 A/B/C 決策）— 最高槓桿，5 min 解鎖 #6/#7/#8
```

## 完成度追蹤

每完成一條，把表格 # 欄前加 ✅ 標記，並在 commit message reference 此 roadmap：

```
git commit -m "feat(...): ... (per cross-session-execution-roadmap-2026-04-29 #N)"
```

## 變更歷史

- **2026-04-29** — 初版（hermes-agent session 覆盤輸出）

## 相關文件

- `docs/plans/c1-soul-status-2026-04-28.md` — SOUL 治理 Step 1/2 細節
- `docs/plans/hermes-model-baseline-route-b-2026-04-29.md` — 路線 B 強化版設計
- `docs/plans/ck-lvrland-bridge-stub/` — Phase 1 skill 矩陣 4/4
- `docs/plans/master-integration-plan-v2-2026-04-19.md` — Hermes 共同大腦 + 多 agent 總綱
- `CK_AaaP/CONVENTIONS.md` §7 — Session 啟動位置規範
- `CK_AaaP/adrs/REGISTRY.md` — 跨 repo ADR 索引
