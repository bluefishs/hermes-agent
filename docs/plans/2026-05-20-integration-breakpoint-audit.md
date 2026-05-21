# Integration Breakpoint Audit — 2026-05-20

> 來源：[`2026-05-20-architecture-retro-execution-plan.md`](2026-05-20-architecture-retro-execution-plan.md) §9.2 第一波 ① 任務
> 目標：盤點 4 個 ADR-0020 Phase 1 bridge 從「工程已建」到「真實 user-facing」之間的**整合斷點**
> 模式：純讀取 + 跑既有 verify / unit test，不動代碼、不切 session、零費用
> Memory：[[feedback-integration-over-scope]]

---

## 0. 摘要

| 範疇 | 健康度 |
|---|---|
| CK_Hermes 端 4 native tool 程式碼 | 🟢 141 unit tests passed |
| CK_Hermes 端 mock e2e baseline | 🟢 4 passed / 2 skipped（skipped 為 LLM-driven，缺 env） |
| verify-bridges.py 本體 | 🟢 跑通，7 個 SKIP（無 env，預期）|
| **跨 repo 命名與配置一致性** | 🔴 **6 個明確斷點**（D1-D6，見 §2） |
| Production SKILL.md 覆蓋 | 🟡 5 個 bridge 中只有 3 個有 production SKILL.md（missive / pile / lvrland），observability / showcase 還在 plan stub 階段 |

**核心發現**：工程鋼樑已建，但 **3 套命名系統並存** + **observability env var 在 SKILL.md 與 native tool 之間分裂** + **SKILL.md `toolsets:` 欄位 4 個缺 1 個**。這些是「真實流程跑不通」的根因，不需要寫新代碼，只需要對齊配置。

---

## 1. 5 個 bridge 全貌一覽

| 元件 | ck-missive | ck-pile（PileMgmt）| lvrland | ck-observability | ck-showcase |
|---|---|---|---|---|---|
| **Production SKILL.md** | `CK_Missive/docs/hermes-skills/ck-missive-bridge/` ✅ | `CK_PileMgmt/docs/hermes-skills/ck-pile-bridge/` ✅ | `CK_lvrland_Webmap/docs/hermes-skills/lvrland-local/` ✅ | **❌ 不存在** | **❌ 不存在** |
| **CK_Hermes plan stub** | （無，直接 production） | `docs/plans/ck-pilemgmt-bridge-stub/SKILL.md` | `docs/plans/ck-lvrland-bridge-stub/SKILL.md` | `docs/plans/ck-observability-bridge-skeleton/SKILL.md` | `docs/plans/ck-showcase-bridge-stub/SKILL.md` |
| **CK_Hermes native tool** | `tools/missive_tool.py` ✅ | `tools/pilemgmt_tool.py` ✅ | **❌ 不存在**（lvrland 用 dynamic manifest） | `tools/observability_tool.py` ✅ | `tools/showcase_tool.py` ✅ |
| **SKILL `name:` 欄位** | `ck-missive-bridge` | `ck-pile-bridge` | `lvrland-local` | `ck-observability-bridge`（stub） | `ck-showcase-bridge`（stub） |
| **SKILL `toolsets:` 欄位** | ✅ `[missive]` | ❌ 缺 | ❌ 缺 | ❌ 缺（stub） | ❌ 缺（stub） |
| **SKILL env var 命名** | `MISSIVE_*` | `PILE_*` | `LVRLAND_*` | `OBS_*` | `SHOWCASE_*` |
| **native tool env var 命名** | `MISSIVE_*` ✅ | `PILE_*` ✅ | （無） | `OBSERVABILITY_*` ❌ | `SHOWCASE_*` ✅ |
| **verify-bridges.py env 命名** | `MISSIVE_*` | `PILE_*` | （未涵蓋） | `OBSERVABILITY_*` | `SHOWCASE_*` |
| **Unit test 數** | 34 | 29 | — | 42 | 36 |
| **狀態** | 🟢 全鏈一致，只缺 env | 🟡 SKILL 缺 toolsets，其餘對齊 | 🟡 缺 native tool，缺 toolsets | 🔴 env 命名分裂 + 無 production SKILL | 🔴 無 production SKILL |

---

## 2. 6 個整合斷點（D1-D6）

### 🔴 D1 — observability env var 命名分裂（嚴重，10 min 可修）

