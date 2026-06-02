# Hermes 對話入口 skill dispatching 修復計畫

> 2026-05-31 | 狀態：**核心 live test 確認** = agent 有全部工具（35 個，含 terminal/skill_view/execute_code）且能執行，但**不照協定跑 `query.py`，改亂猜檔案路徑捏造「公文=0」**（live：154s/简中/假設為零；真實 1809）。非認證/SKILL.md/snapshot/模型/toolset。
> 關聯記憶：`project_hermes_baseline_go_nogo_20260530.md`
> baseline GO/NO-GO：🔴 NO-GO → 真正修法 = **方案 S：SOUL.md 內建 always-on 指示「查公文必跑 `python3 …/query.py agent_query`」+ 強制繁中**（agent 已證能跑 terminal，只缺指示）。改後須 live 驗回 1809。

---

## ✅✅ GO（2026-06-02 端到端打通並 live 驗證，supersede 全文）

**人機完整鏈路真活：** `/v1` 對話「現在系統裡公文總共有幾份？」→ agent 真呼叫 `terminal: query.py agent_query --question "現在系統裡公文總共有幾份？"` → Missive 回 `success:true / 1,817 筆（收文 1257 + 發文 560）` → agent 繁中忠實轉述「**1,817 筆公文**…」。與直接 query.py 的 ground truth **完全一致**，無捏造/無簡體/無反問。transcript 親見（`profiles/meta/sessions/session_api-*.json`）。

**兩端各修一處，合起來才通：**
- **CK_Hermes 端**（本 session）：① `config.yaml` 主模型切 groq `llama-3.3-70b-versatile`；② `profiles/meta/SOUL.md` 加「業務查詢強制規則」。→ agent 從「亂猜路徑/捏造」變成「正確 dispatch + 忠實轉述」。
- **CK_Missive 端**（用戶於 CK_Missive session 修）：Missive 後端容器 `OLLAMA_BASE_URL` `localhost:11434`→`host.docker.internal:11434`（容器內 localhost 指向自己，連不到宿主的 ck-ollama；改後 embedding 768D + ollama 生成 fallback 都通）。→ query.py 從「無法生成查詢向量/通用建議無數字」變成「回確切 1817 筆」。

**殘留（非阻斷）**：① `/v1` 對話延遲 ~145–175s；② groq 偶洩簡體字/偶把指令寫成文字不執行（~1/4，prompt 哄 tool-use 本質限制）；③ 確定性升級（選配）：把 ck-missive-bridge 註冊成 agent 可直接呼叫 tool；④ Telegram token `8606583690` 失效待換（2026-06-02 用戶決定暫緩）。

### 延遲根因調查（2026-06-02，已實測，結論：非 config 可解）
- **groq 本身很快**：容器內直打 groq `llama-3.3-70b`（帶 UA）= **2.9s / 200**；gateway resolved model 確為 groq（`_resolve_gateway_model()`=`llama-3.3-70b-versatile`、base_url=groq，config.yaml 勝過 env 的 `HERMES_MODEL=qwen`）。
- **瓶頸 = gateway 每請求開銷**：極簡 prompt（輸出 2 字、不呼叫工具）的 `/v1` 仍花 **30s**、`prompt_tokens=15708`。那 ~27s 是 **api_server 每個請求重建 AIAgent + 組系統提示（27 個 baseline 工具 schema + 7 skill snapshot + SOUL）+ session/memory 設定** 的固定成本，與 groq 推論（2.9s）無關。
- **toolset 縮減無效**：那 27 工具（含 browser_*/image/vision）是 AIAgent **硬編 baseline**，`config.yaml` 的 `platform_toolsets.api_server` 與 `toolsets.disabled` **都不控制它**（實測改後 session 仍 27 工具、prompt_tokens 不變）→ 已還原該無效設定。
- **∴ 真要降延遲需 fork 程式碼改動**（agent 實例復用 / lazy 載入 skill snapshot / 精簡 baseline 工具）+ 重建 image，非 runtime config；或後端側把統計類查詢走 get_statistics 輕路徑（CK_Missive，省 query.py 那段 4→43s 變異）。延遲屬「可接受但待工程優化」，非阻斷。

---

## 🟢 過程定案（2026-06-02，端到端打通前的根因釐清，保留供覆盤）

**真正根因（推翻所有先前版本，含 零之零 的「SOUL 不進 /v1」）= 我一直在改錯檔。**
- `active_profile` = **meta**。agent 載入的 SOUL 是 **`/opt/data/profiles/meta/SOUL.md`**，不是我先前狂改的 root `/opt/data/SOUL.md`（兩者是不同檔，內容原本相同）。改 root SOUL 當然對 `/v1` 無效——不是「SOUL 不進 /v1」，是**改錯位置**。改 **meta profile SOUL** 後，token 立刻變化、行為立刻改變。
- 證據：session transcript 的 `system_prompt` 含 SOUL 標記「主腦」但不含我的 root 編輯 → 確認讀的是 meta SOUL。

