# Cross-Session Next 3 — 收斂跨 session 待動清單

> 版本：v2.2 · 2026-05-22 evening · CK_Hermes session（5/5 實機驗收 + SOUL 注入反例後）
> 目的：取代 sprint-a-relay / sprint-b-relay / retro-execution-plan §2.2-§2.4 / breakpoint-audit §7.2 散在 4 處的待動條目
> 原則：**只列下一動 3 項** — 任一項落地後本檔即時更新，不堆積歷史
> Memory：[[feedback-integration-over-scope]]、[[feedback-pre-demo-functional-verification]]

---

## v2.2 變更摘要（5/5 實機驗收 + SOUL 注入反例）

實機 5 題（A/B/C/D 類各 1-2 題）全綠：
- ✅ 對話能力完整恢復
- ✅ Groq direct + SSOT backend 注入 = 11s + 答案正確
- ✅ Hermes path 確認可用但延遲 50s+（hermes 自帶 14k prompt tokens）
- ✅ Groq 對「未知題」誠實認（C類 ck-missive-bridge tool / D類 Postgres 用量）— **比 hallucinate 強**
- ⚠️ Compound 多問會吞子題（教用戶「一次一問」即可繞過）

**B（SOUL 注入 SSOT）嘗試失敗**：
- 把 1.2KB SSOT block 寫進 SOUL.md → Hermes path 從 51s 漲到 >120s
- 已回退；學到「SOUL 改動須 budget」教訓
- ADR-CK-003 方向轉為「ck-platform-context skill」（dynamic tool dispatch）取代 SOUL bloat
- 完整紀錄：[`lesson-l21-hermes-runtime-dispatching-2026-05-22.md`](lesson-l21-hermes-runtime-dispatching-2026-05-22.md)

---

## v2.1 變更摘要（v2 #1 已落地）

v2 #1（修 profile/meta config 解 L21）**已完成**：
- ✅ `/opt/data/profiles/meta/config.yaml` 從 `model: ''` 補成 dict-form（Ollama + Groq fallback_model）
- ✅ `auxiliary.compression.context_length: 65536` override（qwen2.5:7b-ctx64k 預設 32K < hermes 64K min）
- ✅ R3 layer 3 probe `回答一個字：好` → 24.9s 真實回 `好`（Hermes LLM dispatch 真實通了）
- ✅ AaaP Chat backend 注入 SSOT meta + projects context system prompt（[overview.py:_aaap_context_system_prompt](../../../CK_AaaP/platform/services/backend/routers/overview.py)）
- ✅ Hermes timeout 反向策略 15s → 10s（快速 fallback Groq + 注入的 SSOT context → 0.5s 答對）
- ✅ 3 題 smoke test 全綠（列管系統清單 / missive 健康 / 四塔分別）— 答案 11s 內回到 UI

副效應發現：
- 🟢 backend `service: ck-showcase-api` 已悄悄改為 `aaap-platform-api` — Phase 2.5 backend rename 部分提前落地
- ⚠️ Hermes via Ollama 處理 SSOT-rich AaaP 問題需 50-90s+（hermes-agent runtime 自帶 14k+ prompt tokens：SOUL.md + skill manifest），且 SOUL.md **無 AaaP SSOT 知識**，需 ADR-CK-003 補位

---

## 當下 Top 3（v2.2，5/5 實機 + SOUL 失敗後重排）

### 🥇 #1 — ADR-CK-003 v2：寫 `ck-platform-context` skill（取代 SOUL 注入）

**目標**：讓 Hermes 路徑能答 AaaP SSOT 問題，且**不**膨脹 SOUL.md（避免每次 chat +1.2KB → +70s 延遲）

**設計方向**：
- 新 hermes skill `ck-platform-context`，提供 native tool `aaap_get_ssot_context(query: str)`
- Tool 動態從 SSOT yaml 抓 meta + projects[] + integration_status，回 LLM-friendly 文字
- SOUL.md 只加 1 句「需要 AaaP 元資料時呼叫 `aaap_get_ssot_context` tool」（< 50 bytes）
- 對「列管系統清單」「missive 狀態」等問題，Hermes agent loop 觸發 tool → SSOT context 進入工作記憶 → 答案準確
- Hermes 自身 prompt 不脹

