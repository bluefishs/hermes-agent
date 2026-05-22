# Lesson: L21 — Hermes Runtime Dispatching & AaaP Chat 對話能力恢復

> 日期：2026-05-22
> Session：CK_Hermes（D:\CKProject\CK_Hermes\）
> 觸發：2026-05-21 宣稱「demo ready」→ 2026-05-22 用戶實測 12 層揭穿 → 8 小時診斷 + 修復
> Memory：[[feedback-pre-demo-functional-verification]] · [[feedback-integration-over-scope]]
> 對偶 ADR 候選：ADR-CK-001（runtime patch）✗ / ADR-CK-002（image entrypoint）✓ / ADR-CK-003（SOUL SSOT）✗

---

## 0. 一句話總結

「Hermes runtime hard-coded fallback to openrouter」**真實存在**，但 root cause 不在 runtime 程式碼，而在 **profile config 漂移**：active profile = `meta`，而 `/opt/data/profiles/meta/config.yaml` shipping default 是 `model: '' providers: {}`，runtime resolver 找不到 provider → fallthrough 到 openrouter 預設 → 401。修法 = profile config 補 dict-form model + Groq fallback_model + auxiliary.compression context_length override（10 min 解 8h 卡關）。

---

## 1. 完整事件鏈

### 1.1 觸發
- 2026-05-21：CK_Hermes session 宣稱「hermes-stack demo ready，等用戶 30min browser 操作」
- 2026-05-22：用戶實測，連續 12 層 diagnostic 揭穿三個獨立問題（line A/B/C）

### 1.2 揭穿的三條線
- **線 A**：`:8642 /v1/chat/completions` HTTP 401，root cause 待診斷
- **線 B**：`:9119` ck-hermes-web 容器 restart loop
- **線 C**：`:3000` ck-open-webui 容器 Exit 137

### 1.3 修復順序與結果

| 階 | 動作 | 結果 |
|---|---|---|
| 線 B fix | docker-compose 加 `PYTHONPATH=/opt/hermes` env | ✅ web 從 restart loop 恢復 |
| 線 C fix | port 從 `:3000` 改 `:3010`（避開 Missive frontend 佔用） | ✅ open-webui 健康 |
| 線 A 診斷 | `/api/health` Bearer 是 gateway 自己的 auth，不是 LLM 上游；envFile 不自動 propagate；config.yaml /opt/data/ vs /opt/data/profiles/meta/ 不同 | 揭穿 profile 漂移 |
| 線 A fix | profile/meta config.yaml 補 model dict + fallback_model + auxiliary.compression.context_length=65536 | ✅ L3 dispatch 24.9s 真實回 |
| AaaP Chat 對話能力 | backend 注入 SSOT meta + projects context；Hermes timeout 反向縮短到 10s 快速 fallback Groq | ✅ 5/5 實機題目答對 |
| SOUL 注入嘗試 | 把 SSOT 受管清單寫進 SOUL.md（+1.2KB） | ❌ Hermes 路徑從 51s 變 >120s，**回退** |

---

## 2. 五個技術教訓

### L21.1 — Hermes profile 系統的「靜默漂移」

**現象**：HERMES_HOME=/opt/data，但 active_profile=meta，runtime 實際讀 `/opt/data/profiles/meta/config.yaml`。Root 的 `/opt/data/config.yaml`（操作者以為在編輯的）**完全不被載入**。

**為何危險**：操作者改 root config 看不到生效，會反覆改、debug、加 env，最終放棄。系統表面 healthy（3/3 container green）但 functional 失效。

**修法常識**：任何「改 config 沒生效」第一步先查 `cat /opt/data/active_profile` + `ls /opt/data/profiles/`。

### L21.2 — docker-compose `env_file:` 不自動 propagate 新加變數

**現象**：在 `.env` 加 `HERMES_INFERENCE_PROVIDER=custom` 後 `docker compose up --force-recreate`，容器 Config.Env 仍沒這變數。

**Root cause**：未確證，但實證行為。`environment:` block 直接寫的變數 100% 進容器；`env_file:` 來源變數有時不會。

**修法常識**：debug 用變數一律加 `environment:` block 顯式聲明，**不要靠 env_file**。

### L21.3 — docker healthcheck 只測 readiness，不測 functional

**現象**：3 個 hermes 容器 healthy 2 days，但 chat 一句都沒跑成功。Healthcheck 用 `curl /health` 只測 process alive + port open。