**修法（CK_Hermes 端，已實作並 live 驗證有效）= 兩項 config/內容變更：**
1. **`config.yaml` 主模型切 groq `llama-3.3-70b-versatile`**（qwen2.5:7b 太弱：給對指令仍把 `--question` 填 SQL、或捏造數字）。備份 `config.yaml.bak.20260602-pre-groq`。
2. **`profiles/meta/SOUL.md` 加「業務查詢強制規則」**（凌駕導師人格）：第一動作用 `terminal` 跑 `python3 /opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "<原始中文問句>"`；硬性規定 ① 真正發 tool call 不可寫成 code block ② `--question` 用雙引號包中文原問、禁 SQL ③ 失敗誠實回報、無數字不捏造。備份 `profiles/meta/SOUL.md.bak.20260602`。

**live 驗證（4 次 /v1 真實對話，親見 transcript）**：
- agent **已能正確 dispatch**：呼叫 `terminal` → `query.py agent_query --question "目前有幾份公文"`（中文原問、正確引號、非 SQL、真 tool call）。
- agent **已能誠實回報後端結果**：query.py 回 `success:false / 無法生成查詢向量` 時，agent 回「目前查詢失敗，原因：…」**不再捏造數字**（先前會捏 0/423/456）。
- 偶發不穩：groq 仍 ~1/4 機率把指令寫成文字不執行、或洩漏簡體字——已加規則緩解，但**非 100% 確定性**（prompt 哄 tool-use 的本質限制）。

**∴ 機制這側（CK_Hermes）= 修通**（正確 dispatch + 忠實回報）。**端到端仍拿不到正確數字的根因 = CK_Missive 後端**：query.py 雖成功執行，但 `data.answer` 降級——時而通用建議無數字、時而 `無法生成查詢向量（Ollama embedding 服務）`。屬 **CK_Missive session**（疑與 `ck_missive_ollama_dev` 容器 Created 未啟動有關，待查）。

**殘留（非 CK_Hermes 範圍或選配）**：
1. **CK_Missive 後端**：修 embedding/生成降級，讓 get_statistics 類查詢回確切數字（不然 Hermes 再準也只能誠實回報「後端查詢失敗」）。
2. **確定性升級（選配，CK_Hermes）**：把 ck-missive-bridge 註冊成 agent **可直接呼叫的 tool**（現 `skill_view` 的 `available_skills` 只有 bundled、不含 ck-*），可免去靠 prompt 哄 terminal 的不穩定。
3. **Telegram token** `8606583690` 失效 → 更新 `hermes-stack/.env` + `/platform resume telegram`。
4. **模型成本/簡體**：groq 有 API 成本且偶洩簡體；若要回 qwen 省成本，dispatch 穩定度會下降。

> ⚠️ 教訓（最關鍵）：**改任何 Hermes 設定前，先確認 `active_profile` 並改「該 profile 底下」的檔**。本案橫跨多 session 反覆誤判，全因一直改 root 檔而 active 是 meta profile。驗證方式：看 session transcript 的 `system_prompt` 實際內容，或 `cat /opt/data/active_profile`。

---

## 零之零、★★★★ 2026-06-01 LIVE 實證（⚠️ 本節 A「SOUL 不進 /v1」結論已被上方 2026-06-02 定案更正：真相是改錯檔，非不載入）

> 2026-06-01 用戶授權「優先恢復 Hermes agent 功能」後，於 production gateway 實打 `/v1/chat/completions`（model=`meta`，API_SERVER_KEY 真實認證）逐步驗證，**親見每次完整 stdout 與 token 計數**。結論推翻本文件先前「方案 S 改 SOUL 即可修 /v1」的核心假設。

**A. 方案 S（改 SOUL.md）對 `/v1` 路徑完全無效——已 live 證偽並回滾**
- 改 SOUL.md 加約 600 字「業務查詢強制規則」後，重啟 gateway，`/v1` 回應的 `prompt_tokens` **始終 = 14754**（與改前一字不差）→ **SOUL.md 根本沒進 `/v1` 的 prompt**。
- 源碼確認（`gateway/platforms/api_server.py:1065-1078`）：`/v1/chat/completions` 的 `system_prompt` **只取請求 messages 裡 role=system 的內容**，沒帶 SOUL；agent 核心只另加 skill snapshot。**SOUL 只作用於 SOUL-driven 路徑（Telegram/CLI/native），不作用於 `/v1`（= AaaP 前端 / Open WebUI / OpenAI-compat 客戶端走的路徑）。**
- ∴ 先前「SOUL 在所有入口 always-on」是**錯的**。SOUL 編輯已**回滾**至 `SOUL.md.bak.20260601`（disk 已還原；in-memory 仍是重啟時載入的改版，但 /v1 不用、Telegram 已壞，無實效）。

**B. 真正能影響 `/v1` 行為的管道 = 請求帶 `role=system` message——已驗證生效但揭露模型太弱**
- 帶強指令 system message（要求「第一動作必跑 `python3 .../query.py agent_query`、禁反問、禁 SQL、繁中」）後，`prompt_tokens` 跳到 **30430**（system 確實進 prompt）。
- 但 qwen2.5:7b 回應：**(1) 回简体中文**（無視繁中指令）；**(2) 捏造「423 份」**（既非真實，也非工具回傳值）。→ **模型 instruction-following + tool-use 太弱**，給了正確管道仍捏造。

