# ck-observability-bridge skeleton（B1 Sprint Step 1）

> **狀態**：skeleton（不直接部署）
> **規範源**：`CK_AaaP#0022 ck-observability-bridge-skill` (proposed)
> **規範**：`hermes-skill-contract-v2.md`
> **產生**：2026-04-25 hermes-agent session
> **對齊**：retro-2026-04-25.md §3.F (F 補強 ADR-0022)
> **PoC 來源**：`scripts/loki-tail-poc.py`

## 目的

提供 ADR-0022 的具體實作骨架，供 CK_AaaP session 採納時搬移到
`platform/services/docs/hermes-skills/ck-observability-bridge/` 作為 source of truth。

## 涵蓋範圍

| Tool（依 ADR-0022） | 本 skeleton |
|---|---|
| `obs_loki_query` | ✅ 完整實作（含 stream 解析 + label filter） |
| `obs_loki_errors` | ✅ **補強**（ADR-0022 未列；retro §3.F 提案）|
| `obs_loki_briefing` | ✅ **補強**（ADR-0022 未列；retro §3.F 提案，markdown 輸出）|
| `obs_prom_query` | ⏸ stub（NotImplementedError）|
| `obs_grafana_dashboard_url` | ⏸ stub |
| `obs_alertmanager_silence` | ⏸ stub（含 SAFE_MODE 預設拒絕邏輯）|
| `obs_container_health` | ⏸ stub |
| `obs_alert_active` | ⏸ stub |

## 不直接部署的原因

依 hermes-skill-contract-v2 §1：
> Source of truth：CK_<Project>/docs/hermes-skills/<name>/
> **禁止**：在 hermes-agent repo 下寫 `skills/ck-*-bridge/` — 污染 upstream 目錄

本 skeleton 放於 `docs/plans/ck-observability-bridge-skeleton/`（hermes-agent local plans，
不污染 upstream skills/ 路徑）。CK_AaaP session 採納並建立 source of truth 路徑後，
透過 install.sh 部署到 `~/.hermes/skills/ck-observability-bridge/`。

## 採納路徑（CK_AaaP session）

```bash
cd D:/CKProject/CK_AaaP

# 1. 建立 source of truth
mkdir -p platform/services/docs/hermes-skills/ck-observability-bridge

# 2. 從 hermes-agent 複製 skeleton
cp -r ../hermes-agent/docs/plans/ck-observability-bridge-skeleton/* \
      platform/services/docs/hermes-skills/ck-observability-bridge/

# 3. 修檔內 cross-ref（hermes-agent skeleton → source of truth）
# 4. ADR-0022 status: proposed → executing
# 5. 執行 install.sh 部署到 ~/.hermes/skills/
# 6. hermes-agent session 重啟 hermes-gateway 驗證 /skills 有此 skill
```

## Cross-ref

- ADR-0022：`CK_AaaP/adrs/0022-ck-observability-bridge-skill.md`
- Skill Contract：`docs/plans/hermes-skill-contract-v2.md`
- PoC 設計：`docs/plans/skill-ck-loki-tail-design.md`（已 retract，併入本 skeleton）
- Loki PoC 純 stdlib：`scripts/loki-tail-poc.py`
