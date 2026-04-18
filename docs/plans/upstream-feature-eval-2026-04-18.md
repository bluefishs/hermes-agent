# Upstream feature evaluation — 2026-04-18

> Scope：三項 upstream 新功能對 CK（Missive-first）工作流的適用性評估
> Decision mode：僅產出建議；任何採用動作走 CK_AaaP runbook（不在本 session 實作）

## 1. `/steer <prompt>` — 跑中注入提示（#12116）

### 是什麼

一個 mid-run 的 slash 指令。使用者在 agent 正在跑 tool 時送 `/steer 改查 2024 年案件`，文字會在**下一次 tool batch 結束**時以 `[USER STEER (injected mid-run, not tool output): ...]` 標記附加到 tool result，模型下一輪 iteration 就會看到。

介於既有 `/queue`（turn 邊界才生效）與硬中斷之間。CLI、Gateway（Telegram/Discord/Slack）、Ink TUI 三面都有。72/72 測試通過。

### 對 CK 的價值

- **高** — Missive KG 查詢經常會陷入「agent 走錯搜尋方向」但使用者不想整輪打斷重跑。/steer 剛好補這個 gap。
- 範例：agent 用 `ezbid` 爬蟲找案件，中途發現該週資料缺失；傳 `/steer 改從 CKMissive KG `contribute` endpoint 取` 可即時導向，不中斷已跑過的 tool traces。

### 風險 / 成本

- **低** — 不改 role alternation、不 invalidate prompt cache。
- 需要的前端支援：Telegram bot（優先）+ Web UI（次要）。Telegram 目前未啟用 token，要等 CK_AaaP 設 `TELEGRAM_BOT_TOKEN` 後才能用。

### 建議

- **採用**。排入 Missive 工作流 runbook：在 CK_AaaP 的 `SOUL.md` / onboarding 文件中加一段「mid-run steering」使用情境
- 不需任何 hermes-agent 側改動

## 2. `execute_code project/strict` mode（#11971）

### 是什麼

`execute_code` tool 從「永遠在 staging tmpdir + `sys.executable`」改為 **預設 `project` mode**：

| | strict（舊行為） | **project（新預設）** |
|---|---|---|
| CWD | staging tmpdir | session 的 `TERMINAL_CWD` |
| Python | `sys.executable` | `VIRTUAL_ENV/bin/python` → `CONDA_PREFIX/bin/python` → fallback |
| 環境 scrubbing | ON | ON（不變） |
| Tool whitelist | ON | ON（不變） |

使用者體驗：`import pandas`、`./data.csv`、`.env` 讀取行為跟 `terminal()` 一致（之前弱模型會來回 flip-flop）。

### 對 CK 的價值

- **中** — CK workflow 對 `execute_code` 用量不算高（主要走 Missive API + skill），但當 agent 要跑臨時 Python 腳本處理 KG 資料時，project mode 可避免「明明 hermes-stack 容器裡有 pandas、`execute_code` 卻說沒有」的混淆。
- 安全性：regression guards 覆蓋 OPENAI/ANTHROPIC/GITHUB token scrubbing 與 tool whitelist；`test_neither_description_uses_sandbox_language` 明確防止 agent 誤信沙箱保護而做出危險行為（commit 39b83f34 回歸測試）。

### 風險 / 成本

- **低-中** — 升 upstream 到 v2026.4.16 時 schema 18 → 19 自動加 `code_execution.mode: project`。hermes-stack 容器內若要切回 strict，只改 config.yaml。
- **但要注意**：ADR-0017 Docker Secrets 實施時，`project` mode 讓 `execute_code` 能存取 session CWD；若該 CWD 掛載了 secret volume，需評估是否切 `strict`。

### 建議

- **預設接受 project mode**（隨 upstream rebase 自動套用）
- 在 ADR-0017 實施時**重評**：如果 Docker Secrets 走 tmpfs + CWD 掛載，需在 config.yaml 切 `code_execution.mode: strict`，或把 secret mount 點移出 `TERMINAL_CWD`
- 對 CK workflow 無需立即改動

## 3. Tool Gateway（ungate + per-tool opt-in）

### 是什麼

Nous Portal 託管的 tool-calling 服務。2026-04 ungate 後採**訂閱制 + per-tool opt-in**。使用者在 Nous Portal 買 subscription 後，以 API key 啟用特定 tools（例如 web search、scraping、code execution），hermes-agent 透過 Tool Gateway protocol 叫用。

### 對 CK 的價值

- **低** — CK 的 tool set 已經由 `ck-missive-bridge` skill 直接 curl Missive API 覆蓋核心查詢路徑。Tool Gateway 主打的 web search / scraping / remote code execution 在 CK 語境下：
  - web search：已有 Open WebUI 代理 或 Missive KG 內部搜
  - scraping：Missive 自己的 ezbid 爬蟲
  - remote code exec：pm2 + ck-ollama + Docker 已夠
- **可能用得到**：Polymarket / arXiv / GitHub 等 specialist skills（但這些也在 upstream bundled skills 裡，不一定要走 Gateway）

### 風險 / 成本

- **成本**：訂閱月費（未查具體價位）。免費層存在但 rate-limit。
- **Vendor lock-in**：Tool Gateway 是 Nous 商業服務；若未來要自 host 或切其他 agent framework，會多一層耦合
- **安全**：把 tool call payload 送第三方

### 建議

- **暫不採用**。待下面條件達成再重評：
  1. Missive KG 查不到的特定外部資料源變成 routine 需求
  2. Nous Portal 定價公佈且可接受
  3. Nous 資料處理合規符合 CK 內部政策（目前未知）
- Default stance：`disabled` 或 unset

## 一表總結

| 功能 | 對 CK 價值 | 風險 | 建議 | 立即動作 |
|---|---|---|---|---|
| `/steer` | 高 | 低 | **採用** | 隨 v2026.4.16 rebase 已內含；告知使用者可用 |
| `execute_code project/strict` | 中 | 低-中 | **預設接受**，ADR-0017 時重評 | 隨 rebase 已內含；無改動 |
| Tool Gateway | 低 | 中（成本+lock-in） | **暫不採用** | 保持 unset |

## 後續事項

- `/steer` 使用情境補入 CK_AaaP `SOUL.md` / Hermes onboarding runbook（非本 session 範圍）
- `execute_code` 在 ADR-0017 Docker Secrets 草案時 **必須列為評估項目**
- Tool Gateway 監看一年：追 Nous Portal 訂閱條款 + `ungate` 相關 issue