**C. 第二個獨立故障：Missive 後端 LLM 生成層降級（與 Hermes 無關）**
- 2026-06-01 手動跑 `query.py agent_query`（ground truth，`tools_used:["get_statistics"]`、18.7s）回傳的 `answer` **完全沒有數字**：「根據上述分析…1. 進行公文清理…2. 實施公文版本控制…」（通用建議）。
- ∴ 即使 Hermes 完美 dispatch，Missive 後端當下也回不出數字（生成層降級，3-tier Groq→NVIDIA→Ollama→canned 落到通用回應）。「1809」是先前健康時刻的值，現在連 ground truth 都拿不到數。

**D. 第三個故障：Telegram bot token 失效**
- gateway log：`telegram.error.InvalidToken: token 8606583690:*** rejected` → Telegram 平台已 `paused after 10 consecutive failures`。需更新 token 後 `/platform resume telegram`。

**E. skill_view registry 與 snapshot 不一致（佐證）**
- gateway log：agent 有呼叫 `skill_view('missive-agent')`（猜錯名）→ `available_skills` 清單**只有 bundled skills**（dogfood/yuanbao/claude-code/codex/hermes-agent/opencode/architecture-diagram/ascii-art…）、**不含任何 ck-*-bridge**。但 `.skills_prompt_snapshot.json` 含 ck-missive-bridge×4。→ **兩套登錄表不一致**：agent prompt 索引看得到 ck-missive-bridge，但 `skill_view` 工具載不到它。

### ∴ 修法重新定位（三條獨立戰線，方案 S 出局）
1. **`/v1` 行為（AaaP 前端）**：靠請求 `role=system` 或 server-side 注入（方案 C：改 `api_server.py` 為無 system message 時注入預設業務指令），**且必須搭配 tool-use 夠強的模型**（qwen2.5:7b 不行）。最低成本驗證路徑＝先讓 AaaP 前端送強 system prompt + 暫切 groq llama-3.3-70b 實測。
2. **Missive 後端生成降級**：屬 CK_Missive session，查 `ai_connector.py` 3-tier provider 當下額度/連線，讓 get_statistics 類查詢直接回統計數而非走生成。
3. **Telegram token**：更新 `hermes-stack/.env` 的 Telegram token + resume。
4. **skill_view registry**：若要走「agent 自主 skill_view→query.py」路線，須查為何 ck-* 沒進 `skill_view` 的 available_skills（registry 來源 ≠ snapshot 來源）。

> ⚠️ 教訓追加：**「SOUL always-on 於所有入口」是未經 live 驗的推論**；用 `prompt_tokens` 不變一眼證偽。改 production 設定後必看「token/實際 prompt 是否變」再宣稱生效。本次因有逐步看 stdout + token，沒有重蹈捏造。

---

## 零、★★★ 決定性核心（2026-05-31 最終，源碼鐵證，supersede 以下全部舊診斷）

**症狀**：使用者自然語言問「公文總數」→ agent 幻覺 `from hermes_tools import terminal` 不執行 / 回「找不到工具」。

**根因（2026-05-31 live test 確認）= agent 有全部工具且能執行，但不照 skill 協定查 Missive，改亂猜檔案路徑。** 不是內容/部署/認證/模型/toolset。

**工具層全部到位（運行時實測）**：`/v1` 跑 `hermes-api-server` 平台 toolset = **35 個工具，含 `terminal`/`skill_view`/`execute_code`（全 True）**。`_HERMES_CORE_TOOLS` baseline 也含這些。config 的 `toolsets.enabled:[core,code]` 兩名**解析成空**（`resolve_toolset('core')=[] 'code'=[]`，`web` 正常回 2）→ 那行其實沒生效，但平台 toolset 已給足工具，故無影響。agent 知道 ck-missive-bridge 存在（snapshot 一行描述 + skill_view 在手 → `has_skills_tools=True` 注入 skill 索引）。

**live 決定性證據（容器內 python 直打 `/v1/chat/completions`，model=`meta`，親見完整 stdout）**：
```
問「目前系統總共有幾份公文？」→ HTTP 200 / 154.1s / 171 字
回應（简体中文，違反 SOUL）：「…当前目录 /opt/data/missive/logs 下并没有找到包含公文记录的日志文件…我可以假设当前系统中的公文数量为零。」
```
- agent **有用執行工具**（去 `ls` 了 `/opt/data/missive/logs`）→ **terminal/execute_code 能跑、approval gate 沒擋**（排除 approval 假設）。
- 但它**沒呼叫 `skill_view('ck-missive-bridge')`、沒跑 `query.py`** → 改自己亂猜「公文 = log 檔」翻目錄，找不到就捏造「公文=0」。
- 真實答案是 1809 份（直打 API 已證）。agent 既不查 skill 也不走 query.py。

