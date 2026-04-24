# Hermes Skill Contract v2 — 實作者 Quick Reference

> **狀態**：draft（2026-04-25 起草）
> **規範源**：`CK_AaaP#0018` Hermes Skill 契約 v2（proposed）
> **適用**：本 fork（NousResearch Hermes Agent v0.10.0+）下的 CK bridge skills
> **本檔目的**：從 hermes-agent Python runtime 視角提供 skill 作者速查；與 ADR-0018 規範互補不重複

## 1. 位置分工

| 層 | 路徑 | 擁有者 |
|---|---|---|
| 規範 | `CK_AaaP#0018` | CK Platform Team |
| 實作速查（本檔）| `hermes-agent/docs/plans/hermes-skill-contract-v2.md` | hermes-agent session |
| Source of truth | `CK_<Project>/docs/hermes-skills/<name>/` | 對應業務 repo |
| Runtime | `~/.hermes/skills/<name>/` 或 `/opt/data/skills/<name>/`（container）| 部署產物 |

**禁止**：在 hermes-agent repo 下寫 `skills/ck-*-bridge/` — 污染 upstream 目錄，rebase 衝突。

## 2. 與 upstream 對接點（hermes-agent 視角）

### 2.1 Skill loader 入口

Hermes gateway 啟動時掃 `~/.hermes/skills/**/SKILL.md`（symlinked category dirs 從 v2026.4.23 才 consistent，見 `fix(skills): follow symlinked category dirs consistently`）。本規範依賴此行為。

### 2.2 tools.py register_all(registry)

```python
def register_all(registry) -> int:
    """
    Hermes skill loader entry point.
    
    Args:
        registry: hermes-agent 的 tools.registry.registry 單例
    
    Returns:
        int: 註冊 tool 數量；0 代表 skill 載入失敗（gateway 會 log warning 但不 crash）
    """
    count = 0
    registry.register(
        name="missive_entity_search",
        description="...",
        parameters={...},
        handler=_handle_entity_search,
        check_fn=_missive_health_check,  # gateway 啟動時呼叫一次
    )
    count += 1
    return count
```

### 2.3 Tool handler 回傳契約

- **永遠回傳 JSON string**（非 dict），讓 Hermes prompt caching 穩定
- **錯誤格式固定**：`{"error": "<code>", "tool": "<name>", "message": "<user-facing>"}`
- **Timeout 實作於 handler**，別依賴 Hermes 外部 timeout（gateway 不中斷執行中 tool）

### 2.4 check_fn 與 prerequisites.services

`SKILL.md` frontmatter 的 `prerequisites.services[].url` 只是**聲明**。真正的 health check 必須在 `tools.py` 提供 `check_fn`：

```python
def _missive_health_check() -> bool:
    try:
        import urllib.request, os
        url = os.environ["MISSIVE_BASE_URL"] + "/api/health"
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False
```

Gateway 啟動時跑一次；失敗則該 skill 的 tool 從 registry 拿掉（不 crash 整個 gateway）。

## 3. Prompt caching 守則

上游政策：**不 mid-conversation 換 toolset**。影響本契約：

1. Skill **升級不可中斷進行中對話** — 用 `docker compose cp` 複製新版 → 讓下一個新 session 自動抓新版，不熱重載
2. 新增 tool 可在 session 邊界生效；移除 tool 會 invalidate cache
3. `prerequisites.env_vars` 變更**必須**寫成 version bump（即使只改 default）— 避免 cache hit 但實際 env 不同

## 4. Profile 隔離接點（v2 新增，與 Master Plan v2 Phase 2 對齊）

當 profile switching 啟用後（尚未）：

- `~/.hermes/profiles/<name>/skills/` 優先於 `~/.hermes/skills/`
- Meta profile（`profiles/meta/`）**不應**載入 domain bridge skill；只載 `llm-wiki` 等 meta skill
- Domain profile（`profiles/missive/`）載對應 bridge：
  ```
  profiles/missive/skills/ck-missive-bridge/  → symlink 或複製自 source of truth
  ```

**目前現況**（2026-04-25）：profile switching 尚未 wire up，所有 skill 都在 `~/.hermes/skills/` 下被全體 profile 共用。本節為 Phase 2 預留設計。

## 5. 本 fork 的已知差異點

| 差異 | upstream 行為 | CK 需求 | 目前如何處理 |
|---|---|---|---|
| `prerequisites.services` | 無此 field | 需啟動時 health check | `check_fn` 走 runtime（ADR-0018 額外欄位留給未來） |
| `metadata.hermes.min_version` | 無檢查 | 想要 gate | 暫用 `python -c "import hermes_cli"` 失敗 exit |
| Skill symlink | v2026.4.23 前不穩 | Phase 2 要 symlink SOUL/skill | **升級 v2026.4.23 為前置** |

## 6. 新建 CK bridge skill SOP

1. 於 `CK_<Project>/docs/hermes-skills/<name>/` 起 skeleton（source of truth）
2. `SKILL.md` frontmatter 填齊 section 2.2 欄位
3. `tools.py` 實作 `register_all` + 每個 tool 的 handler + check_fn
4. `install.sh`：copy 到 `~/.hermes/skills/<name>/` 或 `docker compose cp hermes-gateway:/opt/data/skills/<name>/`
5. 在 hermes-agent session 下：新 session 啟動 → `/skills` 驗證列出 → 呼叫測試
6. 於 `CK_AaaP#0018` registry / `wiki/concepts/skill-<name>.md` 登錄（observer 角色記錄）

## 7. 已知的 CK 現有 / 計劃中 skill

| Skill | Source of Truth | 狀態 | 對應 ADR |
|---|---|---|---|
| `ck-missive-bridge` v2.0 | `CK_Missive/docs/hermes-skills/` | ✅ 已部署 | `CK_Missive#0014` |
| `ck-showcase-bridge` | `CK_Showcase/docs/hermes-skills/`（待建） | 📋 proposed | `CK_AaaP#0021` |
| `ck-observability-bridge` | `CK_DigitalTunnel/docs/hermes-skills/`（待建） | 📋 proposed | `CK_AaaP#0022` |
| `ck-pilemgmt-bridge` | `CK_PileMgmt/docs/hermes-skills/`（待建） | 📋 proposed | `CK_AaaP#0023` |
| `ck-morning-report` | `CK_Missive/docs/hermes-skills/`（待建） | 📋 Phase 1 | — |

## 8. 不要做

- ❌ 在 hermes-agent repo 提交 ck-* skill 檔（source of truth 屬業務 repo）
- ❌ Skill 內 hardcode `http://host.docker.internal:8001` — 讀 env var
- ❌ Skill 內寫 shadow logger（那是 gateway 側 ADR-0014 機制）
- ❌ Skill 內跨 profile 呼叫其他 profile 的 tool（違反 Master Plan v2 D7 bottom-up）
- ❌ Mid-conversation 改 toolset

## 9. Cross-ref

- 規範：`CK_AaaP/adrs/0018-hermes-skill-contract-v2.md`
- Master Plan：`docs/plans/master-integration-plan-v2-2026-04-19.md`
- Profile 隔離陷阱：`~/.hermes/profiles/meta/wiki/concepts/pitfall-hermes-python.md`
- Upstream 相依：`docs/plans/upstream-sync-cadence.md`
- Crystal Seed 複製：`docs/plans/crystal-seed-bootstrap.md`
