# ADR-CK-005: dispatch 可靠度 — agent loop 條件式強制 tool_choice（fork spike 設計）

> 狀態：**rejected → ⚠️ 2026-06-03 查證 ERRATA：受測模型實為 qwen2.5:7b 非 groq（見 §0.5）——「①對 groq 無效」依據失效，①待在真 groq 70b 上重測** — 見下方「⛔ 結果」與「§0.5 ERRATA」

## 0.5 ⚠️ ERRATA（2026-06-03 :9119 dashboard 查證，推翻本 ADR 否決依據）

**本 ADR 全程聲稱受測模型為 groq `llama-3.3-70b`，但實機查證證明實際受測的是 ollama `qwen2.5:7b`。**

- 根因：`active_profile=meta`，`/v1` 載入 **meta profile config.yaml（主模型 qwen2.5:7b，最後修改停在 5/22）**；6/2「config 切 groq」改的是 **root config.yaml**，對 active=meta 不生效（與 6/2 改錯 SOUL 同一陷阱，[[feedback_hermes_active_profile_before_edit]]）。
- 鐵證：tool_choice patch 改 `run_agent.py`（不改 model）→ 受測模型＝當時 active 主模型；`:9119/api/sessions` 今日 9 session（含本 spike 7 樣本，tool_call 1~5）`billing_base_url` **全 = ck-ollama qwen、0 筆 groq**。
- **∴ 正確結論**：本 ADR 證明的是「**qwen2.5:7b** 對被強制的 tool_choice 仍 4/7 吐文字」；**groq 70b 的 tool_choice 遵守度從未被測**。「①對 groq 無效」**不成立**。
- **修正後方向**：①tool_choice **不否決**，但前提是先把 **meta profile config 主模型切真 groq 70b**（root config 無效），再 A/B 重測。
- **→ 2026-06-04 執行結果（在真 groq 上驗證受阻）**：切 groq 70b 真生效（ck-ollama 無 70b、實走 groq.com 坐實），但 **groq 免費 tier on_demand TPM 12k < hermes 每請求 20,427 token → 首次後全 413/502，不可行**，已還原 qwen（端到端複驗 1821 筆 GO）。∴ **①在真 groq 70b 上的驗證被 TPM 牆擋住**，需 groq 付費 tier 或削 prompt<12k 才能測；現實 dispatch 改善回 **③ gateway post-process**（model-agnostic、不受 TPM）。詳見 [`2026-06-03-hermes-ui-integration-review.md`](2026-06-03-hermes-ui-integration-review.md) §2.5。

---