**∴ 確認核心：qwen2.5:7b 拿到 35 工具 + 知道 skill 存在，卻不會「先 skill_view 載入 ck-missive-bridge 再 terminal 跑 query.py」這套協定，而是即興亂查。沒有任何 always-on 指示叫它跑 query.py。**（groq 70b 先前同樣失敗 → 因 SOUL 從沒給指示，非純模型大小。）

### 連帶撤回本文件所有舊結論
- ❌ 認證 401 / SKILL.md 缺範例 / snapshot 過期重啟 / profiles-meta / 「無 skill 載入機制」/ toolset 沒開 → **全非主因或本身有誤**。真相只有一句：**agent 有能力但無指示去跑 query.py，遂亂查。**
- ❌「重啟 gateway 即修好」「複製進 meta」「補 SKILL.md body」→ 對 `/v1` 路徑皆無效（body 不進 prompt、重啟不改行為）。**勿執行。**

### 真正修法（live 確認後收斂為單一首選）
- **★ 方案 S（首選，已被 live 結果支持）**：在 **SOUL.md 內建 always-on 操作指示** —「涉及公文/案件/工程/標案/統計/知識圖譜時，**務必先用 terminal 執行** `python3 /opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "<原問題>"`，把回傳 `data.answer` 轉述；**嚴禁**自己猜檔案路徑或假設數字；全程**繁體中文**」。理由：agent 已證實能跑 terminal，缺的只是「該跑哪條」的明確指示；SOUL 在所有入口（含 `/v1`）always-on。純內容、可回滾。
  - 連帶解 **简体中文** 違反 SOUL（同一段強化繁中）。
- **方案 T（補充，僅 Telegram/Discord/Slack）**：config 加 `channel_skill_bindings`/topic→ck-missive-bridge，讓那些 channel 新 session 直接把 SKILL.md body 注入（agent 連 terminal 範例都從 body 拿）。**不解 `/v1`/Open WebUI/LINE。**
- **方案 C（最重，未來）**：改 `api_server.py:_run_agent` 為 `/v1` 也支援 channel/default skill binding。
- ⚠️ **方案 S 後仍須 live 驗**：改 SOUL 後（可能需新 session 或重啟使系統提示重載）再打一次 `/v1` 問公文總數，**成功標準 = 回 1809、繁中、有跑 query.py**。改 SOUL 前先確認 SOUL 載入時機（per-session 重讀 vs process 啟動快取）。

---

## 零之二、★ SOUL.md 內在矛盾＝缺指示的「機制」（2026-06-01 讀全文鐵證）

> 2026-06-01 直讀 `C:\Users\User1\.hermes\SOUL.md`（= 容器 `/opt/data/SOUL.md`，5621 bytes，mtime 5/22 16:49 → **方案 S 尚未套用**）。發現 NO-GO 不只是「缺指示」，而是 SOUL **同時給了互相打架的指示**，agent 因而即興亂查：

| SOUL 段落 | 原文要旨 | 對 agent 的淨效果 |
|---|---|---|
| 跨 agent 仲裁 #1 | 「公文…的答案以 **Missive 為準**…呼叫 `ck-missive-bridge` 代問」 | ✅ 叫它查 Missive，但**沒給執行指令** |
| 角色定位 | meta「**不直接處理業務**」「不做派工」 | ⚠️ 暗示「別自己算」，卻無替代動作 |
| 可呼叫工具 | 「其他 agent 的 skill **只能間接呼叫**（透過 profile switch 或請使用者轉問）—**你不直接跨越 profile 邊界**」 | 🔴 **直接禁止**它呼叫 ck-missive-bridge |

**∴ 機制定讞**：SOUL 一邊說「呼叫 ck-missive-bridge 代問」、一邊說「你不直接跨越 profile 邊界、skill 只能間接呼叫」→ agent 收到**自相矛盾**的指令，且全程無一條「用 terminal 跑 `python3 scripts/query.py`」的具體執行範例 → 遂幻覺 code／亂猜路徑／捏造 0。這正是 live test 觀察到行為的**根因機制**。

**∴ 方案 S 的精確落點（改 SOUL 三處，純內容、可回滾）**：
1. **語言規則段下方**或**可呼叫工具段**新增 always-on 區塊：「涉及公文/案件/工程/標案/統計/知識圖譜 → **務必先用 terminal 執行** `python3 /opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "<原問題>"`，把回傳 `data.answer` 轉述；**嚴禁**自己猜檔案路徑或假設數字。」
2. **修正矛盾**：把「可呼叫工具」段的「其他 agent 的 skill 只能間接呼叫…你不直接跨越 profile 邊界」改為**明確例外**：「**唯 `ck-missive-bridge`（及其他 ck-*-bridge）為 meta 內建代問工具，得直接以 terminal 執行其 `query.py`**；此非跨 profile 邊界，而是 meta 仲裁業務真相的指定管道。」
3. 「跨 agent 仲裁」段把「呼叫 `ck-missive-bridge` 代問」補上具體指令連結（指向第 1 點）。

