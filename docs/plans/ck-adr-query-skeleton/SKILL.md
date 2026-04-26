---
name: ck-adr-query
version: 0.1.0
description: 跨 CK 6 repo 91+ ADR 自然語言查詢 skill（read-only，data-driven via Variant B）
author: CK Platform Team
license: MIT

prerequisites:
  env_vars: []
  optional_env_vars:
    - ADR_INDEX_PATH
  services: []  # 純檔案讀取，無外部服務

metadata:
  hermes:
    tags: [ck, adr, governance, read-only]
    homepage: https://github.com/bluefishs/CK_AaaP/blob/main/adrs/REGISTRY.md
    related_skills: [ck-missive-bridge, ck-observability-bridge]
    min_version: "0.10.0"
---

# ck-adr-query

跨 CK 生態 6 repo 91+ ADR 的自然語言查詢入口。

依 retro-2026-04-25 §3.E 提案；遵循 taiwan.md 觀察者紀律（只讀、不杜撰、不替治理改 status）。

## 設計原則

1. **Data-driven** — 不直接掃 6 repo（容器內看不到 D:/CKProject）；讀預先萃取的 JSON index
2. **Stale warn** — JSON mtime > 30 天主動提示重跑萃取
3. **碰撞透明** — `adr_collisions` 為 first-class tool，治理 ADR 編號漂移風險直接可見
4. **不杜撰** — search miss 回 structured error，不臆測
5. **觀察者紀律** — 不主動建議改 ADR；ADR 全文不入 wiki

## 環境變數

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `ADR_INDEX_PATH` | ❌ | `/opt/data/profiles/meta/wiki/raw/adr-index.json`（容器）/ `~/.hermes/profiles/meta/wiki/raw/adr-index.json`（host）| 索引 JSON path |

## 資料萃取（Host 端 cron）

```cron
*/30 * * * * /usr/bin/python /d/CKProject/hermes-agent/scripts/adr-query-poc.py index --pretty > ~/.hermes/profiles/meta/wiki/raw/adr-index.json
```

JSON schema 1.0；含 104+ ADRs metadata + 32 collisions。30 分鐘 stale 對 ADR 查詢完全可接受
（ADR 不會 30 分內變動 5 次）。

## Tools 清單

| Tool | 狀態 |
|---|---|
| `adr_search` | ✅ implemented |
| `adr_list` | ✅ implemented |
| `adr_lifecycle` | ✅ implemented |
| `adr_collisions` | ✅ implemented |
| `adr_read` | ⚠️ stub（容器邊界；回 host path 引導使用者）|
