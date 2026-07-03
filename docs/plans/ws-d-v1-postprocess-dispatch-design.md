# WS-D 候選 #3 設計契約 — /v1 業務查詢後處理攔截（治捏造 / 文字化 tool_call）

> 2026-07-03。承 `2026-07-03-integration-review.md` 附三、`ws-d-business-query-fastpath-design.md`、ADR-CK-005 ③。
> **狀態：設計契約（待使用者 GO 後 TDD 實作）。未改任何 runtime 程式碼。**

## 1. 問題陳述（實測坐實）

`/v1` meta 對話問業務查詢（如「公文幾份」），弱模型 qwen2.5:7b 兩種失敗模式：
- **A. 捏造數字**：後端沒回數字 → 自編（實測「1234」，ground truth 1895）。
- **B. 文字化 tool_call**：選對工具但寫成文字沒執行（實測 `terminal("...query.py agent_query --question \"...\"")`）。

兩者同源＝**模型發 structured tool_call 的保真度牆**（runtime 層，非 prompt/tool 形式）。免費基礎（本地 qwen）下無法靠換模型/prompt 解（6/3~6/16 三方向全否決）。

## 2. 為何落在 api_server 後處理層（非 hook、非 caller 側）

- 框架 hook 系統（`gateway/hooks.py`）**對 /v1 emit=0**（0.13.0 實查）→ hook 路線不可行。
- caller 側（AaaP Chat 分類器）只覆蓋單一 caller，Open WebUI→/v1 這條真實入口涵蓋不到。
- **∴ 唯一 model-agnostic、覆蓋所有 /v1 client 的落點 = `api_server.py` 回應後處理**，與既有 `convert_zh()` 同注入點（非串流 `:1290`、串流 `:1435`）。不受 TPM、不靠模型強度。

## 3. 🔴 資安關鍵：窄白名單（絕不通用執行模型輸出）

**威脅**：若後處理盲目執行模型吐出的任何 `terminal(...)` 文字，模型（或 prompt injection）可令其執行 `terminal("rm -rf ...")` → RCE。

**鐵則**：
1. **只匹配單一已知安全樣式**：`terminal("<path>/query.py agent_query --question \"<Q>\"")`，且 `<path>` 必須 endswith `ck-missive-bridge/scripts/query.py`（或白名單 skill 清單）。
2. **只執行 query.py 的 `agent_query`（或其他唯讀 action 白名單）**，其餘一律不執行、原文放行。
3. **參數消毒**：`<Q>` 只當作 `--question` 的值傳入（argv 陣列、非 shell 字串插值），禁 shell 展開。
4. 偵測不到白名單樣式 → **完全不動、原文放行**（fail-safe）。

## 4. 攔截邏輯（pseudocode）

```
def intercept_business_dispatch(response_text, original_question) -> str:
    # 僅在 feature flag 開啟時作用（HERMES_V1_DISPATCH_FIX）
    if not enabled(): return response_text

    m = MATCH_TEXTIFIED_QUERYPY.search(response_text)   # 嚴格 regex，見鐵則 1
    if not m: return response_text                       # fail-safe：非白名單樣式原文放行

    question = m.group("question") or original_question
    try:
        result = run_query_py(action="agent_query", question=question, timeout=90)  # argv 陣列、非 shell
    except Exception:
        return response_text                             # 執行失敗→原文放行，不破壞對話

    if not result.get("success"): return response_text
    answer = result["data"]["answer"]                    # 後端真實答案（含數字）
    return answer                                        # 交由既有 convert_zh() 繁化
```

- 掛載順序：`intercept_business_dispatch()` **先於** `convert_zh()`（回填後再繁化）。
- 串流：文字化 tool_call 難在 delta 逐塊偵測 → **串流路徑先只做「完整回應」偵測**（緩衝到 finish 再攔截），或串流時停用本功能、退回非串流補救。MVP 先做非串流（`:1290`）。

## 5. Feature flag / 回滾

- env `HERMES_V1_DISPATCH_FIX`（預設 off，opt-in，如 `HERMES_ZH_CONVERT` 模式）。
- 回滾＝unset env（即時 no-op），或還原 image。烤入 image 後預設關、compose 設 flag 開（部署解耦）。

## 6. TDD 案例（RED→GREEN）

| # | 輸入 | 期望 |
|---|---|---|
| T1 | 回應含 `terminal("...ck-missive-bridge/scripts/query.py agent_query --question \"公文幾份\"")` | 攔截、執行、回填真實數字（1895）|
| T2 | 一般對話「你好」 | 原文放行、不觸發 |
| T3 | 回應正常已含數字（dispatch 成功） | 不重複執行、原文放行 |
| T4 | **惡意** 回應含 `terminal("rm -rf /")`（非白名單） | **不執行**、原文放行 |
| T5 | 回應含非白名單 skill `terminal("...other.py ...")` | 不執行、原文放行 |
| T6 | query.py 執行逾時/失敗 | graceful 原文放行、對話不破 |
| T7 | flag off | 完全 no-op |

## 7. 實作步驟（GO 後）

1. TDD：先寫 `tests/gateway/test_v1_dispatch_intercept.py`（T1–T7）RED。
2. 實作 `gateway/dispatch_intercept.py`（regex 白名單 + run_query_py argv 執行 + fail-safe），api_server.py `:1290` 掛載於 `convert_zh` 前。
3. GREEN → 本地 pytest 全綠。
4. rebuild image（v2026.7.x）→ deploy（compose 設 `HERMES_V1_DISPATCH_FIX=agent_query`）。
5. 驗收：/v1 業務查詢連測 5 次全回真實數字、一般對話無副作用、health-smoke 8+1、惡意樣式不執行。
6. 更新 CLAUDE.md/memory、commit、tag。

## 8. 預期效益

- **治本捏造/文字化 tool_call**：dispatch 保真度不再是使用者可見缺陷（後端真值回填）。
- model-agnostic、零額外成本、不受 TPM。
- 殘留（非本案）：延遲（每請求重建 AIAgent，架構性）、跨 session 記憶（模型強度 D-δ）。