> ⚠️ 仍須 live 驗：SOUL 是 system prompt，**可能 per-session 重讀**（fresh `/v1` session 即生效）**或** process 啟動快取（需重啟 gateway）。落地順序：先改 SOUL → 開新 `/v1` session 問公文總數 → 若仍幻覺再 `docker restart ck-hermes-gateway` 後複驗。**成功標準＝回 1809／繁中／有跑 query.py。**

---

## ⚠️ 重大更正（2026-05-31 複查）：前一版「核心議題」診斷錯誤，已撤回
前一版本斷定「skill 不在 active profile(meta) 掃描路徑/snapshot」——**經 python 運行時實測證明錯誤**。teach point：先前基於不完整 `ls`/`find` + 源碼推論，沒實測 `HERMES_HOME` env 就下結論。

### 運行時鐵證（容器內 python 實測，取代所有路徑推論）
```
$ docker exec ck-hermes-gateway python3 -c "from hermes_constants import get_hermes_home,get_skills_dir; print(get_hermes_home()); print(get_skills_dir())"
HERMES_HOME      = /opt/data            ← env 直設，NOT /opt/data/profiles/meta
get_skills_dir() = /opt/data/skills     ← agent 掃 ROOT skills（33 項，含 ck-missive-bridge）
$ docker exec ck-hermes-gateway grep -c ck-missive-bridge /opt/data/.skills_prompt_snapshot.json
2                                        ← agent 讀的 snapshot 確實含 ck-missive-bridge
```
（`active_profile` 檔內容 "meta" 在 `HERMES_HOME` 已設時**不被 get_hermes_home 使用**，只在 env 未設時當警告——故 meta profile 目錄是誤導，agent 根本沒用它。）

## 一、修正後的真實核心議題

**ck-missive-bridge skill 確實在 agent 的掃描目錄(`/opt/data/skills`)與 prompt snapshot 裡（含 2 筆）——agent「看得到」skill。但對話時 agent 仍寫幻覺 code（`from hermes_tools import terminal`）不真正呼叫它。**

→ 根因**不在** skill 部署/註冊（那層是好的），而在以下之一（待重新查證，不臆測）：
1. **模型 tool-calling 能力**：active gateway model 是本地 `qwen2.5:7b`，7b 模型對「該用哪個 skill + 正確呼叫格式」能力弱（最初判斷，繞一圈後回到此）。
2. **skill 呈現方式**：snapshot 雖含 ck-missive-bridge，但 SKILL.md 內容是否清楚告訴 agent「用 `python3 scripts/query.py agent_query`」？agent 卻自創 `hermes_tools.terminal` → 可能 SKILL.md 沒給對呼叫範例，或 hermes 的 skill 執行慣例與 SKILL.md 寫法不符。
3. **groq 切換是否真生效未定**：若 active config = root `/opt/data/config.yaml`（HERMES_HOME=/opt/data 下，這很可能就是 active config），則我先前改 root config 的 groq **其實改對了檔**，但切換後行為沒變 → 需重新確認 gateway 實際載入的 model。

### 仍成立的事實（不受本次更正影響）
| 事實 | 驗證 | 結果 |
|---|---|---|
| skill 腳本手動可跑 | `python3 query.py agent_query` | 回 1809 份公文（真實） |
| 直打 Missive API | X-Service-Token | HTTP 200 真實 |
| agent 對話不呼叫 skill | gateway `/v1/chat/completions` | 幻覺 code，不執行 |
| doc 包已修 | tools.py/tool_spec/SKILL.md | query_sync→query 等已同步 |

### ★ 真正核心議題鎖定（2026-05-31 複查最終，源碼+運行時雙證據）
**SKILL.md 沒教 agent 怎麼執行 skill** → grep `/opt/data/skills/ck-missive-bridge/SKILL.md` 的 `query.py`/`python3`/`scripts/` = **全 0 筆**。SKILL.md 只寫「有哪些 tool、何時用、呼叫規範」與「架構：tools.py 動態註冊」，但**從沒給實際執行指令** `python3 scripts/query.py agent_query --question "..."`。
- agent 讀 snapshot 知道「該查 Missive」(snapshot 含 ck-missive-bridge 4 筆)，但不知怎麼執行 → 自創幻覺 `from hermes_tools import terminal` / `terminal(command='ck-missive-bridge count')`（模組與指令皆不存在）。
- SKILL.md 宣稱的「tools.py register_all 動態註冊 tool」機制在此 hermes 版本**未生效**（若生效 agent 會直接呼叫 tool，而非寫 code）→ 此 hermes 版本是「agent 讀 SKILL.md 後用 terminal tool 跑 scripts」模式，但 SKILL.md 沒寫該跑什麼。
- query.py docstring 本身就說明它「設計給用 file 執行繞過 approval gate」→ 佐證預期用法是 terminal 跑 `python3 scripts/query.py`，只是 SKILL.md 漏寫。

**∴ 真正根因 = SKILL.md 內容缺陷（缺執行指令範例），非部署/profile/模型能力。** 低風險可直接修。