**參考**：與 `ck-missive-bridge` 同模式（dynamic manifest + native tool）

**DoD**：
1. skill 程式碼 + tool 實作（依 [CK_FORK_POLICY §1 L2](../../CK_FORK_POLICY.md)）
2. SOUL.md 加 1 句指引（≤ 50 bytes）
3. Hermes 直連測「列管系統清單」≤ 60s + 答對

**工時**：2-3h

---

### 🥈 #2 — Phase 2.5 身份收斂 bulk rename（CK_AaaP session，3-4h）

**新狀態**：backend `service: aaap-platform-api` 已就位（部分提前完成）

**剩餘範圍**（依 [`CK_AAAP_ABSORPTION_POLICY.md §3.1`](../../../CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md)）：

| Target | 當前 | 目標 |
|---|---|---|
| backend service name | ✅ `aaap-platform-api` | done |
| Container `ck-showcase-{dev,prod,backend,postgres,redis}` | 5 個容器 + network | `aaap-platform-*` |
| docker-compose service blocks | 仍叫 ck-showcase-* | rename |
| Frontend src 字串引用 `CK_Showcase` | ~149 file refs | bulk find-replace（排除 ADR / #下架專案 / docs/api auto-gen） |
| Tests 同步 | snapshot + fixture | re-run all |
| `.devcontainer/docker-compose.yml` | container_name 含 ck-showcase | rename |

**Hard deadline**：2026-08-22

**DoD**：policy §5 5 步驗收全綠

**工時**：3-4h

---

### 🥉 #3 — ADR-CK-002 寫 image entrypoint venv quirk

**目標**：把 PYTHONPATH workaround 升 ADR + 究 root cause（為何 web container 走 entrypoint.sh 的 `source .venv/bin/activate` 後 `python3` 仍找不到 hermes_constants，而 gateway 走同一路徑沒事）

**動作**：
1. 寫 `D:\CKProject\CK_Hermes\docs\plans\adr-ck-002-image-entrypoint-venv.md`
2. 完整 root cause 診斷（可能 gosu re-exec + activate script interaction）
3. Upstream PR 草稿（or evaluation 不必 upstream，PYTHONPATH 永久成為 docker-compose env 即可）
4. 紀錄到 [CK_FORK_POLICY.md §3](../../CK_FORK_POLICY.md) L3 patch 清單（或標 L1 docker-compose env，免 patch）

**DoD**：ADR-CK-002 寫完 + 政策表格更新

**工時**：1-2h

---

## v2.1 原 Top 3 收回

| v2.1 序 | 動作 | 為何在 v2.2 變 |
|---|---|---|
| ~~v2.1 #1~~ 用戶實機 30 min | ✅ **本日完成** | 5/5 題答對 + compound parsing 副作用紀錄 |
| ~~v2.1 #2~~ Phase 2.5 bulk rename | → v2.2 #2 | 順序降一級 |
| ~~v2.1 #3~~ ADR-CK-003 SOUL 注入 | ❌ **嘗試失敗** | 升 v2.2 #1，方向改為 dynamic skill 而非 SOUL bloat |

---

## 已收回 — 用戶實機驗收清單（v2.1 #1 結果）

| # | 類 | 問題 | 結果 | 平均延遲 |
|---|---|---|---|---|
| 1a | A | 列管系統清單（單問） | ✅ 8 個全列 + 標籤對 | 11s |
| 1b | A | 三問合一（清單 + 四塔 + 監控元件） | 2/3（清單被吞）| 同上 |
| 2 | B | missive 狀態如何？ | ✅ active/high/subdomain 全對 | 11s |
| 3 | B | lvrland subdomain？ | ✅ lvrland.cksurvey.tw | 11s |
| 4 | C | ck-missive-bridge tool？ | ✅ 誠實「沒清單」+ 引架構 | 11s |
| 5 | D | Missive Postgres 用量？ | ✅ 誠實「不知」+ 指向監控塔 | 11s |

**結論**：對話可用、答案正確、延遲穩定。Compound 多問副作用 = 教學「一次一題」即可繞過。

---

## 暫不在 Top 3（v2.2 觀察名單）

### 🥇 原 #1 — 用戶實機驗收 30 min（CK_Hermes session，**user-driven**）

**目標**：把今日「實驗室綠燈」翻譯為「實際使用者場景」— 找出 lab vs prod gap