**修法常識**：任何 hermes-stack ADR 必加 functional probe healthcheck（如 1 句最簡 chat completion）。本 session 已產出 [`scripts/verify-hermes-stack.py`](../../scripts/verify-hermes-stack.py) 三層 probe 補位。

### L21.4 — Hermes-via-Ollama 14k tokens prompt 是不可商議的物理限制

**現象**：Hermes runtime 自帶 SOUL.md + skill manifest，每次 chat 都注入 ~14k tokens。對 qwen2.5:7b 本地推論 = 50s+。

**含意**：
- AaaP Chat 用 Hermes 路徑 = 不可能 ≤ 15s（除非 model 換大算力 + 暖快取）
- Groq direct + backend SSOT 注入 = 11s 且正確
- **這兩條是不同 use case，不該競爭同一條 path**：
  - Hermes path → tool dispatch（agent loop 必需的場景）
  - Groq direct → SSOT meta Q&A（用戶單問就答的場景）

### L21.5 — SOUL.md 注入會讓 hermes 更慢，不會更聰明

**嘗試**：把 SSOT 受管清單（1.2KB）寫進 SOUL.md，期待 Hermes 路徑能答 AaaP 問題不用 fallback。

**結果**：Hermes 路徑從 51s 漲到 >120s（被 curl 切斷），完全反效果。

**為何**：SOUL 是 hermes-agent runtime 對「每次 chat 都注入 system prompt」，size 直接乘以 token-per-second 處理速度。任何 SOUL 增量都全局加重 Hermes 延遲。

**修法常識**：SOUL 改動需 budget — 字數每加 100 字評估「值得拖慢全 stack」嗎？AaaP SSOT 屬於可動態查詢的資料，**該走 skill tool dispatch（ck-adr-query / future ck-platform-context）而非塞進 SOUL**。

---

## 3. 對 ADR-CK-001/002/003 候選的影響

| ADR 候選 | 原假設 | 今日結論 | 行動 |
|---|---|---|---|
| **ADR-CK-001** runtime patch（修 hard-coded openrouter） | upstream code 需 patch | 假設錯誤 — root cause 是 profile config，不是 runtime hard-code | **不寫**，問題已解 |
| **ADR-CK-002** image entrypoint venv quirk | venv activation 在 web container 不穩定 | 待診斷未動；目前用 PYTHONPATH workaround 解 | **保留候選**，下次有空寫 |
| **ADR-CK-003** SOUL 注入 SSOT | 解 Hermes path AaaP-blindness | 嘗試失敗 — SOUL 注入會讓 Hermes 更慢 | **改方向**：寫成 `ck-platform-context` skill（dynamic tool dispatch）而非 SOUL bloat |

---

## 4. 架構決策的事實基礎

5/5 實機題目 + 1 SOUL 注入失敗，提供以下事實基礎：

| 架構選擇 | 應採 | 不應採 |
|---|---|---|
| AaaP Chat 主路徑 | Groq direct + backend SSOT 注入（11s，準確） | Hermes path（50s+，無 AaaP context） |
| Hermes path 角色 | tool dispatch（呼叫 missive_health 等真實工具）| 通用對話替代 Groq |
| SOUL.md 內容 | 人格與行為原則（current state 5.5KB OK） | SSOT 受管清單 / 動態資料（用 skill 動態查） |
| Backend system prompt | SSOT meta + projects + tower mapping（已落地） | 過長 — 避免超過 prompt window |
| 多問合一 prompt | 教用戶「一次問一題」（compound parsing 會吞子題） | 信任 LLM 多問會完整覆蓋 |

---

## 5. 已產出的文件 / 工程資產（本日）

