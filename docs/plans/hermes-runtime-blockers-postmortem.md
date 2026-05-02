# Hermes Runtime Tool-Calling 真因 Postmortem — 6 層真因

> **日期**：2026-05-01（第四輪 iteration 終結版）
> **session**：hermes-agent
> **狀態**：完整真因鏈確認 → **架構性問題**，非單點修補可解
> **取代**：v1 / v2 / v3 playbook 全部假設

## TL;DR

**ck-* bridge skill 對接 hermes runtime 的設計與 hermes（NousResearch fork）的設計哲學 mismatched**。

實驗證據（4 trials × 3 hermes-runtime test）找出 **6 層真因鏈**：

| # | 假設 | 證據 | 結論 |
|---|---|---|---|
| L1 | 13K context 過大壓垮 7B model | Trial C: 12990 tokens 仍 ✅ | ❌ 否定 |
| L2 | qwen2.5:7b 能力不足 | Trial D: OpenAI tools schema 全 ✅ | ❌ 否定 |
| L3 | ck-* SKILL.md 沒寫 curl 範例 | E1: 即使明確命令也被擋 | 🟡 部分（model 會 emit）|
| L4 | hermes tirith security scan 擋 plain HTTP | E1: `[HIGH] Plain HTTP URL` | ✅ 真因 |
| L5 | hermes container 沒裝 curl binary | E1b: `curl: command not found` | ✅ 真因 |
| L6 | python -c 被 hermes approval gate 擋 | E1c: `script execution via -e/-c flag. Asking for approval` | ✅ 真因 |

**根本架構問題（L7）**：hermes 設計給「local dev agent 跑 terminal/code/web 任務」，**不是設計給「自然語言 → 內部 HTTP API gateway」**。CK 把 6 個業務 backend 包成 ck-* skill 期望 model 透過 terminal+curl 呼叫，但 hermes 三道安全閘 + 缺 binary 把這條路堵死。

## 6 層真因詳細

### L1：Context size 否定（v1 假設破產）

**Trial C** 用 27K chars / 12990 tokens 測試 raw qwen2.5:7b：

```json
{
  "label": "C_full_simulated",
  "prompt_tokens_actual": 12990,
  "has_tool_call_xml": true,
  "content_preview": "<tool_call>{\"name\": \"missive_health\", \"arguments\": {}}</tool_call>"
}
```

**結論**：7B model 在 13K context 下 instruction-following 完全 OK。v1 推薦的「skill lazy-load 6→1」**完全不必要**。

### L2：Model 能力否定（v1 假設破產）

**Trial D** 用 ollama OpenAI-compat + 標準 tools schema：

```json
{
  "label": "D3_soul_plus_skill",
  "prompt_tokens": 3743,
  "openai_tool_calls": [{"name": "missive_health", "args": "{}"}]
}
```

**結論**：qwen2.5:7b 完全支援 OpenAI function-calling。v1 推薦的「換 Groq primary」「啟 Anthropic escalate」**不必要**。

### L3：SKILL.md 缺 curl 範例（v2 假設半破）

**E1** 用 hermes runtime + 明確 user message「請使用 terminal 執行 curl ...」：

```
[0] FUNCTION_CALL name=terminal args={"command":"curl -s http://host.docker.internal:8001/api/health"}
```

Model **完全會** emit terminal function_call。所以 v2 推薦「加 curl 範例到 SKILL.md」確實能讓 model 學會 emit—— 但**下游被擋**（見 L4-L6）。

`grep register_all` in hermes codebase = **0 hits** 仍是真實 finding：ck-* `tools.py / register_all(registry)` 設計**hermes 不認**，這個 convention 從一開始就是 placebo。

### L4：tirith security scan 擋 plain HTTP（真實 P0 #1）

**E1** 結果：

```
[1] FUNCTION_OUTPUT:
{
  "exit_code": -1,
  "error": "⚠️ Security scan — [HIGH] Plain HTTP URL in execution context:
            URL 'http://host.docker.internal:8001/api/health' uses unencrypted HTTP..."
}
```

**Source**：`/opt/hermes/tools/tirith_security.py` + `/opt/hermes/tools/approval.py:704`

ck-* skill 的 `MISSIVE_BASE_URL=http://host.docker.internal:8001` 全部會被 tirith 標 HIGH severity → block。

