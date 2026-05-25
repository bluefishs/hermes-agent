---
name: ck-platform-context
description: >
  AaaP 平臺元資料動態查詢 — 提供 SSOT 列管專案、四塔覆蓋率、整合健康度等
  治理層 context。用於「列管系統清單 / 受管專案 / 四塔分別 / 哪些專案有
  hermes_bridge / 整合健康度」等 SSOT meta 問題。動態 dispatch 取代 SOUL
  注入（避免 prompt 膨脹 → 慢的反效果，見 lesson-l21 §2.5）。
toolsets: [aaap]
when_to_use: |
  使用者問及以下任一即呼叫 `aaap_get_ssot_context`：
  - 列管系統 / 受管專案 / managed projects 清單
  - AaaP 平臺四塔 / 管理塔 / 監控塔 / 控制塔 / 入口塔
  - 跨專案 integration_status / hermes_bridge / cf_tunnel 覆蓋率
  - 特定專案的 phase / maturity / subdomain
  - 「Phase 2.5 / Phase 3-A」等 SSOT 治理問題

  ❌ 不使用本工具的場景（轉 domain bridge 或觀測塔）：
  - live 業務數據（Missive Postgres 用量、commit 紀錄）
  - 即時 metrics（CPU / 記憶體 / 請求數）
  - 單一專案內部細節（document 內容、文章查詢）
when_not_to_use: |
  - 純對話 / 寒暄 / 個人化問題
  - 與 AaaP 無關的通用知識題
---

# ck-platform-context — AaaP SSOT 動態查詢

## 背景

2026-05-22 嘗試把 SSOT 受管清單嵌入 SOUL.md 失敗 — 1.2KB SOUL 增量造成
Hermes path 從 51s 漲到 >120s timeout（hermes runtime 每次 chat 都注入
14k+ prompt tokens，SOUL 改動 × Ollama qwen2.5:7b 處理速度 = 全域延遲爆炸）。

ADR-CK-003 v2 改用 **dynamic tool dispatch** 取代 SOUL 注入：
- SOUL 維持精簡（人格 + 行為原則）
- SSOT 元資料以 tool call 動態取
- 只有問到 SSOT 問題時 LLM 才呼叫，**不每次 chat 付 prompt 稅**

## 提供的 tools

### `aaap_get_ssot_context`

**輸入**：
- `query` (string, optional) — 專案名 substring filter（case-insensitive）；
  空字串或不填 = 回所有 8 個專案 + 四塔覆蓋率

**輸出**：JSON `{summary: <markdown text>, projects_returned: <count>}`

**範例輸出**（query=""）：
```
=== CK_AaaP 平臺（SSOT v1.6.1）===
整合健康度: 60  (6/8 active projects)

四塔覆蓋率:
  - governance: ...
  - observability: ...
  - control_plane: ...
  - gateway: ...

=== 8 個 SSOT 列管專案 ===
- CK_GPS_v3 [deprecated/legacy] subdomain=— cf=none bridge=none
    控制樁位管理系統 v3
- CK_Missive [active/high] subdomain=missive.cksurvey.tw cf=missive.cksurvey.tw bridge=ck-missive-bridge-v2.0
    訊息服務專案
...
```

## 環境設定

| Env | 必需 | 預設 | 說明 |
|---|---|---|---|
| `AAAP_BASE_URL` | ✅ | — | AaaP backend 入口（容器內 `http://host.docker.internal:5201`）|
| `AAAP_API_TOKEN` | optional | — | 預留 Bearer auth |
| `AAAP_TIMEOUT_SECONDS` | optional | `10` | HTTP timeout |

當 `AAAP_BASE_URL` 未設，整個 toolset 自動 hidden（用戶 / hermes runtime 都看不到）。

## 與其他 bridge 的關係

| 對象 | 關係 |
|---|---|
| `ck-missive-bridge` | 互補 — platform-context 答「Missive 是哪個 phase/maturity」（治理層）；missive-bridge 答「Missive 那份合約內容是什麼」（業務層）|
| `ck-observability-bridge` | 互補 — platform-context 答「監控塔有哪些元件」；observability-bridge 查具體 Prometheus / Grafana metrics |
| `ck-showcase-bridge` | 取代 — Showcase 已於 Phase 2 併入 AaaP，platform-context 直取 SSOT 是更直接的路徑 |

## 變更歷史

- v1.0 (2026-05-25) — Initial ADR-CK-003 v2 落地，取代 v1（SOUL 注入失敗實驗）
