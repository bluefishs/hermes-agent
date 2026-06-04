# Hermes UI(:9119) 與前後端整合檢視 — 2026-06-03

> 狀態：實機檢視報告（本 session live 探測，唯讀為主）。
> 觸發：使用者要求檢視 `http://localhost:9119/sessions` 與前端服務對應整合。
> 關聯：[[feedback_hermes_active_profile_before_edit]]、[`CROSS_SESSION_NEXT_3.md`](CROSS_SESSION_NEXT_3.md)、[`adr-ck-005-dispatch-tool-choice-forcing.md`](adr-ck-005-dispatch-tool-choice-forcing.md)

---

## 0. 三前端入口架構（實機確認）

| 入口 | 容器 | 啟動 | 角色 | 認證 |
|---|---|---|---|---|
| **:9119** dashboard | `ck-hermes-web` | `cli.py dashboard --host 0.0.0.0 --port 9119 --insecure` | **管理/觀測 SPA**（sessions/agents/routines 檢視） | SPA 注入 `window.__HERMES_SESSION_TOKEN__`，前端打同 container `/api/*`（Bearer） |
| **:8642** gateway | `ck-hermes-gateway` | OpenAI-compat API | **對話/接入面**（`/v1` chat、Telegram、外部 client） | `/health` 公開；`/v1/*` 需 API key（401） |
| **:3010** open-webui | `ck-open-webui` | open-webui:main | **另一 chat 前端** | open-webui 自管 |

- :9119 SPA shell（649B）= client-side routing：`/`、`/sessions`、`/health` 皆回同一 SPA，由前端 router 解析。
- web_dist = `/opt/hermes/hermes_cli/web_dist`；`HERMES_HOME=/opt/data`。
- `--insecure` flag：dashboard 以非 TLS + 注入 session token 模式跑（本機 127.0.0.1:9119 綁定，非公網）。

---

## 1. dashboard 後端 API 對應（帶注入 token 實測）

| endpoint | 帶 token 結果 | 判讀 |
|---|---|---|
| `/api/sessions` | ✅ 200 `application/json`（20 筆真資料） | **唯一確認的真 JSON API** |
| `/api/health` / `/api/agents` / `/api/routines` | ⚠️ 200 但回 **SPA HTML**（catch-all） | 該 JSON endpoint **未實作或路徑不同** → 前端對應功能可能空轉 |
| `/api/profiles` | ⚠️ **timeout（>10s）** | 掛起或重操作，需查 |
| 未帶 token | 401 | 認證生效，但 **無 `WWW-Authenticate` header**（client 無法協商，僅硬擋） |

`/api/sessions` 物件欄位豐富：`id/source/model/model_config/system_prompt/started_at/ended_at/last_active/message_count/tool_call_count/input_tokens/output_tokens/billing_provider/billing_base_url/estimated_cost_usd/title/preview/handoff_state/is_active …`

---

## 2. 🔴 A 級發現：`/v1` 主模型實為 ollama qwen，非 groq（改錯檔重演）

### 2.1 證據鏈
- `active_profile = meta`。
- **meta profile** `config.yaml` 主模型 = `qwen2.5:7b-ctx64k` @ `http://ck-ollama:11434/v1`（fallback 才是 groq `llama-3.1-8b-instant`）。
- **root** `config.yaml` 主模型 = groq `llama-3.3-70b-versatile` @ `api.groq.com` —— **但 active=meta，root config 對 `/v1` 不生效**。
- gateway env：`HERMES_MODEL=qwen2.5:7b-ctx64k`、`OPENAI_BASE_URL=http://ck-ollama:11434/v1`（也指向 ollama）。
- **20/20 session（含今日 6/3）`billing_base_url=http://ck-ollama:11434/v1`、`model=qwen2.5:7b-ctx64k`、provider=custom** —— 含有 `tool_call_count>0` 者，主路徑全程 ollama，連 groq fallback 都未觸發。