### L5：Container 無 curl binary（真實 P0 #2）

**E1b** 改用 HTTPS（CF Tunnel `https://missive.cksurvey.tw`）：

```
[0] FUNCTION_CALL name=terminal args={"command":"curl -s https://missive.cksurvey.tw/api/health"}
[1] FUNCTION_OUTPUT: {"output": "/usr/bin/bash: line 3: curl: command not found", "exit_code": 127}
```

NousResearch hermes-agent docker image 沒裝 curl。`docker exec ... which python python3 wget curl httpie` 結果：**只有 `python3`**。

### L6：python -c 被 approval gate 擋（真實 P0 #3）

**E1c** 改用 `python3 -c "import urllib..."`：

```
[1] FUNCTION_OUTPUT:
{
  "exit_code": -1,
  "error": "⚠️ script execution via -e/-c flag. Asking the user for approval.",
  "status": "approval_required"
}
```

**Source**：`/opt/hermes/tools/approval.py` `detect_dangerous_command` — `python -c` / `bash -c` 等 inline script execution flag 被列為需要 approval。

OpenAI-API client 沒處理 approval 機制 → 卡死。

### L7：架構性 mismatch（最深層）

Hermes 設計哲學：
- **本機 dev agent**：terminal/code/web 三個 core toolset，model 像 software engineer 跑 git / pytest / curl
- **內建安全閘**：tirith scan + approval gate 防止意外破壞
- **Skill = 內建 toolset 的使用範例**（如 arxiv skill：「用 curl 打這個 URL」）

CK 設計：
- **業務 NL → API gateway**：用戶問業務問題，model 路由到對應 backend
- 6 個業務 backend 包成 ck-* skill
- **錯把 skill 當作 API tool registry**（用 `register_all(registry)` 但 hermes 不認）

不匹配點：
1. CK 期望 skill 自動 register tool；hermes 期望 model 看 SKILL.md 自己用 terminal
2. CK 用 plain HTTP 對 internal backend；hermes tirith block
3. CK 沒在 image 加 curl；hermes 預設只有 python3
4. python -c 被 hermes approval gate 擋

## 4 條 Unblock 路徑（不再是 3 條，全部需重新評估）

### 路徑 R1 — 對症下藥（修每個層）

| 層 | 修法 | 工時 | 風險 |
|---|---|---|---|
| L4 | ck-* skill MISSIVE_BASE_URL 統一改 HTTPS（CF Tunnel）| 30 min | LvrLand/Pile 等 subdomain 還沒上 CF Tunnel（roadmap #12-13）|
| L5 | rebuild hermes image 加 RUN apt install curl | 1h（含 image rebuild）| 偏離 upstream image |
| L6 | helper script（不用 -c flag）寫進 skill `scripts/`，SKILL.md 教 `bash scripts/foo.sh` | 1h × 5 skill | sane，類似 arxiv skill 範式 |

合計：~5h，分散到各業務 repo。

### 路徑 R2 — Yolo mode（risky）

```yaml
# config.yaml
approvals:
  mode: off  # 關掉 approval gate
```

或 env：
```bash
HERMES_YOLO_MODE=1
```

**風險**：所有命令 auto-approve，包含 `rm -rf /`。production 公網入口**不能用**。

### 路徑 R3 — 改架構：hermes 不做 API gateway

接受 hermes 不適合作為「業務 NL gateway」，把它定位為原本設計：**dev agent**。
業務 NL → API 走另一條路：
- 簡單方案：業務 backend 各自 expose `/api/v1/ai/query` endpoint，hermes 透過 `web_extract` （啟用 web toolset）打它
- 完整方案：另起一個 lightweight router（FastAPI），hermes 只負責 chat/intent 分類

**工時**：完整方案 1 週起跳。

### 路徑 R4 — Patch hermes 認 register_all

最徹底的解：fork hermes 改 prompt_builder + tool_registry，讓 ck-* skill 的 `register_all(registry)` 真的把 tool register 為 OpenAI tools schema 傳給 model。

```python
# hypothetical patch in /opt/hermes/agent/skill_loader.py
def load_ck_skill(skill_dir):
    if (skill_dir / "tools.py").exists():
        spec = importlib.util.spec_from_file_location(...)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, 'register_all'):
            count = mod.register_all(_global_tool_registry)
            return count
    return 0
```

