# Hermes Tool Registration 機制研究

> 來源：T1 self-pace 研究（2026-05-16）
> 目的：為 B-1「補實 ck-missive-bridge skill 真實 tool function」釐清前置條件
> 上游：[architecture-retro-action-items-2026-05-15](architecture-retro-action-items-2026-05-15.md)

## 三層架構

### Layer 1 — Tool Registry（`tools/registry.py`）

中央註冊表，全 process 單例 `registry`。關鍵 API：

- `registry.register(name, toolset, schema, handler, check_fn=None, requires_env=None, is_async=False, ...)` — 在模組 import 時呼叫
- `discover_builtin_tools()` — AST 掃描 `tools/*.py`，自動 import 任何在模組頂層呼叫 `registry.register(...)` 的檔案（`tools/registry.py:57-74`）
- `ToolEntry` slots：name / toolset / schema (OpenAI tool schema) / handler (Callable) / check_fn / requires_env / is_async / description / emoji / max_result_size_chars
- Shadow protection：同 name 不同 toolset 註冊會被拒絕；MCP-to-MCP overwrite 允許

### Layer 2 — Skill（`agent/skill_utils.py`）

純 Markdown + YAML frontmatter，**不註冊 tool function**：

- `get_external_skills_dirs()` 讀 `~/.hermes/config.yaml` 的 `skills.external_dirs` 列表
- frontmatter 欄位：`name` / `description` / `platforms` / `toolsets`（啟用某 toolset 對應的全部 tool）
- skill body 是 prompt 模板，告訴 LLM 何時用 tool

### Layer 3 — MCP Tool（`tools/mcp_tool.py`）

外部 MCP server 動態註冊：

- `register_mcp_servers(servers: Dict[str, dict])`（`mcp_tool.py:3041`）
- `registry.register_toolset_alias(name, toolset_name)`（`mcp_tool.py:3007`）— 為 MCP toolset 配 alias
- 支援 `notifications/tools/list_changed` 動態 refresh

## ck-missive-bridge 補實的三條路徑

| 路徑 | 機制 | 工時 | 風險 |
|---|---|---|---|
| **α. Native tool** | 寫 `tools/missive_tool.py`，`registry.register("missive_health", ...)` 與 `registry.register("missive_get_document", ...)`；skill frontmatter 加 `toolsets: [missive]` | 1d | 改本 repo 需 commit；最小範圍 |
| **β. MCP server** | Missive 端新增 MCP server endpoint，hermes-agent 由 `register_mcp_servers()` 載入 | 2–3d | 雙 repo 連動；MCP wire protocol 學習成本 |
| **γ. Inline HTTP tool** | 不註冊新 tool，僅在 skill body 精確 prompt LLM 使用 hermes 內建 HTTP/Bash tool 構造請求 | 0.5d | LLM hallucination URL/payload；不可重複 |

**推薦：α**。理由：

1. 工時最短，完全在 hermes-agent session 範圍內
2. 為其他 3 個 bridge（observability/showcase/pilemgmt）建立可複製範式
3. 對應 ADR-0020 Phase 1 標準路徑：每個受管專案 = 1 個 toolset
4. handler 是純 Python，便於 mock，QW-3 e2e test 可拆 unit + integration 兩層

## α 路徑落地清單（B-1 細項）

```
tools/missive_tool.py
  ├─ schema_health = { name: "missive_health", description: "...", parameters: {...} }
  ├─ schema_get_doc = { name: "missive_get_document", description: "...", parameters: {id: ...} }
  ├─ async def handle_health(args) -> Dict[str, Any]:
  │     # httpx GET ${MISSIVE_BASE_URL}/health
  ├─ async def handle_get_document(args) -> Dict[str, Any]:
  │     # httpx GET ${MISSIVE_BASE_URL}/api/documents/${id}
  └─ registry.register("missive_health", "missive", schema_health, handle_health, ...)
     registry.register("missive_get_document", "missive", schema_get_doc, handle_get_document, ...)

tests/tools/test_missive_tool.py
  ├─ unit：httpx_mock 驗證 URL / header / timeout / error handling
  └─ check_fn：MISSIVE_BASE_URL env 不存在時 toolset disable

CK_Missive/docs/hermes-skills/ck-missive-bridge/SKILL.md
  └─ frontmatter 加 `toolsets: [missive]`，body 縮減（不再描述 URL 構造，交給 tool schema）
```

## 跨 session 依賴

| 動作 | session | 必要 |
|---|---|---|
| `tools/missive_tool.py` + test | hermes-agent | ✅ |
| `MISSIVE_BASE_URL` env 注入 `hermes-stack/.env` | CK_AaaP | ✅ |
| SKILL.md frontmatter `toolsets` 更新 | CK_Missive（部署包） | ✅ |
| README / wiki 更新 | hermes-agent | ✅ |

## 後續

- 本研究覆蓋 B-1。同型範式可直接複製到 C-3 三 bridge：`tools/showcase_tool.py` / `tools/observability_tool.py` / `tools/pilemgmt_tool.py`，後續節省 60%+ 工時
- QW-3 e2e test 應在 B-1 落地後寫，否則只能測 prompt 模板
- 若團隊未來要把 hermes-agent 與業務服務解耦（避免 hermes-agent 變成「萬能 client」），β MCP 路徑可作為遷移目標

> 結論：α 路徑為最大效益。下一輪 self-pace 可開始 B-1 第一步（建立 `tools/missive_tool.py` 骨架 + 第一個 unit test，純 RED-GREEN TDD），仍無 git 風險。