### 2.2 結論（高信心）
**`/v1`（active=meta）的實際主模型一直是本地 ollama qwen2.5:7b；6/2「config 主模型切 groq」改在 root config，與當初改錯 SOUL 同一陷阱——對 active=meta 的 `/v1` 從未生效。**

### 2.3 連鎖影響（顛覆既有文件前提）
1. CLAUDE.md / NEXT_3「6/2 起 gateway 主模型 = groq llama-3.3-70b」對 `/v1` **不成立**。
2. 6/2 GO 的 terminal dispatch（~50-75%）其實是 **qwen 達成**的 → **反證**「qwen tool-use 太弱無法 dispatch、改 groq 才通」的論述。
3. **ADR-CK-005「測 groq tool_choice 4/7」受測模型＝qwen，已坐實誤標**：tool_choice patch 改 `run_agent.py`（不改 model）；今日 9 session（含 spike 7 樣本，tool_call 1~5）`billing` 全 ck-ollama qwen、**0 筆 groq**；meta config 主模型自 5/22 未動。∴ 該 ADR 證明的是「**qwen2.5:7b** 對強制 tool_choice 仍 4/7 吐文字」，**groq 70b 從未被測** → 「①對 groq 無效」**不成立**，①待真 groq 上重測。S2.5 β（MCP）同理為 qwen 表現。

### 2.3.5 config 檔差異坐實（查證證據）
- `root config.yaml`（今日 07:16、2.2KB、有 `.bak.20260602-pre-groq`/`.bak.20260603-pre-mcp`）：主模型 groq `llama-3.3-70b`、toolsets core/code。
- `meta profile config.yaml`（**最後修改 5/22**、8.4KB）：主模型 qwen `2.5:7b`、fallback groq `llama-3.1-8b-instant`、完整 agent/terminal/toolsets 設定。
- 兩者完全不同檔；6/2~6/3 全部 config 改動打在 root，meta（=/v1 實載）自 5/22 凍結 → **groq 對 /v1 從未生效，鐵證確立**。

### 2.4 待使用者決策（不 blind 改 — 涉行為/成本/需重測）
- **選項甲（查證後價值上升）**：把 meta profile config 主模型改 groq `llama-3.3-70b`（對齊 6/2 本意）→ 需重啟 gateway（中斷數秒）+ A/B 重測 dispatch + 重評 ADR-CK-005 + groq API 成本。**為何價值上升**：groq 70b tool-use ≫ qwen 7b，**dispatch 很可能本就大幅改善**，使 ①tool_choice / ③gateway post-process **皆可能變不必要**——這是「先查證」後浮現、最低後悔的單一行動（改 1 檔 + 重啟 + 跑 7 樣本即可定論）。
- **選項乙**：確認 qwen 主模型即現狀夠用（6/2 GO 本就 qwen 達成）→ **修正文件敘述**（移除「主模型 groq」誤述），groq 留作 fallback。成本零、行為不變，但 dispatch 維持 ~50-75%。
- **共通**：無論甲乙，**dashboard `model` 欄顯示 = request 標籤/base client，非實際 provider 真相**（真相在 `billing_*` 欄）——前端應以 billing 欄為準，避免誤導。
- **建議**：傾向**選項甲**——它同時驗證「groq 70b 是否解決 dispatch」這個從未測過的核心假設，且可逆（備份 meta config + 失敗即還原）。

### 2.5 🔴 選項甲實測結果（2026-06-04，已執行+還原）—— groq 70b 免費 tier 不可行

授權後執行選項甲（meta config 主模型 qwen→groq `llama-3.3-70b`、備份 `config.yaml.bak.20260603-pre-groq70b`、重啟 gateway）：