**工時**：hermes-agent fork patch + upstream PR + 1–2 週測試。

## 推薦執行序

| 步驟 | 路徑 | 工時 | 為何先做 |
|---|---|---|---|
| 1 | R1 - L6 helper script（5 skill）| 5h | 解 L6 + 標準化（仿 arxiv skill），CK 可控 |
| 2 | R1 - L4 改 HTTPS | 30 min × 5 | 解 L4，但需 LvrLand/Pile CF Tunnel 先上（依賴 roadmap）|
| 3 | R1 - L5 rebuild image | 1h | 加 curl 讓 helper script 可用 curl |
| **替代** | **R3 改架構** | **1 週** | **長期最乾淨**，但需業務 repo 配合 |
| **絕不** | **R2 yolo** | — | **public-facing 不可用** |

## 對先前產出的影響

| 文件 | 影響 |
|---|---|
| `hermes-integration-playbook.md` v1（縮 context / 換 Groq / escalate） | 全部過時，**不要照做** |
| `hermes-integration-playbook.md` v2（SKILL.md curl pattern） | L4-L6 把這條路堵死，**不夠** |
| `skill-curl-pattern-patch.md`（5 skill 統一 curl patch） | 配合 R1 重做：改 helper script + HTTPS endpoint |
| `escalate-config-patch-2026-04-29.md` | 與 P0 無關，**仍可做但不解 P0** |
| `escalate-helpers/`（complexity helper） | 與 P0 無關，**仍是好設計**但解不了 tool-call 失效 |
| `cross-session-execution-roadmap` #6 (escalate) | 降為 P2（非阻塞）|
| `cross-session-execution-roadmap` #12-13 (CF Tunnel) | **升為 P0**（解 L4 的前置）|

## 業務影響

當前用戶若用 Open WebUI / Telegram / OpenAI-API 對 hermes 問業務問題：
- Model 知道有 ck-* skill（SKILL.md 在 prompt context）
- 但**無法實際呼叫**（L4-L6 三道閘擋住）
- 用戶看到的是「我將呼叫 ck-missive-bridge 工具」**自然語言模擬**
- **零實際業務查詢能力**

這是 P0 服務可用性問題，但是**架構性的**，無法 30 min 修。

## 立即建議（用戶決策）

**Option α — 接受 hermes 當 chat-only**：
- 暫時把 hermes 用作 NL chat（不期望 tool-call 業務 backend）
- 業務查詢走另一個入口（Open WebUI 直接打業務 backend，bypass hermes）
- **工時 0**，但失去 hermes-as-gateway 的設計意圖

**Option β — 走 R1 對症下藥**：
- 業務 repo 各自 30 min – 5h 套路徑
- 先 helper script + HTTPS（依賴 CF Tunnel 完成）
- 4 週內可有業務查詢能力

**Option γ — 走 R3 改架構**：
- 寫獨立 lightweight FastAPI router
- hermes 只做 NL parsing
- 1 週工時，最乾淨但最大變動

**推薦 β**：路徑明確、不大改架構、與既有 ADR-0020 平台化方向一致。

## 變更歷史

- **2026-05-01** — 初版（hermes-agent session 第四輪 iteration）；6 層真因確認；取代 playbook v1/v2

## 相關文件

- `docs/plans/_ab_lab/run_ab.py` `run_trial_d.py` — A/B/C/D 4 trials 證據
- `docs/plans/_ab_lab/results.json` `results_d.json` — 實驗結果
- `/opt/hermes/tools/tirith_security.py` — L4 source
- `/opt/hermes/tools/approval.py:704` — L6 source
- `/opt/hermes/agent/prompt_builder.py:196` — TOOL_USE_ENFORCEMENT_MODELS 證據
- `docs/plans/hermes-integration-playbook.md` — v1/v2 過時 playbook（已加校正段）
- `docs/plans/skill-curl-pattern-patch.md` — v2 patch 設計（部分過時，需重做）
- `D:/CKProject/CK_AaaP/adrs/0020-aaap-platform-with-hermes-control-plane.md` — 平台化總綱（β 路徑與此對齊）
