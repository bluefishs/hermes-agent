# WS-D 設計契約：業務查詢確定性分流（取代 narrow post-process）

> 狀態：design-only（本檔不動 production；零風險）
> 日期：2026-06-09 · CK_Hermes session
> 對應：[`adr-ck-003-aaap-consciousness-federation.md §4/§7-S2.5/S4`](adr-ck-003-aaap-consciousness-federation.md) · [`2026-06-03-hermes-ui-integration-review.md §2`](2026-06-03-hermes-ui-integration-review.md)
> 關聯記憶：[[project_aaap_consciousness_federation_arch]]、[[feedback_integration_over_scope]]
> 政策：[`CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)（本設計**不需 fork**：落 caller 側 + 架構定址）

---

## 0. 一句話

業務文件查詢（公文數/統計）有一條**確定性答案路徑**（`query.py agent_query` → Missive 後端 → 6.4s、100% 可靠）；不該讓它依賴 meta LLM 迴圈「自己決定要不要發 terminal tool_call」（實證僅 70% 可靠、~145-175s）。**分流＝確定性查詢別走 LLM 迴圈，而非把不穩迴圈修到 81%。**

---

## 1. 背景：WS-A 量化裁決（為何放棄 post-process）

2026-06-09 對「③ gateway post-process」做有界研究（唯讀，已還原零殘留）：

### 1.1 Phase 0 — 全量 55 sessions 分類（實證）
| 項 | 值 |
|---|---|
| 業務題分母 | 27 |
| 成功 dispatch | 19（**baseline 70%**，吻合文件 ~50-75%） |
| 文字化可還原 | 2-3 |
| 不可還原硬失敗 | 5 |

**8 失敗案例真實分佈**（逐一讀全文）：裸指令文字化 ×1（`46f0719`）、JSON-fenced 指令 ×1（`e162114b`）、叫錯工具 ×1（救了也無益）、**從 SSOT 幻覺直答 ×2**、**宣告後亂碼死掉 ×1**（`片刻請*****`）、**反問不行動 ×1**、**空回應 ×1**。

→ **post-process 天花板 = 70%→~78-81%（僅 +8-11pp）；失敗中可還原僅 25-38%，低於預設 60% gate。** 主導失敗＝模型根本沒承諾發 tool_call（runtime 層保真度），post-process 無能為力。

### 1.2 Phase 1 — L2/L3 落點（唯讀讀碼）
`run_agent.py` 零 `emit()`/HookManager 參照 → **agent loop 不觸發 hook 系統**（hook 只在 `gateway/run.py:3501` 聊天平臺迴圈接線；`api_server.py` 的 emit 全是 SSE/metrics）。**∴ `/v1` 主路徑不過 hook → L2 hook 不可行 → narrow post-process 只剩 L3 fork（rebuild image + 維護債）。**

### 1.3 合併裁決
**narrow post-process 對 /v1 ＝低 CP 值（收益微 +8pp、成本高 L3 fork）→ 否決。** 同向兩 gate（可還原<60% + L2 關閉）。此為高價值負向結論，**勿再投入**（同 S1/S2.5/tool_choice）。

---

## 2. 核心洞察（分流的地基）

| 路徑 | 可靠度 | 延遲 | 性質 |
|---|---|---|---|
| `query.py agent_query` 直呼 Missive 後端 | **100%**（6/9 驗 1,830 筆） | **6.4s** | 確定性、無 LLM 自由裁量 |
| meta `/v1` LLM 迴圈 → 自發 terminal tool_call | ~70% | ~145-175s | 不穩、每請求重建 AIAgent |

**dispatch 不可靠的根源不是「迴圈修不好」，是「確定性查詢被放進不該放的迴圈」。** 分流即把前者抽出迴圈。

---

## 3. 設計：兩層分流 + 明確邊界

### 3.1 邊界（誠實先講）
- **可零成本確定性化的**：在「進 Hermes LLM 迴圈**之前**」攔截的 caller／定址層。
- **不在 甲 範圍（需 fork）**：raw `/v1` API client 直打 gateway 的 in-loop 確定性化——無 caller 可攔、Hermes 內攔即 L3。這類維持現況 ~70% + 失敗重試，或引導改走下方定址。

### 3.2 Layer 1 — 架構定址（多數已存在，ADR-CK-003 §4）
**Missive 業務查詢 → 坤哥 `/kunge`（Missive 平臺自己的後端意識體，直查後端、不經 meta loop）。** 此入口 `CK_Missive#0031` 已建。
- **meta `/v1` 保留給**：跨域 / 治理 / 平臺級 / 跨平臺統整題。
- **「工作」不是寫新東西，是讓前端/使用者走對入口**：Missive 平臺問公文→坤哥；AaaP 平臺問跨域→Meta。
- 落點：CK_Missive / CK_AaaP 前端導引（**非本 session**）。

### 3.3 Layer 2 — caller-side fast-path（混合入口才需）
對「一個聊天框混進業務題」的入口（典型＝AaaP Chat，`CK_AaaP/platform/services/backend/.../overview.py`，已有 Groq fallback + SSOT 注入）：
```
使用者訊息 → [業務查詢分類器] ──命中──▶ 直呼 Missive /api/ai/agent/query（service_token）
                              │                    └─▶ 回確定性答案（~6s），不進 Hermes
                              └──未命中──▶ 既有 Hermes meta /v1 路徑
```
- 落點：**CK_AaaP session**（caller 在 AaaP 後端）。
- 復用：認證鏈（`X-Service-Token` / `POST /api/ai/agent/query` / `service_auth.py`）已通（6/2 建）。

---

## 4. 分類規格（窄定義，防誤判偷走對話題）

**只攔「確定性 lookup」，不攔「討論/設計」**：

- ✅ 命中（路由到 fast-path）：含統計/計數意圖 — `公文.*(總數|幾份|多少)` / `收文|發文.*(數|幾)` / `統計` / `總共.*份`。
- ❌ 排除（即使含「公文」也走 Hermes）：含討論詞 — `怎麼|如何|為什麼|建議|設計|流程|管理|優化|比較`（這些是對話題，非查數）。
- **精度優先於召回**：寧可漏攔（退回 Hermes ~70%）也不可誤攔對話題（毀 UX）。初版只收計數/統計，驗證穩定再漸擴。
- 分類器形式：caller 側正則／關鍵字即可（**不需 LLM、不需 Hermes**）；未來可選輕量意圖模型。

---

## 5. Session 歸屬 + DoD

| 層 | 動作 | Session | DoD |
|---|---|---|---|
| L1 定址 | 前端導引 Missive 業務→/kunge、跨域→Meta | CK_Missive/CK_AaaP | 平臺問業務不再落 meta loop |
| L2 fast-path | AaaP Chat 加業務分類器→直呼 Missive agent query | **CK_AaaP** | 「公文幾份」→ ~6s 確定性答對、未進 Hermes；對話題仍走 Hermes |
| 守則 | 分類器精度測試（業務題 vs 對話題各 N 例） | CK_AaaP | 零誤攔對話題 |

> **本 CK_Hermes session 能交付的＝本設計契約**（分類規格 + 落點 + 邊界）。實作落 CK_AaaP/CK_Missive session（caller 側），對齊「Session 啟動位置分流」§7。

---

## 6. 風險 / 守則
- 🟡 **誤攔風險**（Layer 2 主風險）：分類器太寬→偷走對話題。緩解＝窄定義（§4）+ 精度測試 + 排除討論詞。
- 🟢 **不碰 Hermes**：本設計零 fork、零 image rebuild、不動 meta SOUL/config（避 S1 prose 教訓）。
- 🟢 **正交 baseline**：fast-path 未命中即原路 Hermes，baseline GO 不受影響。
- ⚠️ **不解 raw /v1 in-loop**（§3.1 邊界）：那類維持 ~70%+重試，或引導改定址；若未來真要 in-loop 確定性＝回到 fork 決策（彼時才評估 WS-A「替代乙 rescue」天花板 100% 版）。

---

## 7. 關聯
- WS-A 量化來源：[`2026-06-03-hermes-ui-integration-review.md`](2026-06-03-hermes-ui-integration-review.md)（§2 主模型/延遲）
- 架構定址：[`adr-ck-003-aaap-consciousness-federation.md §4`](adr-ck-003-aaap-consciousness-federation.md)
- 認證鏈/部署包：`CK_Missive/docs/hermes-skills/ck-missive-bridge/`
- Memory：[[feedback_integration_over_scope]]、[[feedback_pre_demo_functional_verification]]