### 待最終確認（修 SKILL.md 前）
1. hermes 此版本 skill 執行確切慣例（agent 用哪個 terminal tool、cwd 是否在 skill 目錄、能否直接 `python3 scripts/query.py`）→ 決定 SKILL.md 範例的精確寫法。
2. tools.py register_all 為何沒生效（hermes 版本是否棄用此機制）→ 決定要不要一併清掉 SKILL.md 的過時「架構」段。

**與模型強弱無關**：root skills 與 meta skills 是不同目錄；agent 只看 active profile(meta) 的 skills。換 groq llama-3.3-70b 也沒用（agent 連 skill 存在都不知）。**這推翻先前「本地模型 tool-calling 不足」初判**——模型是次因，主因是 skill 不在 active profile context。

---

## 二、連帶澄清（清除先前誤判，避免重複）

1. **groq 切換其實改對了檔（再次更正）**：HERMES_HOME=`/opt/data` → active config = `/opt/data/config.yaml`（57 行）。我先前 groq 就改在此檔＝**改對了 active**（不是改到非 active 的 meta profile——那個更正也是錯的）。但已回滾，現 active model = qwen2.5:7b（python 運行時實測確認）。意涵：若當時 groq 重啟有生效，則 groq 70b 也吐幻覺 code → 佐證根因非模型而在 SKILL.md/skill 執行機制；但「當時 groq 是否真重啟生效」未確證（首次 restart 曾報 no such service），故不下定論。
2. **LINE「查詢處理時間較長」同源**：`backend/app/services/integration/line_bot.py:167/224`（`:51` 今日 v6.12 緊急修法）。agent 拿不到資料又慢 → LINE reply-token 窗口超時。skill dispatch 修好後應緩解（但重 RAG 查詢仍可能超 LINE 窗口，需另解）。
3. **已修且為真（不受本議題影響）**：Missive 後端 `/api/ai/agent/query` + X-Service-Token（直打回 1809 份公文真實）；skill 腳本 `query.py agent_query` 手動可跑；doc 包三檔（tools.py/tool_spec.json/SKILL.md）已同步修正（query_sync→query、補 X-Service-Token、timeout→90）。

---

## 三、修法機制（已查源碼，標註已知 vs 待驗證）

### 已查到（親見）
- `hermes` CLI **不在 gateway 容器 PATH**（`hermes: not found`，rc=127）——gateway 以 python module 跑。CLI 操作需 `python -m hermes_cli ...` 或在有 CLI 的環境。
- profile-skill 管理模組：`/opt/hermes/hermes_cli/profile_distribution.py`（`install_distribution`/`update_distribution`/`_copy_dist_payload`/`_count_skills`）+ `profiles.py` + `skills_config.py` + `skills_hub.py`。
- snapshot / skill prompt 相關源碼（親見定位，已更正）：`/opt/hermes/agent/prompt_builder.py`（含 `skills_prompt_snapshot` 字串，agent prompt 組裝處）；另有 `/opt/hermes/tests/agent/test_skill_commands_reload.py` → 暗示存在 **skill reload 機制**（修法線索：可能有不需重啟即可 reload skill 的指令/hook）。⚠️ 先前誤寫 `skills.py`，該檔不存在，已更正。
- gateway 啟動 log `Syncing bundled skills into ~/.hermes/skills/ ...` 證啟動會跑同步，但同步的是 bundled 分類 skill（apple/creative/...），非 ck-* 自訂 bridge skill。

### ❌❌ 已撤回（2026-05-31 host 掛載源實測證偽）：本段「profiles/meta」證據全錯
> 下方原「複查 100% 確認」與「★★ 運行時鐵證」兩段聲稱 `HERMES_HOME=/opt/data/profiles/meta`、`get_skills_dir()=/opt/data/profiles/meta/skills`、「meta/skills 26 項無 ck-*」。
> **經 host 掛載源（`C:\Users\User1\.hermes` = 容器 `/opt/data`）直接實測，全部證偽**：
> - `~/.hermes/profiles/meta/` **目錄根本不存在**（META-SKILLS-NOT-FOUND / META-SNAP-NOT-FOUND）→ 不可能是掃描路徑。
> - 正確的是本文件**頂部「重大更正」段**：`HERMES_HOME=/opt/data`、`get_skills_dir()=/opt/data/skills`、root snapshot 含 ck-missive-bridge ×4。
> - ∴ 方案 A/B 賴以成立的「root skills 不被掃描、需複製進 meta」前提**不成立**，已作廢（見第四節更正）。
> **teach point**：源碼 `get_hermes_home()=base/profiles/<active>` 的推論，被 `HERMES_HOME` env 直設覆蓋；任何 runtime 路徑結論必以 host/容器實測為準，且出現自相矛盾的兩組「鐵證」時應立即停手重驗，不續寫。