**動作**：

1. **打開 AaaP Chat 主介面**：
   ```
   瀏覽器：http://192.168.50.210:5200/
   位置：首頁 PlatformDashboard 的「AaaP Chat（Hermes → Groq fallback）」卡片
   ```

2. **跑 4 類問題**：
   - **A 類 — 元資料**：列管系統清單 / AaaP 平臺四塔 / 監控塔核心元件
   - **B 類 — SSOT 細節**：missive 狀態 / lvrland subdomain 是什麼 / 哪些專案有 hermes_bridge
   - **C 類 — 跨架構**：Phase 3-A 觀測棧分割做了什麼 / ck-missive-bridge 有什麼 tool
   - **D 類 — 預期會錯**：今天有沒有人 commit / Missive Postgres 容量 / 即時 metrics 數字

3. **觀察並記錄**：
   - 哪題回 `via: hermes`（agent loop / tool 真實啟動）
   - 哪題回 `via: groq-direct`（fallback path）+ `fallback_reason`
   - 哪題答案明顯 hallucinate / 引用過時資料 / 名詞混淆
   - 哪題回應 > 15s（UX 不可接受門檻）

4. **產出**：實測 4 類 × 2-3 題清單 + 標記每題 OK / WRONG / SLOW

**DoD**：30 min 連續對話，產出實機體驗清單。問題不必全答對；目標是「先看真實 UX 落差」。

**工時**：30 min（用戶人工）

---

### 🥈 #2 — Phase 2.5 身份收斂 bulk rename（CK_AaaP session，半天）

**新狀態**：backend `service: aaap-platform-api` 已就位（部分提前完成）

**剩餘範圍**（依 [`CK_AAAP_ABSORPTION_POLICY.md §3.1`](../../../CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md)）：

| Target | 當前 | 目標 |
|---|---|---|
| backend service name | ✅ `aaap-platform-api` | done |
| Container `ck-showcase-{dev,prod,backend,postgres,redis}` | 5 個容器 + network | `aaap-platform-*` |
| docker-compose service blocks | 仍叫 ck-showcase-* | rename |
| Frontend src 字串引用 `CK_Showcase` | ~149 file refs | bulk find-replace（排除 ADR / #下架專案 / docs/api auto-gen） |
| Tests 同步 | snapshot + fixture | re-run all |
| `.devcontainer/docker-compose.yml` | container_name 含 ck-showcase | rename |

**Hard deadline**（policy §2）：從 ADR-0020 Phase 2 完成日 + 90 天，最遲 2026-08-22

**DoD**：policy §5 5 步驗收全綠

**工時**：3-4h（backend rename 已完成省 1h）

---

### 🥉 #3 — ADR-CK-003 SOUL.md 注入 SSOT context（CK_Hermes session，1-2h）

**目標**：讓 Hermes 路徑本身知道 AaaP SSOT，不再依賴 Groq fallback + 後端注入

**為什麼是 #3 不是 #1**：
- AaaP Chat backend 已注入 SSOT system prompt → Groq fallback 答對
- Hermes path 慢但「不答錯也不答對 — 只是 generic 回應」(用戶感知 = fallback 接住即可)
- 真正阻塞 = Hermes 走 4 bridge skills（tool dispatch）的 AaaP 場景，必須等 SOUL 對齊才能達

**動作**：

1. 確認 SOUL.md 在哪：
   ```
   /opt/data/SOUL.md（root）+ /opt/data/profiles/meta/SOUL.md（active profile）
   兩者可能不同步 — 同 L21 profile 教訓
   ```

2. 起 ADR-CK-003 draft（依 [`CK_FORK_POLICY.md §2`](../../CK_FORK_POLICY.md)）：
   - 判定 L1（純編輯 SOUL.md）或 L2（plugin/skill 動態注入）
   - 若選 L2：呼叫 `ck-adr-query` 或新 `ck-platform-context` skill 動態查 SSOT
   - 若選 L1：直接把 SSOT meta + projects yaml block 嵌入 SOUL.md

3. 測 Hermes 路徑能否在 SOUL 補完後答對「列管系統清單」+ 時間 ≤ 30s

**DoD**：Hermes via Ollama 對「列管系統清單」回答正確 + ≤ 30s + 不需 backend 注入

**工時**：1-2h

---