- ✅ **config 生效、實際真走 groq**：新 session `model=llama-3.3-70b-versatile`；**決定性證據＝ck-ollama 模型清單只有 qwen/gemma/nomic、無 70b**，故 model=70b 的請求成功回答必經 groq.com（非本地）。
- ✅ **附帶修正**：`billing_base_url` 欄顯示 ck-ollama 但實走 groq → 證明該欄是 `OPENAI_BASE_URL` env 回顯、**非實際 provider**（先前用它佐證「全走 ollama」的證據作廢；A 級結論改靠 config 檔事實+model 欄，仍成立）。
- 🔴 **決定性失敗＝groq 免費 tier TPM 牆**：首次成功（65s）後連 5 次 **502**，gateway log 鐵證：
  ```
  HTTP 413: Request too large for model llama-3.3-70b-versatile
  service tier on_demand, TPM Limit 12,000, Requested 20,427
  ```
  hermes 每 /v1 請求 ≈ **20,427 token**（SOUL+27 工具 schema+7 skill snapshot 固定開銷）> groq 免費 tier **12,000 TPM** → 單次即 413。首次成功僅因 TPM 視窗剛重置擠進去。
- **∴ 選項甲在不升級 groq 付費 tier 下不可行**。這解釋了「qwen 一直留主模型」的隱藏合理性：**qwen 本地無 TPM 限制、吃得下 20k token**。
- ✅ **已還原**：meta config `cp .bak.20260603-pre-groq70b` 回 qwen（md5 一致）+ 重啟 gateway + `/v1` 確認不再 502；`query.py agent_query` 端到端複驗 **1821 筆 GO**。

**修正後 dispatch 方向（三條全有硬約束）**：
| 方向 | 狀態 |
|---|---|
| ① tool_choice 強制 | 受測實為 qwen（非 groq）；真 groq 70b **被 TPM 牆擋**，無法在免費 tier 驗證 |
| 切 groq 70b 主模型 | ❌ 免費 tier TPM 12k < 20k／請求；需 **付費 tier** 或 **削 prompt 至 <12k** |
| ③ gateway post-process | model-agnostic，**不受 TPM 影響** → 在 qwen 上仍是最務實首選 |
| 削 hermes 每請求 prompt（20k→<12k） | **2026-06-04 讀碼+量測證實「廉價不可行」，見 §2.6** |

---

## 2.6 🟡 削 prompt 可行性 —— 讀碼+量測定論（2026-06-04，唯讀，未動 production）

> 觸發：覆盤建議「削每請求 prompt<12k」同時解延遲與 groq TPM 牆，列為最高槓桿。實際讀碼 + 量測 live session 檔後**下修**。

### 2.6.1 推翻 CLAUDE.md「27 工具硬編、config 不控制、需 fork」
- **config 確實可控**（讀碼 `tools_config.py:1046 _get_platform_tools`）：`/v1` 走 `platform_toolsets.api_server`（meta config 未設→預設 `hermes-api-server`），可由 `platform_toolsets.api_server`（白名單）或 `agent.disabled_toolsets`（黑名單）裁剪，**無需 fork**。`platform_toolsets.api_server` 只 scope /v1（cron/telegram/cli 各走自己預設）。
- ∴ CLAUDE.md「toolset 縮減無效＝硬編、config 不控制、需 fork」**誤述**，本節更正。

### 2.6.2 但量測證明「削到 <12k」廉價不可行（live session 檔精算）
量測最新 `/v1` session 檔（`session_api-*.json` 的 `system_prompt` + `tools` 欄，即真正送 LLM 的內容）：

| 項 | chars | ~tokens | 佔比 |
|---|---|---|---|
| system_prompt（SOUL + skill snapshot）| 19,304 | **4,826** | 24% |
| tools schema（**27 工具**，非 38）| 46,293 | **11,573** | 57% |
| message/overhead（推算）| — | ~4,000 | 19% |
| **全請求** | — | **~20,427**（對齊 6/4 groq log）| 100% |