**現況**：
- `ck-observability-bridge-skeleton/SKILL.md` 教 user 設 `OBS_LOKI_URL`, `OBS_PROMETHEUS_URL`, `OBS_GRAFANA_URL`, `OBS_ALERTMANAGER_URL`
- `tools/observability_tool.py` 讀的是 `OBSERVABILITY_LOKI_URL`, `OBSERVABILITY_PROMETHEUS_URL`, `OBSERVABILITY_GRAFANA_URL`, `OBSERVABILITY_ALERTMANAGER_URL`
- `scripts/verify-bridges.py` 也用 `OBSERVABILITY_*`

**後果**：即使 user 按 SKILL.md 設了 `OBS_LOKI_URL=...`，native tool 讀不到，tool 自動 hidden（因為 `_base()` 回空字串）。**這條斷點即真實「LLM-driven e2e 跑不通」的根因之一**。

**修法**（二選一）：
- (a) 改 SKILL.md skeleton 用 `OBSERVABILITY_*`（與 native tool 對齊）
- (b) 改 native tool + verify script 用 `OBS_*`（與其他 bridge 命名長度一致，更簡潔）

推薦 (b)，但需確認沒有外部已配 `OBSERVABILITY_*` 的環境。

**修在哪**：本 session（CK_Hermes）可動 — 改 `tools/observability_tool.py` + `scripts/verify-bridges.py` + `docs/plans/ck-observability-bridge-skeleton/SKILL.md`

### 🔴 D2 — ck-observability-bridge / ck-showcase-bridge 缺 production SKILL.md（中等，30 min × 2 可修）

**現況**：
- 其他 3 bridge 都有 production SKILL.md 在對應 repo 的 `docs/hermes-skills/<bridge-name>/`
- observability 應在 `CK_AaaP/platform/observability/docs/hermes-skills/ck-observability-bridge/`（依 ADR-0025 觀測棧已遷入 AaaP）
- showcase 應在 `CK_AaaP/platform/services/docs/hermes-skills/ck-showcase-bridge/`（依 ADR-0020 Phase 2 已遷入 AaaP）

**後果**：deployment 路徑不明，install.sh 無對應 source。

**修法**：跨 session — CK_AaaP session 把 `CK_Hermes/docs/plans/ck-{observability,showcase}-bridge-{skeleton,stub}/` 升級為 production SKILL.md 並遷入 AaaP 對應位置。同時改命名：
- `ck-observability-bridge-skeleton` → `ck-observability-bridge`（去 skeleton 字樣）
- `ck-showcase-bridge-stub` → `ck-showcase-bridge`（去 stub 字樣）

**修在哪**：CK_AaaP session 動

### 🟡 D3 — lvrland 缺 hermes-agent 端 native tool（中等，需評估）

**現況**：
- `lvrland-local` SKILL.md 採「dynamic manifest 註冊 9 tools」模式，從 `GET /api/agent/tools` 拉
- CK_Hermes `tools/` 沒有 `lvrland_tool.py`
- 對比 ck-missive-bridge：雖也是 dynamic manifest，但 hermes-agent 端有 `missive_tool.py` 提供 fallback + 兩個 hardcoded tool（health / get_document）

**後果**：lvrland 無 fallback path，manifest 端點 down 時 hermes 端完全失能。

**修法**（需評估）：
- (a) 跟 missive 一樣補 `lvrland_tool.py` with `lvrland_health` + 一兩個 fallback tool
- (b) 或保持純 dynamic manifest，但確保 hermes runtime 對 dynamic-only skill 有 graceful 降級

**修在哪**：本 session（CK_Hermes）可寫 fallback tool；但需先決策

### 🟡 D4 — 3 個 production SKILL.md 缺 `toolsets:` 欄位（小，10 min × 3）

**現況**：
- `ck-missive-bridge/SKILL.md` v2.0 已有 `toolsets: [missive]` ✅
- `ck-pile-bridge/SKILL.md` 缺 ❌
- `lvrland-local/SKILL.md` 缺 ❌
- `ck-observability-bridge` / `ck-showcase-bridge` 還沒 production SKILL，併入 D2 處理

**後果**：sprint-b §「跨 repo」明確列為 LLM-driven e2e 的瓶頸之一。hermes runtime 載 skill 時無 `toolsets:` 可能影響工具歸群顯示。