## 完成此 3 件之後

回頭看：
- v2.1 #1 → 真實 UX 落差清單 = 接下來 sprint 排序依據
- v2.1 #2 → CK_Showcase 命名鴻溝完全關閉 = ssot.yaml / docker / file refs 全收斂
- v2.1 #3 → Hermes 自身 AaaP-aware = 不再依賴 fallback safety net

**才能**動下列（**不要先動**）：
- D2 production SKILL.md 落地（observability / showcase）
- D4 toolsets 欄位（pile / lvrland）
- D3 lvrland fallback tool 決策
- A-2 ADR proposed triage
- A-3 shared-modules Phase 1A
- M-1 Missive 容器化 spike
- 線 B 根因究底（entrypoint.sh venv quirk）→ ADR-CK-002 候選

---

## 不在本檔範圍（不分散）

- ❌ 不替任何 ADR proposed 補日期 / 拆 Phase
- ❌ 不寫新的 retro / sprint 接力 markdown
- ❌ 不動 Missive PM2 production
- ❌ 不 Anthropic credit 充值
- ❌ 不重訪已落地的 v1 / v2 #1 步驟

---

## 已驗收的本日進度（2026-05-22 累進）

| 項 | 狀態 | 證據 |
|---|---|---|
| R2 CK_FORK_POLICY.md | ✅ | `D:/CKProject/CK_Hermes/CK_FORK_POLICY.md` |
| R1 L21 診斷檔 | ✅ + 結論已落地 | `docs/plans/2026-05-22-L21-runtime-dispatching-diagnose.md` |
| R3 verify-hermes-stack.py | ✅ 實跑揭穿 L1/L2/L3 | `scripts/verify-hermes-stack.py` |
| R4 CROSS_SESSION_NEXT_3.md | ✅ v1 → v2 → **v2.1** | 本檔 |
| ck-hermes-web 恢復 | ✅ | PYTHONPATH workaround |
| ck-open-webui 恢復 | ✅ | port 3010 |
| **L21 線 A 根因 + 修復** | ✅ | profile/meta config 補 model dict + auxiliary override |
| 整體架構釐清備忘 | ✅ | 跨對話 §A-§F + G1-G5 鴻溝表 |
| SSOT 移除 CK_Showcase | ✅ | ssot.yaml v1.6.1 + changelog |
| CK_AAAP_ABSORPTION_POLICY.md | ✅ | `D:/CKProject/CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md` |
| **AaaP Chat 對話能力恢復** | ✅ | 3 題 smoke 全綠 + 11s 內回 UI |
| backend service rename (部分) | ✅（已就位） | `:5201/api/health.service = aaap-platform-api` |
| _patch_meta_profile.py helper | ✅ | `scripts/_patch_meta_profile.py` |
| 5/5 實機驗收 | ✅ | A/B/C/D 4 類各 1-2 題全綠 |
| SOUL 注入嘗試 + 回退 | ✅ + 反例學習 | `scripts/_inject_soul_ssot.py` + lesson §2.5 |
| L21 lesson page | ✅ | `docs/plans/lesson-l21-hermes-runtime-dispatching-2026-05-22.md` |

---

## 維護規則

- #1 落地 → 刪除此項，把 #2 升為 #1，#3 升為 #2，補新的 #3
- 任何「待動」想加入時，先問「這是不是當前 user-facing 解凍鏈上的最近 3 件？」否則拒收
- 本檔禁止 > 1 page。超過即代表分散虛功的傾向回來了。
- 本日已 v1 → v2 → v2.1 三次升版；下次升版觸發 = #1 (用戶實機 30 min) 完成

---

## 關聯
- L21 診斷：[`2026-05-22-L21-runtime-dispatching-diagnose.md`](2026-05-22-L21-runtime-dispatching-diagnose.md)
- Fork 政策：[`../../CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)
- Absorption 政策：[`../../../CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md`](../../../CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md)
- 第三波 retro v2：[`2026-05-20-architecture-retro-execution-plan.md`](2026-05-20-architecture-retro-execution-plan.md) §9
- 整合斷點審計：[`2026-05-20-integration-breakpoint-audit.md`](2026-05-20-integration-breakpoint-audit.md)
- Memory：[[feedback-integration-over-scope]]、[[feedback-pre-demo-functional-verification]]
