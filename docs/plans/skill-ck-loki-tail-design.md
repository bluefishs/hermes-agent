# Skill Design — `ck-loki-tail`

> **狀態**：design + PoC（不部署，等 CK_AaaP 採納 ADR-0020 Phase 1 擴範圍提案）
> **規範源**：`docs/plans/adr-0020-phase1-extension-proposal.md` §3.F
> **規範**：`hermes-skill-contract-v2.md` 實作者指南
> **Source of truth（未來）**：`CK_AaaP/docs/hermes-skills/ck-loki-tail/`

## 1. 動機

CK 觀測棧 (`CK_DigitalTunnel#0040` / Loki 3.4.2) 已 2026-04-17 驗收通過，13+ 容器日誌統一進 Loki。但「使用者要看本週 ERROR」需手動：
1. 開 Grafana :13000 → Explore → 建 LogQL → 篩 → 分組
2. 或 `docker logs <one-container>` 一個個查

`ck-loki-tail` 把 Loki HTTP API 包裝為 Hermes tool，`ck-loki-tail` cron + briefing 模式自動每日彙整 ERROR 給 Meta wiki。

## 2. Loki endpoint

| 場域 | URL |
|---|---|
| Host shell | `http://localhost:13100` |
| Hermes 容器內 | `http://host.docker.internal:13100` |
| Override | `LOKI_BASE` env var |

容器 `ck-platform-loki` (port 13100→3100)，已 expose 給 host。

## 3. Skill 規格（依 hermes-skill-contract-v2 §2.2）

### 3.1 Tools

| Tool | 簽章 | 用途 |
|---|---|---|
| `loki_labels` | `() -> list[str]` | 列出全 label |
| `loki_services` | `() -> list[str]` | 列出已 ingest 的 container |
| `loki_query` | `(logql: str, hours: int = 1, limit: int = 100) -> list[entry]` | LogQL 查詢，回 list[{ts,container,line}] |
| `loki_errors` | `(hours: int = 24) -> dict` | ERROR-pattern 統計（by container），回 {total, by_service, samples} |
| `loki_briefing` | `(hours: int = 24) -> markdown` | 直接產 markdown briefing |

### 3.2 Frontmatter

```yaml
---
name: ck-loki-tail
version: 0.1.0
description: 連 CK 觀測棧 Loki HTTP API 萃取容器日誌（read-only）
author: CK Platform Team
license: MIT

prerequisites:
  env_vars:
    - LOKI_BASE  # default http://host.docker.internal:13100
  services:
    - url: ${LOKI_BASE}/ready
      name: ck-platform-loki

metadata:
  hermes:
    tags: [ck, observability, loki, read-only]
    homepage: http://localhost:13000  # Grafana
    related_skills: [ck-missive-bridge]
    min_version: "0.10.0"
---
```

### 3.3 紀律（taiwan.md 觀察者）

- ✅ **只讀**：不修 Loki 設定、不刪 logs
- ✅ **不主動干預**：briefing 不附「建議 restart 容器」之類干預命令
- ✅ **可追溯**：每個 entry 帶 timestamp + container + raw line（不二次解讀）
- ❌ **不解讀業務含義**：Missive postgres FK error → 不臆測案號或業務影響；交 Missive agent 看
- ❌ **不入 wiki 業務真相**：briefing 進 `wiki/briefings/morning-{date}.md`（ephemeral）；不進 `concepts/` 永久區
- ⚠️ **PII filter**：briefing 不顯示完整 stack trace 中可能含的 PII（譬如公文姓名）；用 `line[:160]` 截斷

## 4. PoC 驗證結果

`scripts/loki-tail-poc.py` 對 live Loki 跑 6 hour window：

```
Total ERROR-pattern lines in last 6h: 5000
Distinct services emitting: 5

  4967  ck-platform-node-exporter         (← noise: prometheus scrape errors)
    26  ck_pilemgmt-backend-1             (← false positive: "Exception handlers registered successfully")
     4  ck-platform-alertmanager          (← genuine warn)
     2  ck-tunnel-worker-1                (← false positive: "INFO ... succeeded")
     1  ck_missive_postgres_dev           (← genuine ERROR: FK constraint violation)
```

**洞見**：simple `(?i)(error|exception|...)` regex 大量 noise + 假陽性。**正式 skill 須改良**：

| 改良 | 動作 |
|---|---|
| Noise 降低 | 預設排除 `ck-platform-node-exporter`（metrics scrape 失敗為常態） |
| 真陽性聚焦 | LogQL `\| level="error"` 用結構化 label 而非 text grep |
| 假陽性過濾 | regex 加 negative lookahead：`(?i)(error\|exception)(?!.*(success\|registered))` |
| Aggregation | 用 `sum by (container) (count_over_time({}[1h]))` 取 hourly trend |
| 分級 | 把結果分「真 ERROR」/「warning」/「filtered noise」三段 |

## 5. Cron 整合（與 daily-closing 配合）

未來 cron schedule：
- 22:30 daily-extraction：呼叫 `loki_briefing(hours=24)` → 寫 `briefings/morning-{tomorrow}.md` 的「觀測段」
- 07:30 daily-awakening：讀 briefing 中觀測段，若有真 ERROR → 簡述給使用者

需 `enabled_toolsets: [ck-loki-tail, llm-wiki]` 縮 token（v2026.4.23 新功能）。

## 6. 部署計畫（等 CK_AaaP 採納）

1. CK_AaaP session 建 `CK_AaaP/docs/hermes-skills/ck-loki-tail/`
2. SKILL.md / tools.py / install.sh
3. 加 `LOKI_BASE` 到 `~/.hermes/.env`
4. `install.sh` → `~/.hermes/skills/ck-loki-tail/`
5. 重啟 hermes-gateway → `/skills` 驗證
6. 測試：`hermes chat -q "近 24h 容器 ERROR 摘要"`

## 7. 不在範圍

- ❌ 寫 Loki / 改 retention 設定（屬 ADR-0019 觀測統一範圍）
- ❌ 跨 Loki/Prometheus/Alertmanager 全棧查詢（Phase 2+）
- ❌ Auto-remediation（Hermes 永遠不主動 restart 容器）
- ❌ 把日誌 mirror 到 wiki 永久區（business secret leak risk）

## 8. Cross-ref

- ADR-0020 Phase 1 ext：`docs/plans/adr-0020-phase1-extension-proposal.md`
- Skill Contract v2：`docs/plans/hermes-skill-contract-v2.md`
- 觀測棧文件：`CK_AaaP/runbooks/loki-verification.md`
- ADR-0019 觀測統一：`CK_Missive#0019 / CK_AaaP#0019`
- ADR-0040 Cloudflare Tunnel：`CK_DigitalTunnel#0040`