**修法**：跨 session — 各對應 repo session 加 frontmatter
- `CK_PileMgmt` session：在 `ck-pile-bridge/SKILL.md` 加 `toolsets: [pile]`
- `CK_lvrland_Webmap` session：在 `lvrland-local/SKILL.md` 加 `toolsets: [lvrland]`

**修在哪**：跨 2 個 repo session

### 🟡 D5 — pytest config 卡 xdist 缺失（小，5 min 可修）

**現況**：
- `pyproject.toml`：`addopts = "-m 'not integration' -n auto"`
- 環境未裝 `pytest-xdist`
- 結果：`python -m pytest ...` 直接 ERROR `unrecognized arguments: -n`
- workaround：每次都要加 `-o addopts=""`，極差體驗

**附帶**：每次跑都有 `HERMES_HOME fallback` warning，但功能不受影響

**修法**（二選一）：
- (a) `pyproject.toml` 拿掉 `-n auto`（每次跑單 worker）
- (b) `pyproject.toml [project.optional-dependencies]` 加 `pytest-xdist` 並文件指引 user 跑 `pip install -e ".[dev]"`

推薦 (b)，但需確認 pyproject.toml extras 結構

**修在哪**：本 session（CK_Hermes）可動

### 🟢 D6 — verify-bridges.py 本體 OK，但 lvrland 沒涵蓋（資訊）

**現況**：verify-bridges.py 只 probe 4 個 bridge（missive / observability / showcase / pilemgmt），沒涵蓋 lvrland

**後果**：lvrland production 上線後無單一 verify 入口

**修法**：本 session 加 `probe_lvrland()` + `LVRLAND_BASE_URL` env，跟其他一致

**修在哪**：本 session（CK_Hermes）可動

---

## 3. 修復順序與依賴

```
立即可動（本 session，CK_Hermes 範圍）：
  D1 observability env 對齊  ←  推薦 (b)：改 native tool + verify script + skeleton SKILL.md 用 OBS_*
  D5 pytest -n auto 拿掉    ←  推薦 (a) 簡單修，或 (b) 加 extras
  D6 verify 加 lvrland probe ←  跟其他 bridge 一致

需要跨 session：
  D2 ck-observability/showcase production SKILL.md 落地  →  CK_AaaP session
  D4 ck-pile / lvrland 加 toolsets:                      →  CK_PileMgmt / CK_lvrland_Webmap session

待評估後再動：
  D3 lvrland fallback tool                              →  本 session 可寫，但先決策保 dynamic 還是補 fallback
```

---

## 4. 對 v2 計畫的修正

執行計畫 §9.2 第一波 **② A-5 + 補 SKILL.md frontmatter** 的真實內容應為：

| 步驟 | 動作 | 目標斷點 | session | 工時 |
|---|---|---|---|---|
| ②-1 | D1 observability env 對齊（改 3 處）| D1 | CK_Hermes（本）| 10 min |
| ②-2 | D5 pytest config 修 | D5 | CK_Hermes（本）| 5 min |
| ②-3 | D6 verify 加 lvrland probe | D6 | CK_Hermes（本）| 10 min |
| ②-4 | hermes-stack/.env 注入 4 個（或 5 個，含 lvrland）`*_BASE_URL`| 配置 | CK_AaaP | 30 min |
| ②-5 | D2 ck-observability/showcase 升 production SKILL.md | D2 | CK_AaaP | 30 min × 2 |
| ②-6 | D4 ck-pile + lvrland 加 toolsets | D4 | CK_PileMgmt + CK_lvrland_Webmap | 10 min × 2 |
| ②-7 | D3 lvrland fallback tool（待決策） | D3 | CK_Hermes（本，待決策） | 30 min（若做）|

→ 第一波 ② 從原本「1h」實際工時 = 2-3h（含跨 session），但能確保 ④ 真實端到端跑通

---

## 5. 結論

**「分散虛功」的具體形態**：
- 11 個 native tool 已 commit、141 unit tests 通過、4 mock e2e 通過 — 工程完成度高
- 但 5 套命名（SKILL name / SKILL env / tool env / verify env / tool file 名）在不同地方各自演化
- 3 個 bridge 中只有 1 個（missive）有完整一致的全鏈路（SKILL ↔ tool ↔ verify ↔ env）
- 沒有單一 SSOT 收斂這個對齊（沒有 BRIDGE_CONTRACT.md 或類似）

**最小可動修復**：D1 + D5 + D6 + ②-4 ②-5 ②-6 = 約 2-3h 跨 session，就能讓「對話：Missive 還好嗎」第一次跑通。

