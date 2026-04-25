# ADR-0020 Phase 1 擴範圍提案 — Hermes 為「謙遜路由器」中樞

> **狀態**：proposal（hermes-agent session 起草，等 CK_AaaP session 採納轉為 ADR-0020 Phase 1 修訂版）
> **產生**：2026-04-25
> **使用者授權**：「採 taiwan.md 概念辦理」（2026-04-25）→ Brain 路徑採**謙遜路由器**而非全知中樞
> **規範源**：`CK_AaaP#0020`（執行中 Phase 1）
> **靈感**：[`design-inspirations-muse-semiont.md`](../../../profiles/meta/wiki/concepts/design-inspirations-muse-semiont.md)

## 1. 為何擴範圍

ADR-0020 Phase 1 原定「擴 4 個 bridge skill」。經本 session 評估：

- 4 bridge skill 解 **入口分歧**，但無法解 **配置/觀測/治理分歧**
- Hermes 已運行至 v0.10.0+ → v2026.4.23（剛完成 sync），新 upstream 含 skill symlink 修復、profile staging、cron toolset 隔離 — Phase 1 載入更多任務的技術前置已成熟
- 使用者明示 Brain = 「謙遜路由器」（taiwan.md 隱喻）→ Hermes 該知道**誰**有答案，但不替他們答

**擴範圍 ≠ 擴職責**。Hermes 多管的事都是**讀**與**彙整**；**寫**仍在各業務 agent。

## 2. 原 Phase 1 範圍 vs 擴範圍

| 動作 | 原 | 擴 |
|---|---|---|
| **A** ck-missive-bridge v2.0 | ✅ 已部署 | ✅ 不變 |
| **B** ck-showcase-bridge | 📋 ADR-0021 proposed | ✅ 不變 |
| **C** ck-observability-bridge | 📋 ADR-0022 proposed | ✅ **不另立**；本提案 §3.F 改為**補強 ADR-0022 — 提供 Loki 子集 PoC + 5 條 noise 改良策略** |
| **D** ck-pilemgmt-bridge | 📋 ADR-0023 proposed | ✅ 不變 |
| **E** ck-adr-query skill（新） | — | ✅ **新增** — 跨 6 repo ADR 自然語言查詢（無對應既有 ADR）|
| **F** ~~ck-loki-tail skill~~ → **補強 ADR-0022** | — | ✅ **修正**：併入 ADR-0022 而非另立（**2026-04-25 retro 後**） |
| **G** unified-entry 路由（新） | — | ✅ **新增** — Open WebUI / Telegram / CLI 走同一 hermes-gateway |

新增 E + G 兩項；F 改為補強既有 ADR-0022。全部本地，不違反 zero-cost 硬約束。

## 3. 三項新 skill 的「謙遜路由器」紀律

### E. ck-adr-query

**做什麼**：使用者問「為何 Missive 用 pgvector 768D」→ skill 掃 6 repo ADR registry → 找到 `CK_Missive#0006` → 摘要回答 + 提供 FQID 連結

**不做什麼**：
- ❌ 不替任何 ADR 改 status
- ❌ 不杜撰 ADR 內容（讀什麼說什麼）
- ❌ 不跨 repo 同步（registry generation 由 `CK_AaaP/scripts/generate-adr-registry.py` 負責）

**Tools**：
- `adr_search(query: str) -> list[FQID]`
- `adr_read(fqid: str) -> markdown`
- `adr_lifecycle(fqid: str) -> {accepted/proposed/...}`

**Source of truth**：`CK_AaaP/adrs/REGISTRY.md`（自動產生）+ 各 repo `<root>/adrs/` 或 `docs/adr/`

### F. ~~ck-loki-tail~~ → 補強 ADR-0022 ck-observability-bridge

**2026-04-25 retro 校準**：原提議 ck-loki-tail 為新 skill；重新讀 ADR-0022 後發現 ck-observability-bridge 已涵蓋 Loki + Prometheus + Grafana + Alertmanager（範圍更廣）。本節改為提供**ADR-0022 Loki 子集的具體實作藍圖**：

**對應 ADR-0022 既有 tool**：`obs_loki_query` + `obs_loki_errors` + `obs_loki_briefing`

**本提案補強內容**：
- PoC 實證（`scripts/loki-tail-poc.py`）證明 Loki HTTP API 從 hermes-gateway 容器內可達（`host.docker.internal:13100`）
- **真實 alarm 偵測**：6h window 5000 ERROR-pattern 中辨識 1 條 `ck_missive_postgres_dev` FK constraint violation
- 揭露 noise 占比 99.4%（`ck-platform-node-exporter` metrics scrape）→ 提出 5 條 noise/假陽性改良策略：
  1. 預設排除 `ck-platform-node-exporter`
  2. LogQL `| level="error"` 用結構化 label 而非 text grep
  3. Regex 加 negative lookahead 過濾 `success/registered`
  4. `count_over_time` aggregations 取 hourly trend
  5. 結果分「真 ERROR / warning / filtered noise」三段