### ✅ host 實測校正後的真實狀態（2026-05-31，取代上述作廢段）
| 實測項 | 值 | 意涵 |
|---|---|---|
| live `SKILL.md` 含執行指令 | `query.py`×7、`python3`×5、`scripts/`×7 | **修法已部署到磁碟** |
| `SKILL.md` 改檔時間 | 2026-05-31 13:45 | 今日已改 |
| root `.skills_prompt_snapshot.json` 改檔時間 | **2026-04-30 23:00** | 比 SKILL.md 舊一個月 |
| snapshot 內 `query.py` / `python3 scripts` | **0 / 0** | agent 讀到的仍是**舊版無執行指令**內容 |
| gateway 容器啟動 | 2026-05-24（改 SKILL.md 前） | 改檔後**未重啟**、未觸發 reload |
| `~/.hermes/profiles/meta/` | **不存在** | 推翻所有 meta-profile 假設 |

**∴ 修法已在磁碟（SKILL.md 補了執行範例），但 snapshot 停在 4/30、gateway 自 5/24 未重啟 → agent 仍讀舊 snapshot，故對話仍寫幻覺 code。manifest(mtime+size) 自動重生「並未發生」（SKILL.md 5/31 改、snapshot 仍 4/30）→ 需主動重啟 gateway 強制重生 snapshot。剩餘工作只有「部署生效 + 真實驗證」一步。**

---

## 四、整體性安排（host 實測校正後：方案 A/B/C 前提已作廢，真實只剩一步）

> ❌ 原方案 A/B/C 全建立在「root skills 不被掃描、需複製/安裝進 `profiles/meta/skills`」——該前提已被 host 實測證偽（`profiles/meta/` 不存在）。**root `/opt/data/skills/` 本就是 agent 掃描目錄、snapshot 本就含 ck-missive-bridge，SKILL.md 也已補執行範例。** 唯一缺口是 snapshot 停在 4/30、gateway 自 5/24 未重啟，新 SKILL.md 尚未進 agent prompt。

### ★ 真實修法（單步、低風險）：重啟 gateway 觸發 snapshot 重生
- 前提（已成立，無需再動）：① live SKILL.md 已含 `python3 scripts/query.py agent_query` 範例；② root snapshot 路徑正確、gateway env `HERMES_HOME=/opt/data`、`MISSIVE_API_TOKEN` 已設。
- 步驟（每步看完整 stdout 才算成功）：
  1. 備份 root snapshot：`cp /opt/data/.skills_prompt_snapshot.json{,.bak.20260531}`
  2. 低流量時段重啟：`docker restart ck-hermes-gateway`，等 healthy。
  3. 驗證 snapshot 已重生收錄新內容：`docker exec ck-hermes-gateway grep -c 'query.py' /opt/data/.skills_prompt_snapshot.json` 應 **> 0**（重啟前為 0）。
  4. **真實對話驗證**：打 `/v1/chat/completions` 問「目前系統有幾份公文」→ 成功標準 = agent 真呼叫 ck-missive-bridge 回「1809 份公文」（與直打 API 一致），`tools_used` 非空，**非**幻覺 `from hermes_tools import ...` code。
  5. 失敗則回滾 snapshot 備份 + 查 `prompt_builder.py` 為何未重生（可能 manifest 比對未涵蓋內容變動，或有額外快取層）。
- 完整可貼上指令稿見第五節之二。

### 若步驟 3 重啟後 snapshot 仍未含新內容（次要分支）
- 代表 manifest(mtime+size) 自動重生機制未如預期 → 手動刪除 snapshot 強制重建：`mv /opt/data/.skills_prompt_snapshot.json{,.stale}` 再重啟，讓 `build_skills_system_prompt` 從零重生。
- 或查 `prompt_builder.py` 是否有 in-memory 快取需要 process 重啟（已含在 docker restart）。

---

## 四之二、數據分析（baseline shadow_trace 35 天，已驗證數據）

來源 `shadow-baseline-report.cjs` 讀 `backend/logs/shadow_trace.db`，2026-04-14~05-30，**1097 calls / 成功率 82.5%**。

### 依實際 LLM provider（揭露兩件事）
| provider | calls | 成功率 | p50 | p95 |
|---|---|---|---|---|
| groq | 488 | **99.4%** | 5.8s | 42s |
| nvidia | 128 | **99.2%** | 18s | 58s |
| ollama | 416 | **63.7%** | **52.8s** | 90s(timeout) |
| (unset) | 65 | 43% | 90s | 90s |

- **整體 82.5% 被 ollama 拉低**：ollama 成功率僅 63.7%、p50 52.8s；groq/nvidia 都 99%+。
- **timeout 共 192 次**，集中在 ollama 與 unset。
- **熱門工具**：search_documents(690)、get_statistics(401)、search_entities(337)、search_dispatch_orders(171)——統計類(get_statistics)是高頻且輕量。

### 與核心議題的交叉印證
1. **這份 baseline 全是「Missive 後端 agent 層」的數據**（shadow_trace 記在 Missive backend），證明 **Missive agent 本身是活的、且 groq 路徑健康（99.4%）**——problem 不在 Missive 後端。
2. **本次 dispatching bug 在 Hermes gateway → skill 這一段**，不會出現在這份 Missive-side baseline 裡（gateway 根本沒成功呼叫到 skill，沒產生 trace）。→ 兩層問題分離清楚。
3. **延遲門檻 ADR-0030 #5「P95<8s」**：只有 groq p50 達標(5.8s)、p95(42s)不達標；ollama 完全不達標。**推論：Missive agent 應強制走 groq、統計類查詢走 get_statistics 輕路徑**（這層優化獨立於 Hermes skill 修復）。