---

## 6. 等待用戶授權

本 session（CK_Hermes）可立即動的三項：

- **D1 observability env 對齊**（10 min）
- **D5 pytest config 修**（5 min）
- **D6 verify 加 lvrland probe**（10 min）

合計 25 min，純 CK_Hermes 內部，不切 session、不產生費用。

D3 lvrland fallback tool（30 min）需先決策保 dynamic 還是補 fallback。

是否授權立即動 D1 / D5 / D6？D3 是否做？

---

## 7. 第一波執行結果（2026-05-21）

用戶於 2026-05-21 授權「依前述規劃辦理」。執行：

| ID | 狀態 | 變更 | 驗證 |
|---|---|---|---|
| **D1** | ✅ 完成 | `tools/observability_tool.py` + `tests/tools/test_observability_tool.py` + `scripts/verify-bridges.py` 全部從 `OBSERVABILITY_*` → `OBS_*`（含 `OBS_TIMEOUT_S`、`OBS_GRAFANA_USER/PASS`）| `pytest test_observability_tool.py` 42 passed |
| **D5** | ✅ 完成 | `pyproject.toml` `addopts = "-m 'not integration'"`（拿掉 `-n auto`） | `pytest` 直跑無須 `-o addopts=""` |
| **D6** | ✅ 完成 | `scripts/verify-bridges.py` 加 `probe_lvrland` + `LVRLAND_BASE_URL`（含可選 `LVRLAND_API_TOKEN`） | `python scripts/verify-bridges.py` 8 個 probe（原 7 + lvrland） |
| **D3** | ⬜ 暫不做 | 待真實流程跑通後再決策（保 dynamic 還是補 fallback） | — |

**整體 regression 驗證**：4 bridge tool tests + missive e2e 一次跑 → **145 passed, 2 skipped, 0 failed**（5.20s）

### 7.1 解凍狀態對應

- D1 解 → **ck-observability-bridge 全鏈一致**（SKILL.md ↔ tool ↔ verify ↔ env），從「user 設了 OBS_LOKI_URL，tool 讀 OBSERVABILITY_LOKI_URL 讀不到」改為「對齊」
- D5 解 → 任何 hermes-agent contributor 跑 pytest 不再卡 xdist 缺失
- D6 解 → lvrland 跟其他 4 bridge 一視同仁，未來 lvrland 上線後 verify-bridges.py 一次涵蓋 5 bridge
- D3 留 → 等 LLM-driven e2e 跑通 lvrland-local dynamic manifest 後再決定要不要補 fallback

### 7.2 餘下跨 session 動作（不在本 session 範圍）

剩餘需切 session 動作（不重複 sprint-a/sprint-b 已列）：
- **D2 production SKILL.md 落地**（CK_AaaP session）：升 `docs/plans/ck-observability-bridge-skeleton/` → `CK_AaaP/platform/observability/docs/hermes-skills/ck-observability-bridge/`；同樣處理 ck-showcase
- **D4 toolsets 欄位補齊**（CK_PileMgmt + CK_lvrland_Webmap session）：各加 `toolsets: [pile]` / `toolsets: [lvrland]` frontmatter
- **hermes-stack/.env 注入 5 個 `*_BASE_URL`**（CK_AaaP session）：對應 ②-4
- **真實端到端跑通**（CK_AaaP session + 用戶 Ollama fallback）：對應 v2 計畫第一波 ③ + ④

### 7.3 v2 計畫進度

| 第一波 | v2 計畫項 | 狀態 |
|---|---|---|
| ① 整合斷點清單 | §9.2 ① | ✅ 完成（本檔本身）|
| ② 配置對齊（CK_Hermes 內部部分） | §9.2 ② → ②-1 / ②-2 / ②-3 | ✅ 完成（D1/D5/D6）|
| ② 跨 session 部分 | §9.2 ② → ②-4 / ②-5 / ②-6 | ⬜ 待 CK_AaaP / CK_PileMgmt / CK_lvrland session |
| ③ Ollama fallback 啟動 | §9.2 ③ | ⬜ 待 CK_AaaP session + 用戶 |
| ④ 真實端到端 | §9.2 ④ | ⬜ 等 ②-4-6 + ③ |
| ⑤ M-2 commit | §9.2 ⑤ | ⬜ 待 CK_Missive session |