- 工具成本**平均分布**（~430 tok/工具），非集中於少數大工具。
- **最低風險削減＝移 `browser`(10)+`vision`(1)+`image_gen`(1)＝12 個 /v1 未用工具**（保留 terminal/skills/file/memory，dispatch 路徑完整）：實測僅省 **1,942 tok（~10%）→ 全請求 ~18,457，仍遠超 12k**。
- 要破 12k 須砍到 **≤7 工具 + 削 system_prompt（SOUL/skill snapshot）**→ **損 meta 大腦通用能力**，違「介面非業務但仍需跨域問答」定位。

### 2.6.3 決議（依「排斥分散虛功」準則）
- **不為 ~10% 延遲 churn production**（移 12 工具不解 groq、僅微降延遲，CP 值低）；此 trim 留作**隨時可選的延遲微調**（`agent.disabled_toolsets:[browser,vision,image_gen]`，純減法、零能力損、可逆）。
- **「削 prompt 解 groq 免費 tier」正式下修為不可行**（須損能力）；groq 路仍須**付費 tier**。
- **dispatch 改善維持 ③ gateway post-process 首選**（model-agnostic、不依賴 prompt 大小）。
- 延遲（~145-175s）真正大頭＝gateway 每請求**重建 AIAgent**（架構性），非 prompt 大小；削 prompt 對延遲僅邊際。

---

## 3. 其他整合議題

- **B. dashboard `model` 欄 + `billing_*` 欄皆非實際 provider（議題升級）**：`model` 欄＝config 主模型 snapshot；`billing_base_url` 欄＝`OPENAI_BASE_URL` env 回顯（固定 ck-ollama）。**兩者都不反映實際打哪個 provider**——判真實 provider 須交叉「model 名 vs ollama 模型清單」（如 70b 不在 ollama → 必走 groq）。UI 建議併呈真實 endpoint。
- **C. ~~/api/agents、/api/routines 回 catch-all~~ → 撤回（非 bug，2026-06-04 複驗）**：根因＝**探測用錯 endpoint 名**。真實路由健全且全 200 JSON：`/api/skills`(25KB)、`/api/cron/jobs`、`/api/tools/toolsets`、`/api/status`、`/api/model/info`、`/api/profiles`。dashboard 前後端對應**健全**（前端用正確 endpoint）。
- **D. ~~/api/profiles timeout~~ → 撤回（暫態）**：複驗 `/api/profiles` 200 JSON(1.2KB)；先前 timeout 屬當時 gateway busy 暫態，非 handler bug。
- **附帶觀察：`/api/cron/jobs` 回 `[]`（空）** → 無 active cron job，呼應 S3 §1.2「daily-awakening 停擺」（meta 22:30 cron 未註冊）→ S3 段 C 接通時需一併重啟 cron。
- **E. 401 無 `WWW-Authenticate`**：純硬擋，client 無協商資訊（dashboard 內部用注入 token 故無感，但非標準）。
- **F. `cli.py` 直跑 `No module named yaml`**：印證 ADR-CK-002 venv/PYTHONPATH quirk（entrypoint 正常啟動的服務不受影響，僅手動 `docker exec python3 cli.py` 會中招 → 排障時須走 venv）。
- **G. session token 每次 dashboard 重啟更換**：本次抓到的 token 為當前實例，重啟後失效（屬正常設計）。

---

## 4. 安全/守則與本輪實際處置（2026-06-04 更新為實況）
- §0–§1 檢視：唯讀探測（`/api/*` GET）。
- §2.5 選項甲：經使用者授權執行 config 變更（meta 主模型 qwen→groq）+ 重啟 gateway → 實測 groq 免費 tier TPM 牆不可行 → **已還原 qwen（md5 一致）+ 重啟 + 端到端複驗 1821 筆 GO**，可逆性完整保全。
- §3 議題 C/D 複驗為非 bug（探測用錯名 / busy 暫態），dashboard 前後端健全。
- **容器與文件一致**：active=meta、meta config=qwen2.5:7b、映像 v2026.5.22、備份齊全（meta config `.bak.20260603-pre-groq70b`、query.py `.bak.20260603-pre-s3b`）。baseline GO 維持。