| 類別 | 資產 | 路徑 |
|---|---|---|
| 政策 | CK Fork Policy | `D:\CKProject\CK_Hermes\CK_FORK_POLICY.md` |
| 政策 | CK AaaP Absorption Policy | `D:\CKProject\CK_AaaP\CK_AAAP_ABSORPTION_POLICY.md` |
| 治理 | SSOT v1.6.1 移除 CK_Showcase | `D:\CKProject\CK_AaaP\platform\services\config\ssot.yaml` |
| 治理 | SSOT changelog v1.6.1 | `D:\CKProject\CK_AaaP\platform\services\config\ssot-changelog.md` |
| 診斷 | L21 診斷計畫 | `docs/plans/2026-05-22-L21-runtime-dispatching-diagnose.md` |
| 計畫 | NEXT_3 v2.1（取代 v2） | `docs/plans/CROSS_SESSION_NEXT_3.md` |
| Lesson | 本檔 | `docs/plans/lesson-l21-hermes-runtime-dispatching-2026-05-22.md` |
| 腳本 | verify-hermes-stack.py 三層 probe | `scripts/verify-hermes-stack.py` |
| 腳本 | _patch_meta_profile.py（profile config fix） | `scripts/_patch_meta_profile.py` |
| 腳本 | _inject_soul_ssot.py（失敗實驗的回顧紀錄） | `scripts/_inject_soul_ssot.py` |
| 修改 | docker-compose.yml 加 PYTHONPATH + port 3010 + provider env | `D:\CKProject\CK_AaaP\runbooks\hermes-stack\docker-compose.yml` |
| 修改 | AaaP Chat backend 加 SSOT system prompt + timeout 反向 | `D:\CKProject\CK_AaaP\platform\services\backend\routers\overview.py` |
| 配置 | profile/meta config.yaml 補 Ollama + Groq fallback | 容器內 `/opt/data/profiles/meta/config.yaml` |

---

## 6. 跨 repo 同步建議（給未來 session）

當 hermes-stack 出問題且現象似「對話不通 / LLM 401 / 神秘 fallback」時，先檢查清單：

1. `docker exec ck-hermes-gateway cat /opt/data/active_profile`
2. `docker exec ck-hermes-gateway cat /opt/data/profiles/$(cat /opt/data/active_profile)/config.yaml | head -20`
   - 看 `model:` 是 `''` 還是 dict — 空就是 L21 同款
3. `docker inspect ck-hermes-gateway --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E "^(HERMES_INFERENCE|OLLAMA|GROQ|ANTHROPIC)" | sed 's/=.*/=<set>/'`
   - env_file 沒進來時改 environment: 直接聲明
4. `python scripts/verify-hermes-stack.py` 三層 probe
5. 若 line A 401，立即跑 [`scripts/_patch_meta_profile.py`](../../scripts/_patch_meta_profile.py) 套 dict-form config

---

## 7. 反思 — 為何花了 8 小時

| 浪費點 | 反思 |
|---|---|
| 假設 memory 推論「runtime hard-coded openrouter」為真，差點寫 ADR-CK-001 | feedback memory 是觀察推論，不是代碼證據；診斷必須代碼 spot check 才能下根因結論（已寫進 R1 §0） |
| docker exec env 全 dump → 4 個 production secret 進對話 transcript | 此類安全事件應**完全避免**：用 `${VAR:+SET}` 模式只回報「有/無」，永不打印實值 |
| 反覆 force-recreate 5+ 次 debug env_file 不 propagate | 早點切到 `environment:` block 顯式聲明可省 ~30min |
| SOUL 注入 SSOT 嘗試前未先評估「prompt size × 處理速度」trade-off | SOUL 改動須先 budget；本次 +1.2KB 造成 >70s 延遲增量 |

---

## 8. 對接下來

NEXT_3 v2.1 升 v2.2（待寫）：
- 新 #1：把 ck-platform-context skill 設計納入 ADR-CK-003 v2 方向（dynamic tool 取代 SOUL bloat）
- 新 #2：Phase 2.5 bulk rename（不變）
- 新 #3：ADR-CK-002 image entrypoint venv quirk（PYTHONPATH workaround 升 ADR）

---

## 關聯
- 觸發 memory：[[feedback-pre-demo-functional-verification]]
- 觸發 memory：[[feedback-integration-over-scope]]
- L21 診斷檔：[`2026-05-22-L21-runtime-dispatching-diagnose.md`](2026-05-22-L21-runtime-dispatching-diagnose.md)
- Fork 政策：[`../../CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)
- 對偶 policy：[`../../../CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md`](../../../CK_AaaP/CK_AAAP_ABSORPTION_POLICY.md)
- NEXT_3：[`CROSS_SESSION_NEXT_3.md`](CROSS_SESSION_NEXT_3.md)
- CROSS_SESSION_BLOCKERS L21 條目：`D:\CKProject\CK_AaaP\platform\CROSS_SESSION_BLOCKERS.md:334`
