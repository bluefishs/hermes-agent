# Skill Design — `ck-adr-query`

> **狀態**：design + PoC（不部署到 `~/.hermes/skills/`，等 CK_AaaP 採納 ADR-0020 Phase 1 擴範圍提案）
> **規範**：`hermes-skill-contract-v2.md` 實作者指南
> **規範源**：`docs/plans/adr-0020-phase1-extension-proposal.md` §3.E
> **Source of truth（未來）**：`CK_AaaP/docs/hermes-skills/ck-adr-query/`（CK_AaaP session 採納時建）

## 1. 動機

CK 生態 91 個 ADR 散在 6 repo（`CK_AaaP / CK_Missive / CK_DigitalTunnel / CK_PileMgmt / CK_lvrland_Webmap / CK_Showcase`），加上 21 個編號碰撞（同號跨 repo 主題不同）。使用者要回憶「為何用 pgvector 768D」需手動翻 6 repo 或讀 REGISTRY.md 的 markdown 表格。

`ck-adr-query` skill 把「自然語言查詢 ADR」變成 Hermes 一個 tool。**只讀**，不改 ADR 狀態，不杜撰 ADR 內容（taiwan.md 觀察者紀律）。

## 2. 來源資料

| 檔案 | 角色 |
|---|---|
| `D:/CKProject/CK_AaaP/adrs/REGISTRY.md` | 主索引（自動產生），含 lifecycle 分組 |
| `D:/CKProject/CK_AaaP/adrs/*.md` | CK_AaaP ADR 全文 |
| `D:/CKProject/CK_Missive/docs/adr/*.md` | CK_Missive ADR 全文 |
| `D:/CKProject/CK_DigitalTunnel/adrs/*.md` | CK_DigitalTunnel ADR 全文 |
| `D:/CKProject/CK_PileMgmt/adrs/*.md` | CK_PileMgmt ADR 全文 |
| `D:/CKProject/CK_lvrland_Webmap/adrs/*.md` | LvrLand ADR 全文 |
| `D:/CKProject/CK_Showcase/adrs/*.md` | Showcase ADR 全文 |

**前置條件**：所有 6 repo 在同一機器上 cloned 於 `D:/CKProject/`（CK 預設 layout）。

## 3. Skill 規格（依 hermes-skill-contract-v2 §2.2）

### 3.1 Tools

| Tool | 簽章 | 用途 |
|---|---|---|
| `adr_search` | `(query: str, repo: str = "", lifecycle: str = "") -> list[FQID]` | 關鍵字搜尋全文，回 FQID 清單 |
| `adr_read` | `(fqid: str) -> markdown` | 讀單一 ADR 全文 |
| `adr_lifecycle` | `(fqid: str) -> {status, date, last_updated}` | 取生命週期狀態 |
| `adr_list` | `(repo: str = "", lifecycle: str = "")  -> list[{fqid, title, status, date}]` | 列出，支援 lifecycle 過濾 |
| `adr_collisions` | `() -> list[{number, repos: list[str], titles: list[str]}]` | 列出跨 repo 編號碰撞（21 個已知） |

### 3.2 Frontmatter（SKILL.md）

```yaml
---
name: ck-adr-query
version: 0.1.0
description: 查詢 CK 生態 6 repo 跨 91 ADR 的自然語言 skill（read-only）
author: CK Platform Team
license: MIT

prerequisites:
  env_vars:
    - CKPROJECT_ROOT
  services: []  # 純檔案讀取，無外部服務

metadata:
  hermes:
    tags: [ck, adr, governance, read-only]
    homepage: https://github.com/bluefishs/CK_AaaP/blob/main/adrs/REGISTRY.md
    related_skills: [ck-missive-bridge]
    min_version: "0.10.0"
---
```

### 3.3 register_all 骨架

```python
def register_all(registry) -> int:
    from . import handlers
    
    count = 0
    registry.register(
        name="adr_search",
        description="Search CK ecosystem ADRs by keyword. Returns list of FQIDs.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string", "default": ""},
                "lifecycle": {"type": "string", "enum": ["", "proposed", "accepted", "deprecated"]},
            },
            "required": ["query"],
        },
        handler=handlers.adr_search,
        check_fn=handlers.check_ckproject_root,
    )
    count += 1
    # ... (other 4 tools)
    return count
```

## 4. 紀律（taiwan.md 觀察者）

