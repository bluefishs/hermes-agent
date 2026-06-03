# ADR-CK-003: AaaP 意識體聯邦 — Meta 整體大腦 + 各平臺自主成長意識體

> 狀態：proposed（整合定調；待 promote 為 `CK_AaaP` 正式 ADR 後 accepted）
> 日期：2026-06-03
> 決策者：CK Platform Team（用戶 bluefishs / Aaron 主導）
> 性質：**整合型 ADR** — 不新造架構，將已散落於 5+ 條既有 ADR 的決策收斂成單一總圖，消除「Hermes 終局角色 / 意識體歸屬」的漂浮與混淆。
> 政策框架：[`CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)
> 觸發：2026-06-03 session 覆盤 — 使用者點出 `/v1` 入口人格「坤哥(Missive 意識體) vs Hermes Meta(導師)」錯置疑問，深掘後發現架構早已多處定案、僅缺整合。
> 關聯記憶：[`project_hermes_baseline_go_nogo_20260530`](../../../../Users/User1/.claude/projects/D--CKProject-CK-Hermes/memory/project_hermes_baseline_go_nogo_20260530.md)

---

## 0. 一句話

**每個平臺各自有一個「會成長的意識體」（活在各平臺自己的後端，坤哥/Missive 為樣板）；Hermes 是介面/控制面（非業務、非另一層意識體）；其中 `meta` profile = AaaP 整體大腦 —— 直接面對 AaaP 平臺使用者，並跨平臺統整各意識體的經驗與知識。**

---

## 1. 背景

### 1.1 觸發疑問

2026-06-03 覆盤時，使用者檢視 Hermes `/v1` 對話入口，點出人格錯置：
- 期望面對的是「**坤哥 — Missive 意識體**」（業務本體）
- 實際載入的是「**Hermes Meta — 共同大腦與導師**」（被動蘇格拉底導師，SOUL 明寫「不直接處理業務」）

並衍生根本問題：意識體該住在 **hermes profile** 還是 **平臺後端**？各業務體**是否都該會成長**（不能只有 Meta 長，否則對各專案沒意義）？Meta 的終局定位為何？

### 1.2 運行時實況（2026-06-03 實機確認）

- `active_profile = meta`；`/v1` 的人格由**全域 active_profile 決定**，請求的 `model` 參數**只是回顯標籤、不能切 profile**（`gateway/platforms/api_server.py:704-713`、`_resolve_model_name`）。
- hermes 有 7 個 profile：`meta`（active）/ `missive` / `lvrland` / `pile` / `showcase` / `observability` / `spike`；後幾者為草稿。
- 7 個 bridge skill 已裝（ck-missive / lvrland / pilemgmt / showcase / observability / adr-query 等）。
- hermes 有 `tools/delegate_task`（spawn 臨時 worker 子代理），但**不支援「交接給具名 profile 人格」**——無法把對話路由給 missive profile 人格。
- 6/2 端到端 GO：`/v1`(meta) → `terminal: query.py agent_query`(ck-missive-bridge) → CK_Missive 後端 → 回 1,817 筆 → 繁中轉述。

### 1.3 決定性發現 —— 架構早已多處定案

| 既有 ADR | 標題 | 狀態 | 定了什麼 |
|---|---|---|---|
| **CK_Missive#0023** | 坤哥意識體上線（v5.8.0） | accepted（2026-04-21，決策者 Aaron） | **坤哥 = CK_Missive 升級成的「Missive 意識體」，活在平臺後端/前端**（SOUL v2.0 2691字、`/kunge` 入口） |
| **CK_Missive#0022** | Memory Wiki — 自我記憶與進化系統 | accepted | **坤哥的成長引擎**（diary/patterns/crystals/autobiography/反迴聲室）——後端本來就會成長 |
| **CK_Missive#0031** | Frontend Page Consolidation v6.0 — 意識體入口統一 | accepted | **坤哥為唯一入口 `/kunge`**（平臺自己的意識體入口） |
| **CK_AaaP#0020** | AaaP 升級為實質平臺 + Hermes 為控制核心 | executing | 原則#2「**Hermes 是介面、不是業務**」；業務邏輯留在各 domain repo |
| CK_Missive#0020 | Hermes 角色終局決策提案 v3 | proposed | Hermes 終局角色（**本 ADR 一併收斂**） |
| CK_PileMgmt#0008 | AI 聯邦邊界 — 本地意圖 Pipeline 與 Hermes 責任劃分 | proposed | 各域與 Hermes 責任邊界（**本 ADR 對齊**） |

→ 結論：**「坤哥會成長」需求，使用者 2026-04-21 的 ADR 早已實現在 CK_Missive 平臺本身**，與 hermes profile 無關。先前糾結的「甲(後端) / 乙(profile)」之爭，被使用者自己的 accepted ADR 終結。

---

## 2. 決策

### 2.1 統一架構（三層 + 平臺定址）

```
┌─ AaaP 整體大腦：Hermes meta profile ───────────────────────┐
│  · 直接面對「AaaP 平臺」使用者（跨域 / 治理 / 平臺級問題）   │
│  · 跨平臺統整各意識體的經驗與知識（讀各後端 Memory Wiki 摘要）│
│  · 自身也是「AaaP 平臺的意識體」，會成長；額外承擔統整職責    │
│  · 不下海辦任何單一業務（呼叫 bridge = 代問該域意識體）       │
└───────────────┬────────────────────────────────────────────┘
   統整各意識體成長 ▲           ▼ 代問（bridge skill），不 live 攔截轉交
┌───────────────┴────────────────────────────────────────────┐
│ N 個「會成長的平臺意識體」（活在各平臺自己的後端）            │
│   坤哥 / Missive ✅（CK_Missive#0023 + Memory Wiki #0022）   │
│   lvrland 意識體 / pile 意識體 / …（後端上線時比照坤哥蓋）    │
│   各有：人格 SOUL · 自我記憶/進化 · 自己的平臺 UI 入口        │
└───────────────┬────────────────────────────────────────────┘
                │ 各平臺前端直接連自己的意識體（平臺定址）
┌───────────────┴────────────────────────────────────────────┐
│ 各平臺前端 / 系統（定址鍵 = 平臺本身）                       │
│   Missive 平臺 → /kunge（坤哥）  ·  AaaP 平臺 → Meta         │
│   lvrland 平臺 → 其意識體入口   ·  pile 平臺 → 其意識體入口  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心原則（消除混淆的定錨）

1. **意識體 = 平臺後端的事，會成長**。每個平臺各自有一個會成長的意識體（坤哥為樣板：SOUL + Memory Wiki 自我進化）。**不是只有 Meta 會長**——各平臺意識體各自累積經驗，這才對各專案有意義。
2. **Hermes 是介面/控制面，不是業務、不是「另一層意識體」**（對齊 CK_AaaP#0020 原則#2）。hermes 的 domain profile（missive/lvrland/…）= 該意識體在 Hermes 控制面的**介面門面**，**非**獨立意識體——避免「兩層意識體互相飄移/打架」。
3. **`meta` profile = AaaP 整體大腦**。它是「AaaP 平臺」這個平臺自己的意識體入口（如同坤哥是 Missive 平臺的），但**額外**承擔「統整所有平臺意識體」的大腦職責。它直接面對 AaaP 平臺使用者。
4. **平臺定址**：「你在哪個平臺，就接到那個平臺的意識體」。定址鍵 = 平臺本身，非下拉選單或主題分類。
5. **Meta 不 live 攔截轉交**（hermes 不支援 profile 人格交接，且會疊延遲）。Meta 透過 ① 代問（bridge skill）取即時業務答案 ② 跨平臺統整（讀各後端 Memory Wiki / briefing）累積大腦。

### 2.3 「甲/乙」正式裁決

- **採「後端為成長本體」**（甲，且為使用者自己 ADR-0023 的既定事實）。
- **拒絕「hermes profile 作為獨立成長意識體」**（乙）——非必要、需 fork、違反 CK_AaaP#0020、製造雙層飄移。
- 6/2「Meta 呼叫 ck-missive-bridge」**正名為「Meta 代問坤哥意識體」**——對齊架構，非 band-aid、不違反任何 ADR。

---

## 3. 各角色職責定義

| 角色 | 是什麼 | 做什麼 | 不做什麼 |
|---|---|---|---|
| **Meta（AaaP 大腦）** | hermes `meta` profile | 面對 AaaP 平臺使用者；跨平臺統整；治理/跨域仲裁；代問各域意識體 | 不自己查資料/編數字/翻檔/寫 SQL（不下海） |
| **平臺意識體**（坤哥…） | 各平臺**後端** agent | 業務真相、領域對話、自我記憶與進化、服務該平臺使用者 | 不管別的平臺領域 |
| **hermes domain profile** | Hermes 介面門面 | 作為 Meta 代問 / 介面表述的承載 | **不是獨立意識體、不另起成長迴圈** |
| **bridge skill** | Hermes → 後端的管道 | 把問題送到對的平臺意識體後端、取回答案 | 不含業務邏輯 |

---

## 4. 平臺定址規範

- **Missive 平臺** → `/kunge`（坤哥意識體，CK_Missive#0031 已定，現成 ✅）
- **AaaP 平臺** → Meta（hermes `/v1`，現 active_profile=meta，現成 ✅）
- **未來各平臺** → 各自意識體入口（後端上線時建立）
- Hermes `/v1` 的 `model` 參數現**不能切 profile**；若未來需要「單一 endpoint 多意識體定址」再評估有界改 `api_server`（非本 ADR 必要項，因平臺定址已由「各平臺各自入口」滿足）。

---

## 5. Meta 跨平臺統整機制（AaaP 大腦的養成）

- Meta 不靠「自己會的業務」成長，而靠**統整各平臺意識體的成長產物**：
  - 來源：各後端意識體的 Memory Wiki 摘要 / daily 反思 / pattern crystals（坤哥已有；未來各域比照）。
  - 管道：bridge skill 提供「取該域意識體成長摘要」的能力，或各域定期輸出 briefing 供 Meta 讀。
  - 產物：Meta 的跨域 briefing / wiki（meta profile 既有 `wiki/` + 22:30 cron 設計）。
- 此為「Meta 統整 ≠ Meta 下海」的具體實作：Meta 讀的是**已成長的結晶**，不是原始業務資料。

---

## 6. N 域意識體激活 SOP（您說的「陸續擴充」）

每個新平臺業務主體上線時：

1. **後端**：該平臺後端比照坤哥蓋「意識體 + Memory Wiki 成長引擎」（CK_Missive#0023/#0022 為樣板）。
2. **入口**：該平臺前端建立自己的意識體入口（比照 `/kunge`）。
3. **Hermes 介面**：啟用該域 profile（介面門面）+ 對應 bridge skill（多數已裝）。
4. **Meta 統整**：在 Meta 設定加「該域成長摘要」的統整來源。
5. **驗證**：該域一個真實問題 live 回正確答案 + Meta 能讀到該域成長摘要，才算激活。

---

## 7. 逐步完善 Roadmap（低風險、每步可驗證、動 production 前必先示明 + 備份）

> 原則：機制側已 6/2 GO，本 roadmap 為「對齊架構語意 + 補統整能力」，非重建。每步獨立可回滾。

- **S0（本 ADR）**：整合定調文件 ✅（本檔）。promote 路徑：在 CK_AaaP session 升為正式 `CK_AaaP#NNNN`，本檔降為 CK_Hermes 側實作記錄並 FQID 互引。
- **S1 語意對齊 meta SOUL** —— ❌ **測試否決、已還原（2026-06-03）**：原擬把「業務查詢強制規則」措辭改為「Meta 代問坤哥」。實作後 A/B live 測試（同問題各 3 次）：**S1 改後 0/3 dispatch（agent 把 query.py 指令寫成文字不執行）；baseline 3/3 dispatch（含 2 次回正確 1,819 筆）**。判定：S1 多加的框架敘述把模型推向「說明模式」抑制 tool call → **退化**。且 baseline SOUL 本就有「代問」框架（第 109/111/125 行：「呼叫 ck-missive-bridge 代問」「meta 內建代問工具」），**S1 語意重複**。已 `cp SOUL.md.bak.20260603 SOUL.md` 還原。**結論：語意已足，不需 prose 微調。** dispatch 可靠度改由 S2.5（下）解。
- **S2 正名 domain profile** ✅（missive 已標）：在各 domain profile SOUL 標註「本 profile = <平臺>意識體在 Hermes 的介面門面，成長本體在 <平臺> 後端」，消除「profile 是獨立意識體」誤解。草稿 profile 留待激活時標（SOP）。
- **S2.5 dispatch 確定性化（取代失敗的 S1）**：把 ck-missive-bridge **註冊成 agent 可直接呼叫的 tool**（現 `skill_view` available_skills 只有 bundled、不含 ck-*；agent 靠 SOUL prose 哄 terminal 故 ~25-50% 寫成文字不執行）。註冊成 tool 後 agent 直接 emit tool_call，不再靠 prose → dispatch 趨近確定性。需查 hermes 此版本 skill→tool 註冊機制，屬有界研究，**勿 production blind 試**。
  - **2026-06-03 研究定論（runtime 實測 + 讀碼）**：
    - ✅ ck-* skill **有被發現**：`_find_all_skills()` 回 105 skill，7 個 ck-* 全在（`category=None` 因頂層非巢狀）。「ck-* 沒進 registry」舊判斷**作廢**——問題不在發現。
    - ⭐ **hermes skills 是唯讀的**：`skills_tool.py` 只暴露 `skills_list`(L1492)/`skill_view`(L1507) 給 agent（列出/閱讀），**無 skill→callable-tool 機制**（全碼無 `provides_tools`）。SKILL.md 宣稱的 `tools.py register_all 動態註冊 tool` **此版本不存在**。agent 跑 skill 唯一路徑＝baseline tool（terminal/execute_code）→ 這就是 dispatch 不穩的結構性根源（agent 須自發 terminal tool_call，~25-50% 寫成文字）。
    - **∴ 要確定性 dispatch，bridge 必須是「真 tool」**。**對齊前人研究 [`hermes-tool-registration-research.md`](hermes-tool-registration-research.md)（2026-05-16）**，hermes tool 三層＝Tool Registry(`tools/registry.py`,`discover_builtin_tools()` AST 掃 `tools/*.py` 自動載入 `registry.register(...)`)／Skill(純 md，frontmatter `toolsets:` 可啟用 toolset)／MCP(`register_mcp_servers()`)。三路：
      - **α 原生 tool（前人推薦）**：寫 `tools/missive_tool.py`+`registry.register(...)`、skill frontmatter `toolsets:[missive]`。工時 ~1d，可複製給其他 3 bridge、對應 ADR-0020「每專案=1 toolset」。**代價：改 CK_Hermes repo → 需 commit + rebuild image 才上線。**
      - **β MCP server**：`config.yaml` `mcp_servers:` + stdio 包 `query.py`（掛 bind volume `/opt/data`）。**免 rebuild image**（只加 config+script+重啟 gateway），但較非標準、MCP wire 學習成本。
      - γ inline（純 prompt 哄內建 tool）＝現況 ~50-75%，不穩。
    - **權衡**：α 乾淨可複製、為平臺標準，但需 rebuild image（fork 部署）｜β 免 rebuild、config-only，但非標準。
    - **2026-06-03 β spike 實測 → 負向/不成立（已還原）**：實作 MCP server `skills/ck-missive-bridge/mcp_server.py`（fastmcp 薄包 query.py）+ root config.yaml `mcp_servers.missive` + 重啟 gateway。
      - ✅ **MCP 基礎設施成立**：`missive_query` 成功註冊、出現在 /v1 agent 工具清單（**免 fork、免 rebuild**，hermes MCP 機制可用）。
      - ❌ **但「真 tool → 確定性 dispatch」未成立、甚至更糟**：把 meta SOUL 指向 `missive_query` 後，3/3 probe 都**把 tool call 寫成文字**（`{"name":"missive_query",...}` as text）或宣告即停，且夾雜亂碼 token（`ilorc`/`incontri la regola`/`letal`）+ 简体。對比同問題 baseline `terminal` **3/3 真 dispatch**（回正確 1,819）。
      - **∴ 關鍵結論**：dispatch 不穩的瓶頸＝**模型/gateway 發 structured tool_call 的可靠度**（groq llama-3.3-70b 對自訂 MCP tool 比對熟悉的 baseline `terminal` **更不穩**），**非 terminal-vs-真tool 的差別**。**這同時預示 α（同樣靠模型發 tool_call）不會解決問題** → **暫不投入 α**。
      - 已還原 baseline（SOUL `.bak.20260603` / config `.bak.20260603-pre-mcp`），gateway 重啟回 terminal 3/3 GO 狀態。`mcp_server.py` 保留（無 config 即 inert）供未來參考。
    - **dispatch 可靠度真正待解方向（重訂）**：① 強制 `tool_choice`（要求 API 層強制發 tool call，非靠 prompt）；② 換 tool-calling 更穩的模型；③ gateway 層 post-process「寫成文字的 tool call」轉真執行。三者皆屬 hermes runtime/fork 層，非 SOUL/config 可解。在此之前 dispatch 維持現況（terminal ~50-75%、GO + 失敗重試）。
- **S3 Meta 統整能力**：定義並接通「Meta 讀各域意識體成長摘要」的管道（先 Missive：讀坤哥 Memory Wiki 摘要 → Meta 跨域 briefing）。
- **S4 殘留收尾（非阻斷）**：dispatch 穩定度（groq 偶簡體/偶不執行）、延遲（~145-175s，架構性）、Telegram token。屬既有 GO 殘留，獨立處理。
- **S5 同步既有文件**：更新 `D:\CKProject\CLAUDE.md`（已部分同步 6/2 GO）補本 ADR 架構連結；更新 ADR REGISTRY。

---

## 8. 整合的既有 ADR（FQID，避免裸號碰撞）

本 ADR **收斂/對齊** 而非取代：
- `CK_Missive#0023`（坤哥意識體本體）、`CK_Missive#0022`（成長引擎）、`CK_Missive#0031`（平臺入口）—— **引用為既定事實**。
- `CK_AaaP#0020`（Hermes 控制面/介面定位）—— **本 ADR 為其在「多意識體聯邦」維度的延伸/加冠**。
- `CK_Missive#0020`（Hermes 終局角色，proposed）—— **本 ADR 一併定案**：Hermes 終局 = 介面/控制面 + meta 為 AaaP 大腦。
- `CK_PileMgmt#0008`（責任邊界，proposed）—— **對齊**：本地意圖/業務在各平臺後端，Hermes 不持業務。

---

## 9. 後果

**正面**：
- 架構零矛盾、九成已建（坤哥/入口/成長引擎/control plane 皆現成）。
- 各平臺意識體自主成長，對各專案有意義；Meta 為 AaaP 大腦統整全局。
- 不需 fork（拒絕乙）、不加答案延遲、複用既有 profile/bridge。
- 終結「Hermes 終局角色 / 意識體歸屬」的長期漂浮與多 session 誤判。

**負面 / 風險**：
- Meta 跨平臺統整（S3）的管道為新增能力，需設計與驗證。
- domain profile 作為「介面門面」而非意識體，需文件持續正名以防未來再混淆。
- 各新平臺要「比照坤哥蓋意識體」有實作成本（屬各平臺 session）。

---

## 10. 待確認 / 待辦

- [ ] 使用者確認本整合定調（§2 核心原則）。
- [ ] promote 為正式 `CK_AaaP#NNNN`（需 CK_AaaP session）。
- [ ] S1 meta SOUL 語意對齊（需 CK_Hermes 動 production SOUL，先示明 + 備份）。
- [ ] S3 Meta 統整管道設計。
- [ ] 更新 ADR REGISTRY + CLAUDE.md 架構連結。