> 日期：2026-06-03 · CK_Hermes session
> 政策：[`CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md) — 本案落 **L3（patch upstream `run_agent.py` + rebuild image + upstream PR 草稿）**
> 關聯：[`adr-ck-003-aaap-consciousness-federation.md §7-S2.5`](adr-ck-003-aaap-consciousness-federation.md)（β spike 反證「tool 形式」非正解）、[`CROSS_SESSION_NEXT_3.md`](CROSS_SESSION_NEXT_3.md) v2.4 #3
> 關聯記憶：[[project_aaap_consciousness_federation_arch]]、[[project_hermes_baseline_go_nogo_20260530]]

---

## 0. 一句話

dispatch 不穩（terminal ~50-75%）的**結構性根因**＝ Hermes agent loop 對 LLM 的每輪呼叫**從不設 `tool_choice`**（預設 auto），模型遂可自由選「發 tool_call」或「把指令寫成文字」。修法＝在 agent loop 的 kwargs 建構單點**條件式注入 `tool_choice`**，強制「業務查詢輪」必發 tool_call。

---

## ⛔ 結果（2026-06-03 spike 已完整實作並 live 測試 → **負向、已還原**）

> supersede「proposed」狀態：本案已實作、部署、A/B 測試、**判定無效並還原至 pristine baseline**。選項①否決。

**實作完全成功，但模型不買單。** patch 正確注入 `tool_choice`（debug log 鐵證：每個首輪 `[acc=1 mode=chat_completions] FORCED tool_choice={'type':'function','function':{'name':'terminal'}} ntools=27`），但 **groq llama-3.3-70b 不可靠地遵守強制**：

| 7 樣本 /v1「公文總數」（toggle=terminal）| turn-1 行為 | 判定 |
|---|---|---|
| 4/7（on1/on3/on4/on7）| 真發 structured `terminal` tool_call | ✅ 強制生效→dispatch（其中 on3/on7 後端生成層降級「AI 回答生成超時」屬殘留③，非 dispatch 問題）|
| 3/7（on2/on5/on6）| **吐成畸形文字**：`ilorc {"terminal": "python3 …query.py…"}`（亂碼 token + tool-call-as-text）| ❌ 強制已套用但 groq 未發 structured call |

- **4/7 ≈ 57%**，落在 baseline ~50-75% 區間內 —— **強制未證明提升可靠度**。
- on6 的 `ilorc` 亂碼 + tool-call-as-text **與 S2.5 β spike（MCP `missive_query`）完全同源失敗模式**（`ilorc`/`incontri la regola` 亂碼）。
- **∴ 鐵證結論**：瓶頸**不在 Hermes 缺 tool_choice**（patch 已補上且正確送達），而在 **groq llama-3.3-70b 對「被強制的 tool_choice」仍間歇吐成文字**——provider/模型的 tool-calling 保真度問題。**選項①（tool_choice，三方向中最被看好者）亦否決。**

**還原**：容器 `run_agent.py` 自 `run_agent.py.bak.20260603-pre-ck005` 還原（md5 = pristine `6d1a08dead…`）、移除 toggle/debug、重啟回 baseline；repo `run_agent.py` `git checkout` 還原（不留核心檔改動）；query.py 探針複驗 `ok/success:true`。**baseline GO 維持。**

**方向重訂（① 既否決）**：
- **③ gateway post-process（現升為首選，因 model-agnostic）**：groq 失敗時格式穩定（`{"terminal":"python3 …query.py…"}` 或裸 query.py 指令字串），gateway 可在收到「文字化 tool call」時偵測 + 真執行。不靠模型保真度。
- **② 換 tool-calling 更穩模型**：根治但涉成本/部署評估（groq 已是當前最佳實測者）。
- patch 程式碼（呼叫點注入 + `_ck_maybe_force_first_tool` helper，env/toggle 雙閘）規格見下 §3/§4，保留供未來參考；**已證對 groq 無效，勿再投入①**。

---

## 1. 背景與既排除項

- baseline 6/2 GO，但 `/v1` dispatch 僅 ~50-75% 可靠：groq llama-3.3-70b 約 1/4 機率把 `terminal: query.py …` **寫成文字不執行**。
- **已排除（ADR-CK-003 §7）**：
  - **S1（SOUL prose 改寫）** ❌ — A/B：改後 0/3，baseline 3/3。prose 反把模型推向「說明模式」。
  - **S2.5 β（把 bridge 註冊成真 tool / MCP `missive_query`）** ❌ — 真 tool 3/3 寫成文字，比 baseline `terminal` 更不穩。**證明瓶頸非「tool 形式 / 有無 surface」**，而是**模型發 structured tool_call 的可靠度**。
- ∴ 真解必在 **runtime/fork 層**，三方向：① 強制 `tool_choice` ② 換 tool-calling 更穩模型 ③ gateway post-process 文字化 tool_call。本 ADR 處理**①（最有望，因下游管道已半通）**。

---

## 2. 根因定位（2026-06-03 唯讀讀碼，行號精確）

| 證據 | 位置 | 結論 |
|---|---|---|
| `/v1` → 建 AIAgent | `gateway/platforms/api_server.py:861 _create_agent` → `886 from run_agent import AIAgent` → `903 AIAgent(...)` | /v1 每請求新建 agent |
| agent 跑 loop | `api_server.py:2754 _run_agent` → `2793 agent.run_conversation()` | loop 在 `run_agent.py` |
| **LLM kwargs 單一建構點** | `run_agent.py:9795 _build_api_kwargs(api_messages)`（呼叫於 `12878`） | 所有 mode 的 api_kwargs 都從這出 |
| **各 mode 傳 `tools=` 但無 `tool_choice`** | `9810/9830/9854`（anthropic/bedrock/codex）+ chat_completions 分支(`9865+`) | tools 有給、tool_choice 全缺 |
| **全檔 `tool_choice` 出現 = 0** | `run_agent.py`（16,319 行）`grep tool_choice` → 0 | **agent loop 從不設 tool_choice → 預設 auto** |
| 下游管道**已備妥** | `agent/anthropic_adapter.py:1986-1996`（OpenAI→Anthropic 映射，含 `required`→`{type:any}`、指名工具→`{type:tool,name}`）；`agent/auxiliary_client.py:964-991`（normalize） | **缺口純粹在「上游 loop 從未傳值」**，adapter 早能吃 |

**∴ 精確改動點 = `run_agent.py:_build_api_kwargs`**：在回傳的 kwargs 條件式加 `tool_choice`。下游 transport/adapter 已能正確翻譯至各 provider（groq OpenAI-compat 亦支援 `tool_choice`）。

---

## 3. 決策（規格）

在 `_build_api_kwargs` 注入**條件式** `tool_choice`，由 profile/config 控制，僅作用於需要 dispatch 的輪次：

### 3.1 觸發條件（避免破壞多輪 / 無限迴圈）
- **僅第一輪**（`turn == 0` / 首次 model 呼叫）強制；其後輪次回 auto，使 agent 能產最終文字（否則 `required` 每輪強制 → 無法收尾）。
- 僅當該 profile 啟用旗標（預設關，meta profile 開）。

### 3.2 強制形式（二選一，spike 對比）
- **(a) 指名工具 `tool_choice={"type":"tool","name":"terminal"}`**：第一輪逼模型必發 `terminal` call → SOUL 既有規則接手「terminal 內跑 query.py」。**精準**但耦合 terminal。
- **(b) `tool_choice="required"`（→ Anthropic `{type:any}`）**：逼發**任一** tool。較鬆，可能發到別的 baseline 工具。
- **建議 spike 先試 (a)**（最貼合現行 terminal→query.py 鏈路）。

### 3.3 config 介面（建議）
```yaml
# profiles/meta/config.yaml（或 platform 級）
dispatch:
  force_first_tool: terminal   # null=關（預設）| "terminal" | "required"
  force_scope: api_server      # 僅 /v1 路徑，不影響 CLI/Telegram
```
`_build_api_kwargs` 讀此旗標 + 當前 turn index 決定是否注入。

---

## 4. L3 Fork 程序（依 CK_FORK_POLICY §2，**實作時才執行**）

1. patch `run_agent.py:_build_api_kwargs`（+ turn index 取得、+ config 讀取）；最小 diff、不碰其他 mode 預設行為（旗標關=零行為改變）。
2. rebuild image `v2026.5.x` + bump `hermes-stack/.env HERMES_AGENT_VERSION`。
3. **A/B live 驗證**（對齊 [[feedback_pre_demo_functional_verification]]）：同問題「公文總數」各 5 次 /v1，比較 `force_first_tool: null`（baseline）vs `terminal`：
   - 預期：baseline ~50-75% dispatch；強制後**首輪 100% 發 terminal**、且仍能產最終繁中文字（無無限迴圈）。
4. upstream PR 草稿送 NousResearch（`tool_choice` 為標準 OpenAI/Anthropic 參數，屬合理擴展點，可能被接受 → 降未來 rebase 負擔）。

---

## 5. 風險 / 開放問題

- **多輪收尾**：必須只強制首輪；需確認 `_build_api_kwargs` 能取得當前 turn index（若無，須由 loop 傳入 → diff 稍大）。
- **(b) required 失準**：可能逼發非 terminal 工具；(a) 指名較穩但耦合。
- **provider 支援**：groq OpenAI-compat 支援 tool_choice；換模型方向（②）獨立保留。
- **不解延遲**：本案只修 dispatch 可靠度，與 ~145-175s 延遲（gateway 每請求重建 agent 的架構性開銷）正交。
- **與 ADR-CK-004 關係**：本案（強制發 tool）是 ADR-CK-004（surface `aaap` toolset 給 LLM）能否可靠被呼叫的**前置**——β spike 已證「只 surface 不強制」未必可靠。**建議 ADR-CK-005 先於 ADR-CK-004 實作**。

---

## 6. DoD（實作驗收，本 ADR 僅定義不執行）

1. 旗標關 → 行為與現況 bitwise 等價（零回歸）。
2. 旗標 `terminal` → /v1「公文總數」5/5 首輪發 terminal call + 仍回正確繁中數字（1,8xx 份）。
3. A/B 數據記入本檔；若強制後反退化（如 β spike），**否決並還原**，轉方向②/③。

---

## 7. 待辦（已收斂 — 本案 rejected）

- [x] ~~使用者裁示是否投入此 fork spike~~ → 2026-06-03 已投入並完成。
- [x] 實作 patch（呼叫點注入 + `_ck_maybe_force_first_tool` helper，env/toggle 雙閘）。
- [x] A/B live 驗證 + 數據回填 §6 → **負向（4/7 落 baseline 區間），否決並還原 pristine**。
- [x] ~~upstream PR 草稿~~ → **因否決不送**（對 groq 無效，無 upstream 價值）。
- [ ] **後續方向（轉出本 ADR）**：③ gateway post-process（首選）/ ② 換更穩模型 — 待使用者裁示，追蹤於 [`adr-ck-003-aaap-consciousness-federation.md §10`](adr-ck-003-aaap-consciousness-federation.md) + [`CROSS_SESSION_NEXT_3.md`](CROSS_SESSION_NEXT_3.md) #3。
</content>
