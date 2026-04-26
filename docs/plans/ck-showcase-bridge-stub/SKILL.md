---
name: ck-showcase-bridge
version: 0.1.0-stub
description: AaaP 治理面板 bridge（原 Showcase；rebrand 後 = AaaP platform/services API）
author: CK Platform Team
license: MIT

prerequisites:
  env_vars:
    - SHOWCASE_BASE_URL
    - SHOWCASE_API_TOKEN
  optional_env_vars:
    - SHOWCASE_TIMEOUT_S
    - SHOWCASE_SAFE_MODE
  services:
    - url: ${SHOWCASE_BASE_URL}/api/health
      name: ck-aaap-platform-services

metadata:
  hermes:
    tags: [ck, aaap, governance, domain-bridge]
    homepage: http://localhost:5200
    related_skills: [ck-adr-query, ck-observability-bridge, ck-pilemgmt-bridge]
    min_version: "0.10.0"
---

# ck-showcase-bridge

依 ADR-0021 規範。AaaP 平臺治理面板的 Hermes 自然語言入口。

**對齊聲明（2026-04-25 retro 後校準）**：
ADR-0021 寫於 Showcase 為獨立 repo 時。**Showcase 已 rebrand 為 AaaP 平臺**（commit `dead601`），
本 skill 實際連 AaaP `platform/services/` 的治理 API（`:5200` Dashboard / `:5201` API）。
未來 Phase 3 內網改 `http://aaap-platform-services:5200`，公網改 `https://aaap.cksurvey.tw`。

**狀態**：stub-only skeleton（B1 Sprint Step 4）。8 tools 簽名與 frontmatter 已就位；
handler 待 CK_AaaP 採納時填實作。

## Tools 清單

| Tool | 狀態 | ADR-0021 |
|---|---|---|
| `showcase_skills_sync_status` | ⏸ stub | Tool 1 |
| `showcase_agents_list` | ⏸ stub | Tool 2 |
| `showcase_security_scan_run` | ⏸ stub (SAFE_MODE) | Tool 3 |
| `showcase_adr_map_query` | ⏸ stub | Tool 4 |
| `showcase_managed_projects_list` | ⏸ stub | Tool 5 |
| `showcase_sso_status` | ⏸ stub | Tool 6 |
| `showcase_governance_health` | ⏸ stub | Tool 7 |
| `showcase_platform_metrics` | ⏸ stub | Tool 8 |

## 紀律（taiwan.md 觀察者）

- ✅ Showcase backend 不改 — 透過既有 HTTP API 消費
- ✅ SAFE_MODE：security_scan_run mode=run 時 dry-run 預估，不真跑
- ❌ 不替任何 ADR / 治理項目改 status — read-only

## 環境變數

| 變數 | 必要 | 預設 |
|---|---|---|
| `SHOWCASE_BASE_URL` | ✅ | `http://host.docker.internal:5200` |
| `SHOWCASE_API_TOKEN` | ✅ | — |
| `SHOWCASE_TIMEOUT_S` | ❌ | `30` |
| `SHOWCASE_SAFE_MODE` | ❌ | `true` |