**併入位置**：`platform/services/docs/hermes-skills/ck-observability-bridge/{poc,references}/`

### G. unified-entry 路由

**做什麼**：所有前端（Telegram / Open WebUI / Missive 前端的 chat 元件）都打 `hermes-gateway:8642` OpenAI-compat API；hermes-gateway 依 query 內容 + 當前 profile 路由到對應 skill

**不做什麼**：
- ❌ 不取代各業務 agent 的功能性 endpoint（Missive `/api/...` 仍直連）
- ❌ 不 cache 業務回答（每次新 query 重打 Missive）
- ❌ 不 cross-agent talk（Missive agent 跟 LvrLand agent 不互通內部狀態，僅 Hermes Meta 萃取）

## 4. 落地節奏

| Phase | 時間 | 動作 | Owner |
|---|---|---|---|
| 1.0（已） | -2026-04-25 | 4 bridge skill 規範 + Master Plan v2 + Meta SOUL | hermes-agent + CK_AaaP |
| 1.1 | 1 週 | E `ck-adr-query` skill 實作（純讀，最低風險） | hermes-agent |
| 1.2 | 2 週 | F `ck-loki-tail` skill 實作（接 Loki HTTP API） | hermes-agent |
| 1.3 | 2 週 | G unified-entry 路由（gateway profile dispatch） | hermes-agent + CK_AaaP |
| 2.0 | 3-4 週 | Missive agent profile pilot（Master Plan v2 Phase 2） | 兩 session 協作 |

## 5. 風險矩陣

| 風險 | 影響 | 緩解 |
|---|---|---|
| Hermes 撞 ctx 64K（Loki tail 大量資料）| 高 | cron 模式而非 in-chat；script 預先過濾 ERROR-level |
| Prompt cache 一次 invalidate 7 個 skill | 中 | 三 skill 同 batch 部署（一次 cache rebuild） |
| ck-adr-query 看到的 ADR 與 registry 漂移 | 中 | skill 啟動時 check `REGISTRY.md` mtime；> 30 天標 stale |
| Loki tail 拉到敏感 PII（公文姓名）| 中 | skill side filter；不入 wiki，僅入 ephemeral briefing |
| 使用者「全知化」期待 vs 路由器姿態 | 低 | SOUL.md / 本 ADR 明文紀律；Meta agent 主動拒答業務 |

## 6. 驗收條件

| Phase | 驗收 |
|---|---|
| 1.1 | `hermes chat -q "為何 Missive 用 pgvector 768D"` → 30 秒內返回 FQID `CK_Missive#0006` 摘要 |
| 1.2 | 連續 7 天 Meta `briefings/YYYY-MM-DD.md` 含 Loki ERROR 段且非空 |
| 1.3 | Open WebUI 與 Telegram 同一問題回答一致（同 session 持久化） |

## 7. 不在本提案範圍

- 把 Showcase / DigitalTunnel repo 實質吃進 AaaP（屬 ADR-0020 Phase 2/3）
- Profile-as-Service 多 hermes-gateway 容器（屬 Master Plan v2 Phase 6+）
- Vital signs dashboard（待 Phase 7+，Semiont 啟發但「選擇性」）
- 任何付費 API 採用（違反零付費硬約束，永久 OUT OF SCOPE）

## 8. 給 CK_AaaP session 的採納清單

當 CK_AaaP session 採納本提案時：

1. ✅ 修訂 `CK_AaaP/adrs/0020-aaap-platform-with-hermes-control-plane.md` Phase 1 範圍段，加 E/F/G 三項
2. ✅ 新建 `CK_AaaP/adrs/0026-ck-adr-query-skill.md`、`0027-ck-loki-tail-skill.md`、`0028-unified-entry-routing.md`（proposed → 跑 generate-adr-registry.py）
3. ✅ docker-compose.yml 加 `--insecure` 到 hermes-web command（解本 session 撞到的 dashboard restart loop）
4. ✅ 通知 hermes-agent session：採納後可進 1.1 實作

## 9. Cross-ref

- 規範主源：`CK_AaaP/adrs/0020-aaap-platform-with-hermes-control-plane.md`
- 設計隱喻：`~/.hermes/profiles/meta/wiki/concepts/design-inspirations-muse-semiont.md`
- Master Plan：`hermes-agent/docs/plans/master-integration-plan-v2-2026-04-19.md`
- Skill 契約：`hermes-agent/docs/plans/hermes-skill-contract-v2.md`
- Crystal Seed（fork-able 模板）：`hermes-agent/docs/plans/crystal-seed-bootstrap.md`