- ✅ **只讀**：不替任何 ADR 改 status / date
- ✅ **可追溯**：每個 search hit 帶 FQID + 檔案 path
- ✅ **不杜撰**：search miss 時回 `{"error": "no_match", "tried": ["..."]}`，不臆測
- ❌ **不跨 repo 同步**：registry 由 `CK_AaaP/scripts/generate-adr-registry.py` 負責，本 skill 不重產
- ❌ **不主動建議改 ADR**：使用者問「這 ADR 該不該 deprecated」→ 回「不在我職責；建議跟 CK_AaaP session 討論」
- ✅ **stale 警示**：若本地 `CK_AaaP/adrs/REGISTRY.md` mtime > 30 天，warn user 「索引可能過期；建議重跑 `generate-adr-registry.py`」

## 5. PoC（純 stdlib Python）

見：`scripts/adr-query-poc.py`

PoC 跑法：
```bash
cd D:/CKProject/hermes-agent
python scripts/adr-query-poc.py search "pgvector"
python scripts/adr-query-poc.py read CK_Missive#0006
python scripts/adr-query-poc.py list --lifecycle proposed
python scripts/adr-query-poc.py collisions
```

## 6. 部署計畫（等 CK_AaaP 採納 ADR-0020 Phase 1 擴範圍提案後）

### 6.1 容器邊界考量（**重要**，2026-04-25 補充）

Hermes runtime 在容器內，僅 mount `~/.hermes`（→ `/opt/data`）；**看不到** `D:/CKProject/CK_*/adrs/`。PoC 在 host 端跑 OK，但容器化後路徑不通。三條落地路徑：

| Variant | 機制 | 優點 | 缺點 |
|---|---|---|---|
| **A** Mount D:/CKProject ro 進容器 | docker-compose.yml 加 `- D:/CKProject:/opt/ckproject:ro` | 即時最新；無 sync 滯後 | 改 compose（CK_AaaP session）；容器看到所有 repo 包含 secrets |
| **B** Cron 萃取 ADR index JSON 進 wiki | host cron 30min run `adr-query-poc.py --json > ~/.hermes/profiles/meta/wiki/raw/adr-index.json`；skill 讀 JSON | 不改 compose；安全（只 export ADR markdown 內容，無 secrets）；snapshot 可追溯 | 30min stale；JSON schema 維護 |
| **C** Skill 透過 hermes-gateway HTTP 呼叫 host 邊車服務 | host 端 Python http server (`:8645`) 包 PoC；skill 在容器內 `host.docker.internal:8645/api/adr/...` | 即時；無 sync 滯後；隔離清楚 | 多一個 host service 要管維護 |

**推薦 Variant B**（30min stale 對 ADR query 完全可接受 — ADR 不會 30 分內變動 5 次）：

1. CK_AaaP session 建 `CK_AaaP/scripts/adr-index-cron.sh`：
   ```bash
   #!/bin/sh
   python /d/CKProject/hermes-agent/scripts/adr-query-poc.py --json-index \
     > ~/.hermes/profiles/meta/wiki/raw/adr-index.json
   ```
2. host crontab：`*/30 * * * * /path/to/adr-index-cron.sh`
3. Skill `tools.py` 讀 `/opt/data/profiles/meta/wiki/raw/adr-index.json`（容器內路徑）
4. PoC 需擴 `--json-index` 命令輸出整個 index 為 single JSON

### 6.2 部署步驟

1. CK_AaaP session 建 `CK_AaaP/docs/hermes-skills/ck-adr-query/`（source of truth）
2. 把本檔內容 + PoC 整合為 `SKILL.md` + `tools.py` + `install.sh`
3. PoC 擴 `--json-index` 命令（hermes-agent session 補完成）
4. host cron 部署 30min ADR index 萃取
5. `install.sh` 複製到 `~/.hermes/skills/ck-adr-query/`
6. 重啟 hermes-gateway → `/skills` 驗證
7. 自然語言測試：`hermes chat -q "為何 Missive 用 pgvector 768D？"`

## 7. 不在範圍

- ❌ Vector embedding ADR（不需，91 個全文 grep 已足夠快）
- ❌ ADR 全文寫入 wiki（業務真相錨定，wiki 不存業務真相）
- ❌ Cross-language（FQID 是英文 + 數字，全保留原樣）
- ❌ 圖形化 ADR 關係圖（Phase 7 之後再議）

## 8. Cross-ref

- ADR-0020 Phase 1 擴範圍：`docs/plans/adr-0020-phase1-extension-proposal.md`
- Skill Contract v2：`docs/plans/hermes-skill-contract-v2.md`
- ADR Registry：`D:/CKProject/CK_AaaP/adrs/REGISTRY.md`（91 ADRs / 21 collisions）
- CONVENTIONS：`D:/CKProject/CK_AaaP/CONVENTIONS.md`（FQID 規範）
