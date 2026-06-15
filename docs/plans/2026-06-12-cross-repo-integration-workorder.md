# 跨 repo 整合優化工單（6/12 覆盤後逐項落地）

> 狀態：工單（本 session＝meta，產出精確規格；**最終 apply 落各 repo session**，避免從錯 session 盲改生產碼）
> 日期：2026-06-12 · CK_Hermes session
> 來源：[`2026-06-12-restart-integration-review.md`](2026-06-12-restart-integration-review.md) §5
> 政策：[[feedback_integration_over_scope]]（整合優先、拒分散虛功）、[[feedback_pre_demo_functional_verification]]、Session 啟動位置分流（CONVENTIONS §7）

---

## WO-1 · ~~P0~~ → P1 預防性 · 修 baseline 計數回歸（CK_Missive session）

> **6/15 狀態更新**：症狀**未重現** — `query.py agent_query`「公文總數」**連測 3/3 全回確切數字 1847**（=ground truth `documents:1847`，probe2 拆 1281 收文+566 發文），即使全走弱模型 gemma4。→ 6/12 的「吐建議無數字」屬**暫態**、已消退。**降為 P1 預防性**：結構性「決定性短路」（修法 1）仍建議做，防弱模型未來再吞數字 + 治 gemma4「數字後綴泛用建議」觀感；非阻斷。詳見 [`2026-06-15-integration-review.md`](2026-06-15-integration-review.md)。

### 根因（6/12 讀碼鎖定，非純暫態）
`CK_Missive/backend/app/services/ai/agent/agent_synthesis.py:106-134` 合成 system_prompt 明文：
- 回覆原則 #4「量化表達 — …**不要只說「有幾筆」**」
- 回覆原則 #5「可行動建議 — 回答結尾給 1-2 個具體的下一步建議」
- 「統計/分析回覆模板」結尾＝「建議：具體的行動項目」

→ **強模型（groq/nvidia）能兼顧「確切數字＋建議」；弱 fallback（ollama gemma4）偏向「只給建議、丟掉數字」。** 故 6/9 gemma4 回得出 1,830、6/12 同 gemma4 全是建議＝prompt 設計 × 模型強度交互，**非單純 provider 暫態**。6/12 兩探針實證：`get_statistics` 有跑、`success:true`，但 answer＝純建議無數字。

### 修法（二擇一或並用，皆 CK_Missive 內）
1. **決定性短路（首選、最穩）**：純計數/統計 query（`_should_inject_graph_context` 已能判定「tool_results 全是純 stat tool」）→ 在 synthesis **前**用模板把 `get_statistics` 的數字直出（例：「目前公文共 N 筆（收文 X＋發文 Y）。」），再讓 LLM 接「分析/建議」。數字永不經弱模型遺失。
2. **prompt 補強**：synthesis system_prompt 加硬規「**第一句必須先給確切數字**，數字優先於建議；統計題即使要建議，也不可省略原始數字」。改善但仍依賴模型遵守（弱模型不保證）。

### DoD
- `query.py agent_query`「公文總數」連測 3 次（含 ollama fallback 路徑）→ answer **必含確切數字**。
- 不回歸：強模型路徑（groq）答案品質不降。
- 落點：`agent_synthesis.py`；驗證走 `query.py` 直呼（繞 /v1）。

---

## WO-2 · P0 · 開 `/api/ai/memory/digest`（CK_Missive session）

### 現況（6/12 查證）
- `grep memory/digest backend/app/` → **無此 route**（只有 `optimization_pipeline_orchestrator.py` 的 LINE digest helper：`format_digest_markdown` / `push_digest_to_line`）。
- `POST /api/ai/memory/digest` 實測回 **405**（非 404）→ 推測路徑前綴被既有 router 匹配但無 POST handler；需 CK_Missive 確認 router 掛載。

### 修法
- 依 [`s3-meta-federation-briefing-design.md`](s3-meta-federation-briefing-design.md) 契約開 `POST /api/ai/memory/digest`（service_token 認證，回各意識體成長摘要 JSON）。
- query.py 已預接此 action（`scripts/query.py:89-95`，現預期 404/405＝「機制就緒等後端」）。

### DoD
- `POST /api/ai/memory/digest`（X-Service-Token）回 200 + digest JSON。
- 解 ADR-CK-003 §7 **唯一外部阻斷**（S3 段A）。

---

## WO-3 · P0/P1 · WS-D Layer 2 業務查詢 fast-path（CK_AaaP session）

### 規格（設計契約已備）
見 [`ws-d-business-query-fastpath-design.md`](ws-d-business-query-fastpath-design.md) §3.3/§4：
- 落點：`CK_AaaP/platform/services/backend/.../overview.py`（AaaP Chat，已有 Groq fallback + SSOT 注入）。
- 流程：使用者訊息 → 窄業務分類器（正則，§4）→ 命中→直呼 Missive `POST /api/ai/agent/query`（service_token，~6s 確定性）→ 未命中→原 Hermes meta /v1。
- 復用認證鏈（`X-Service-Token`，6/2 已通）。

### DoD
- 「公文幾份」→ ~6s 確定性答對、**未進 Hermes**；對話題（怎麼/建議/設計）仍走 Hermes。
- 分類器精度測試：業務題 vs 對話題各 N 例，**零誤攔對話題**（精度優先於召回）。

---

## WO-4 · P1 · WS-D Layer 1 架構定址（CK_Missive + CK_AaaP session）

- Missive 平臺前端：業務查詢導引 → 坤哥 `/kunge`（`CK_Missive#0031` 已建，直查後端不經 meta loop）。
- AaaP 平臺：跨域/治理/統整 → Meta `/v1`。
- DoD：平臺問業務不再落 meta 175s 迴圈。

---

## WO-5 · P1 · FT_StorageTank（鹽倉）整合決策 → 見 [`2026-06-12-ft-storagetank-integration-decision.md`](2026-06-12-ft-storagetank-integration-decision.md)

決策待用戶確認（整合範圍/優先序）。**先決策再動工。**

---

## 優先序與依賴

```
P0  WO-1（計數回歸）   ← 唯一影響「公文幾份」可用性的活問題，最先辦
P0  WO-2（digest）     ← 解 S3 唯一外部阻斷
P0/P1 WO-3（fast-path）← 繞 175s 迴圈、確定性業務答案；依賴認證鏈（已通）
P1  WO-4（定址）       ← 前端導引，與 WO-3 互補
P1  WO-5（FT 整合）    ← 待用戶決策
```

> 本 session（CK_Hermes/meta）交付＝本工單 + FT 決策文件 + 6/12 覆盤。WO-1~4 之 apply 落 CK_Missive/CK_AaaP session（同機可執行，但為記憶衛生與 commit 分流，建議於對應 repo session 進行）。