## 五、執行前提與本次未執行原因

- production gateway 任何重啟短暫中斷 LINE/Telegram/WebUI，挑低流量時段
- **未 blind 執行重啟**：(a) production gateway 重啟中斷 LINE/Telegram/WebUI，須挑低流量時段；(b) 通道 I/O 多次吞輸出，不在看不到結果時對 production 操作（避免重蹈「改了沒驗證又宣稱成功」）。機制本身已釐清——root SKILL.md 已修、snapshot 停 4/30 待重啟重生，非待查。
- 歸屬：hermes-stack / CK_AaaP profile 管理範疇；建議通道穩定或專屬 session 執行

## 五之二、重啟＋驗證指令稿（低流量時段、專屬 session 貼上；逐段看完整 stdout）

```bash
# ── 0. 操作前快照（可回滾）──────────────────────────
docker exec ck-hermes-gateway sh -c 'cp /opt/data/.skills_prompt_snapshot.json /opt/data/.skills_prompt_snapshot.json.bak.20260531'
# 重啟前基準：snapshot 內 query.py 應為 0（舊版內容）
docker exec ck-hermes-gateway sh -c "grep -c 'query.py' /opt/data/.skills_prompt_snapshot.json"   # 期望 0

# ── 1. 重啟 gateway，等 healthy ──────────────────────
docker restart ck-hermes-gateway
# 輪詢 healthy（最多 ~60s）
for i in $(seq 1 12); do
  s=$(docker inspect -f '{{.State.Health.Status}}' ck-hermes-gateway 2>/dev/null)
  echo "health=$s"; [ "$s" = "healthy" ] && break; sleep 5
done

# ── 2. 驗證 snapshot 已重生收錄新 SKILL.md（含執行指令）──
docker exec ck-hermes-gateway sh -c "grep -c 'query.py' /opt/data/.skills_prompt_snapshot.json"   # 期望 > 0
# 若仍為 0：手動強制重建後再重啟一次
#   docker exec ck-hermes-gateway sh -c 'mv /opt/data/.skills_prompt_snapshot.json /opt/data/.skills_prompt_snapshot.json.stale'
#   docker restart ck-hermes-gateway   # 等 healthy 後重跑本段 grep

# ── 3. 真實對話驗證（成功標準：回 1809、tools_used 非空、非幻覺 code）──
#   API_SERVER_KEY 取自 hermes-stack/.env
curl -s http://localhost:8642/v1/chat/completions \
  -H "Authorization: Bearer $API_SERVER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"hermes-agent","stream":false,"messages":[{"role":"user","content":"目前系統有幾份公文？"}]}' \
  | tee /tmp/dispatch_check.json
#   人工判讀 /tmp/dispatch_check.json：
#   ✅ content 含「1809」或正確份數、且回應提到走 ck-missive-bridge / get_statistics
#   ❌ content 出現 from hermes_tools import / terminal(command=...) / 「没有找到工具」→ 仍未生效，回滾查 prompt_builder

# ── 4.（可選）用 repo 內 probe 一次驗三層 + skill dispatch ──
HERMES_E2E_REAL_STACK=1 python scripts/verify-hermes-stack.py --json
```

回滾：`docker exec ck-hermes-gateway sh -c 'cp /opt/data/.skills_prompt_snapshot.json.bak.20260531 /opt/data/.skills_prompt_snapshot.json' && docker restart ck-hermes-gateway`

> ⚠️ MSYS（Windows Git Bash）下 `docker exec ... /opt/...` 路徑會被改寫，已用 `sh -c '...'` 包裹規避；或在指令前加 `MSYS_NO_PATHCONV=1`。

---

## 六、過程教訓（本次覆盤累積，寫進記憶）

1. 改 hermes 設定前**必先實測 runtime 路徑**（`python3 -c "from hermes_constants import get_hermes_home,get_skills_dir; ..."` 或直接看 host 掛載源），別靠源碼推論——`HERMES_HOME` env 會覆蓋 `active_profile`，本案因此誤判 3 次（root→meta→其實 root）。
1b. **磁碟改了 ≠ 生效**：SKILL.md 改後 snapshot 未自動重生（停在舊 mtime），agent 仍讀舊 prompt。改完務必確認「agent 實際讀到的 snapshot/prompt」已更新，再宣稱修好。
2. **看完整 stdout 結尾且確實成功才寫成功**——本對話多次因截斷/未生效/不完整 ls 誤報，全靠後續真實輸出揭穿（token、0-byte、對話 1809、groq 切換、meta skills 內容）。
3. 有依賴的指令勿塞同一並行批次（一個失敗整批取消）。
4. 中文 grep / 大量 stdout 在此 harness 易被吞；用 docker exec 容器內 grep 導檔、Read host 檔較穩。
5. MSYS 路徑：`docker exec ... /opt/...` 需 `MSYS_NO_PATHCONV=1` 前綴或 `sh -c` 包裹。
