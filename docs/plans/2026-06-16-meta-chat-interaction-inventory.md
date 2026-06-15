# Meta Chat 交流盤點複查 + 深化評估（2026-06-16）

> CK_Hermes session。使用者：「盤點複查深化 Hermes meta chat 交流」。
> 方法：對 live `/v1 model=meta` 跑多組對話探針（非僅 healthcheck），實測對話品質。
> 關聯 [[project_meta_chat_restore_deepening]]、[`2026-06-15-meta-chat-restore.md`](2026-06-15-meta-chat-restore.md)。

## 1. 盤點 — meta chat 交流能力矩陣（live 實測）

| 能力 | 狀態 | 實測證據 |
|---|---|---|
| chat 入口 `/v1 model=meta` | ✅ | HTTP 200、繁中主腦回應 |
| 繁中一致（R1）| ✅ live | runtime 啟用後零簡體（「聊天记录」→「對話記錄」）|
| **對話內連貫**（client 重送 history）| ✅ | 帶 3-msg history → 正確「阿廷…成大鹽倉…存量監測」（Open WebUI 走此路徑，體驗正常）|
| R2 記憶引擎（寫 daily/briefing）| ✅ autonomous | 昨晚 daily-closing 自主 fire ok |
| session_search 工具 | ✅ 存在且會被調用 | `tools/session_search_tool.py`；探針觸發後 prompt 漲 15.7k→31.8k（注入搜尋結果）|
| **跨 session 記憶「綜合」** | ❌ **弱** | 問「WS-D 過去結論」→ 真的搜了，但回「未形成明確共識，請提供更多資訊」（**錯**：過去共識豐富）→ qwen 取回了卻綜合不出 |
| 伺服端 session-key 連貫 | ❌ 失效 | turn2 帶 `X-Hermes-Session-Key`=turn1 id → 不記得，反**捏造**「林…赫墨斯代理」|
| 無 context 時的行為 | ❌ 捏造 | 缺記憶時編造似真答案（同業務查詢捏造類）|
| 延遲 | ⚠️ | 一般 60–90s；觸發 session_search 的記憶對話 **266s**（極慢）|

## 2. 複查 — 核心判斷

**深度記憶的「基礎設施」已全部到位，瓶頸收斂為單一點：qwen2.5:7b 的「決定使用記憶 + 綜合取回內容」能力。**

- 寫入端（R2 引擎）✅、取回端（session_search/memory_tool/wiki）✅、對話內連貫（history）✅ — 管路都通。
- 但**用記憶**這一步卡在模型：
  - 不可靠地「決定」去查（同 dispatch ~70% 保真度問題）。
  - 即使查了，**綜合 80k-token 原始 session 的能力不足** → 回泛泛/「找不到」而非真回憶。
  - 缺 context 時**捏造**而非誠實說「沒有那段記憶」。
- 這與 dispatch/groq 同源：**模型強度牆**（qwen 弱、groq 免費 tier TPM 不可行）。∴ 再加管路邊際效益遞減；真槓桿＝模型強度（未來）或**讓記憶更「好嚼」**（見下）。

## 3. 深化建議（依 CP 排序）

### D-α · 讓回憶走「策展 wiki」而非原始 session（CP 最高、治本於 qwen 弱）
原始 session_search 注入 80k-token 原文 → qwen 綜合不動（266s + 泛泛）。但 **wiki 是策展層**（`concepts/` 30+ 頁精煉 + R2 daily/briefings 摘要），小而結構化、qwen 好嚼。
- 作法：SOUL「記憶系統」段強化為**回憶優先讀 `llm-wiki`（wiki concepts/briefings），session_search 僅為補充**；並讓 R2 briefings 成為「上週摘要」的主要來源。
- 效益：回憶更快（不注入 80k 原文）、qwen 綜合得動、與 R2 引擎閉環。

### D-β · 反捏造 recall 規則（安全，止血最危險項）
SOUL 加硬規（比照現有業務查詢反捏造）：**問及「記得/之前/上週」類，若 wiki/session_search 無確切命中，須誠實說「我沒有那段確切記憶」，禁止編造名字/主題/結論。**
- qwen 遵守非 100%，但業務反捏造規則實證大致有效，值得加。

### D-γ · 伺服端 session-key 連貫修復（中）
turn2 帶 `X-Hermes-Session-Key` 未接續 turn1 → 薄客戶端（Telegram/未來 LINE）無連貫。Open WebUI 走 history 不受影響故非緊急。需查 api_server 的 session-key→session 載入邏輯（屬 hermes runtime）。

### D-δ · 模型強度（已知牆，未來）
qwen 綜合弱是根本。groq 免費 tier TPM 牆使 /v1 不可行；付費 tier 或更強本地模型為未來解。**短期不投入**。

## 4. 建議下一步
- **先辦 D-β（反捏造）+ D-α（wiki-first 回憶）**：皆為 `profiles/meta/SOUL.md` 強化，零成本、CP 最高、與本 session 已復原的 R2 閉環。
- ⚠️ 動 SOUL = 動人格，依 SOUL 自身「改前先對話」原則 + [[feedback_hermes_active_profile_before_edit]]，**先取得使用者確認再改該 profile 底下的檔**（改後 live 驗證 + 備份）。
- D-γ/D-δ 排後（runtime / 模型層）。

> 一句話：**meta chat 的「能對話、繁中、對話內連貫、會寫記憶」都已 live；缺的是「可靠地把記憶用進對話」——這卡在 qwen 強度，最佳短期解是讓記憶走策展 wiki（好嚼）+ 反捏造止血。**
