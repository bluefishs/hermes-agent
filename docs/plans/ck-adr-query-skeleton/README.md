# ck-adr-query skeleton（B1 Sprint Step 2）

> **狀態**：skeleton（不直接部署）
> **規範源**：`docs/plans/adr-0020-phase1-extension-proposal.md` §3.E（**新提案**，無對應既有 ADR）
> **規範**：`hermes-skill-contract-v2.md`
> **產生**：2026-04-26 hermes-agent session
> **PoC 來源**：`scripts/adr-query-poc.py`
> **資料源**：`~/.hermes/profiles/meta/wiki/raw/adr-index.json`（Variant B 路徑）

## 目的

跨 6 repo 91+ ADR 自然語言查詢入口。使用者問「為何 Missive 用 pgvector 768D」→
skill 直接從預先萃取的 JSON index 找 → 回 FQID 摘要。

依 retro §3.E 提案。CK_AaaP 採納時建議新增 ADR-0026（編號讓 CK_AaaP session 決定）。

## 涵蓋範圍

| Tool | 狀態 |
|---|---|
| `adr_search(query, repo, lifecycle)` | ✅ 完整實作 |
| `adr_list(repo, lifecycle)` | ✅ 完整實作 |
| `adr_lifecycle(fqid)` | ✅ 完整實作 |
| `adr_collisions()` | ✅ 完整實作（21+ 已知碰撞）|
| `adr_read(fqid)` | ⚠️ stub — 容器邊界限制（見 §3）|

## 容器邊界考量（Variant B 落地）

依 `skill-ck-adr-query-design.md` §6.1：
- Host 端 cron 30min 跑 `python scripts/adr-query-poc.py index --pretty > ~/.hermes/profiles/meta/wiki/raw/adr-index.json`
- 容器內 skill 從 `/opt/data/profiles/meta/wiki/raw/adr-index.json`（bind-mounted） 讀
- 完整 ADR 全文不入 JSON（避免 500KB+ 包袱）→ `adr_read` 為 stub，回 host path 引導使用者自查

## 紀律（taiwan.md 觀察者）

- ✅ 只讀 JSON；不替任何 ADR 改 status / date
- ✅ search miss 回 `{"error": "no_match", "tried": ["..."]}`；不杜撰
- ✅ stale 警示：JSON mtime > 30 天 warn 「索引可能過期；建議重跑 adr-query-poc.py index」
- ✅ adr_collisions 為 first-class — 主動暴露 21+ 跨 repo 編號碰撞風險
- ❌ 不主動建議改 ADR / lifecycle 變更 → 「不在我職責；建議跟 CK_AaaP session 討論」
- ❌ 不寫進 wiki 任何業務真相（業務真相錨定 Missive）

## 採納路徑（CK_AaaP session）

```bash
cd D:/CKProject/CK_AaaP

# 1. 建立 source of truth
mkdir -p platform/services/docs/hermes-skills/ck-adr-query

# 2. 從 hermes-agent 複製 skeleton
cp -r ../hermes-agent/docs/plans/ck-adr-query-skeleton/* \
      platform/services/docs/hermes-skills/ck-adr-query/

# 3. 加 host cron（每 30 分鐘萃取 ADR index）
# 用 Windows Task Scheduler 或 Linux cron：
#   */30 * * * * /usr/bin/python /d/CKProject/hermes-agent/scripts/adr-query-poc.py index --pretty > /c/Users/User1/.hermes/profiles/meta/wiki/raw/adr-index.json

# 4. 採納 ADR-0026 ck-adr-query-skill（依 retro §3.E 提案）
# 5. install.sh 部署到 ~/.hermes/skills/
# 6. hermes-agent session 重啟 hermes-gateway 驗證
```

## Cross-ref

- ADR-0020 Phase 1 ext §3.E：`docs/plans/adr-0020-phase1-extension-proposal.md`
- 設計：`docs/plans/skill-ck-adr-query-design.md`
- PoC：`scripts/adr-query-poc.py`
- 資料源：`~/.hermes/profiles/meta/wiki/raw/adr-index.json`（已產出）
