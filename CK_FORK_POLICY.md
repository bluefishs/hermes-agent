# CK_Hermes Fork Policy

> 版本：v1.0 · 2026-05-22 · CK_Hermes session 寫於第三波架構覆盤後
> 觸發：2026-05-20 retro §H-1、2026-05-22 L21 揭穿 hermes runtime dispatching bug
> Memory：[[feedback-integration-over-scope]]、[[feedback-pre-demo-functional-verification]]

## 0. 為什麼需要這份政策

CK_Hermes 是 NousResearch/hermes-agent 的 fork（remote: `origin` = NousResearch，`fork` = bluefishs）。

在 2026-05-22 之前，CK 增量改動沒有書面約束 — 結果是：
- 第一年所有 CK 增量都集中在 **新增檔案**（`tools/{missive,observability,showcase,pilemgmt}_tool.py` + `tests/` + `scripts/verify-bridges.py` + `pyproject.toml` 一行 `metrics` extra），近乎「零侵入」
- 但 L21（2026-05-22）首次出現「**需要修 upstream 既存代碼**」的 signal — `gateway/platforms/api_server.py` 或 `gateway/run.py` 的 provider 解析鏈可能要改
- 沒有政策即會出現「Plugin / patch / 新檔」三種策略無原則選用，產生 upstream merge 衝突且難復現

這份政策為今後所有「CK 增量是否合理、如何落地」提供決策框架。

---

## 1. 三層增量策略（優先序）

| 層級 | 形態 | 對 upstream 風險 | 適用場景 |
|---|---|---|---|
| **L1 新檔（zero-touch）** | 新增 `tools/*_tool.py`、`tests/`、`scripts/`、`docs/plans/`、`CK_*.md` | ✅ 零衝突 | 預設選擇 — 4 個 bridge native tool 全部走這條 |
| **L2 Plugin / Skill** | `plugins/`、`skills/`、`~/.hermes/profiles/*/skills/` | ✅ 零衝突（upstream 已設計 extension surface） | 行為擴展 — 例：CK 客製 cron prompts、ck-missive-bridge SKILL |
| **L3 Patch upstream 既存檔** | 改 `gateway/`、`agent/`、`run_agent.py`、`hermes_cli/` 等核心 | 🔴 高（每次 weekly rebase 都可能衝突） | **僅限**：upstream bug + PR 已提 / `entry-point` 變動需校準 / 無法用 plugin 點達成 |

**默認順序**：嘗試 L1 → 嘗試 L2 → **明確 ADR 通過**才走 L3。

---

## 2. L3 Patch 准入準則

任何 L3 patch（改 upstream 既存 `.py` / `.ts` 檔）必須同時滿足：

1. **問題已確認在 upstream**：用 `git log --no-merges -- <file>` 確認受影響行近期非 CK 自己改的
2. **無 L1/L2 替代**：書面說明為何 plugin / skill / 新檔不可行
3. **回饋 upstream PR**：開 GitHub Issue / PR 到 `NousResearch/hermes-agent`，連結附在 CK_Hermes ADR 中
4. **CK ADR proposed**：寫成 `docs/plans/adr-N-<topic>.md`（編號接續，不混入 CK_AaaP 的 ADR-NNNN 命名空間）
5. **rebase 計畫**：說明 weekly rebase 時若 upstream 修了同行如何處理（abandon CK patch / 改 plugin / 維持衝突解）

L21 是首個 L3 候選，將觸發 ADR-CK-001（見 §6）。

---

## 3. CK 客製化清單盤點（2026-05-22 snapshot）

依本政策回溯既存 CK 增量歸類：

| 元件 | 類型 | 檔案 | 狀態 |
|---|---|---|---|
| ADR-0020 Phase 1 native tools | L1 | `tools/{missive,observability,showcase,pilemgmt}_tool.py` | ✅ 已落地，3 ✅ + 1 D1 fix |
| Bridge unit tests | L1 | `tests/tools/test_{...}_tool.py` | ✅ 141 passed |
| Bridge mock e2e | L1 | `tests/e2e/test_missive_bridge_e2e.py`、`test_missive_bridge_llm_e2e.py` | ✅ 60 passed + 9 skipped |
| `verify-bridges.py` | L1 | `scripts/verify-bridges.py` | ✅ 8 probe |
| `metrics` extra | L3（最小） | `pyproject.toml` 一行 `[project.optional-dependencies] metrics = [...]` | ⚠️ upstream merge 時若 extras 區塊有改要對齊（2026-05-16 已對齊一次）|
| `addopts` 去 `-n auto` | L3（最小） | `pyproject.toml` | ⚠️ upstream `pytest-xdist` 哪天進默認 dev 依賴就可回退 |
| `.gitignore` CK 區塊 | L1（純 append） | `.gitignore` 末段 `# CK fork` | ✅ |
| Plan 文件 | L1 | `docs/plans/**` | ✅ 不影響 runtime |
| `CK_FORK_POLICY.md` | L1（meta） | 本檔 | ✅ |
| L21 候選 patch | **未動** — 待 ADR-CK-001 決策 | `gateway/platforms/api_server.py` 或 `gateway/run.py` | 🔴 待診斷 |

**結論**：截至 2026-05-22，CK fork 僅 2 處 L3（pyproject 兩行），其餘全為 L1。L21 若需 L3，將是首次有實質 runtime 補丁。

---

## 4. Upstream rebase 節奏

| 動作 | 頻率 | SOP |
|---|---|---|
| `git fetch origin` | 每次 session 啟動 | 不自動 merge，只看落差 |
| **正式 merge** | weekly（建議週五）or 重大 upstream fix 時 | 依 §5 流程 |
| **merge 前快照** | 每次 merge 前 | `git tag ck-pre-merge-YYYYMMDD` 留回退錨 |
| **CI 紅燈處理** | 立即 | 不繼續疊 CK commit，先 revert merge 修通再來 |

L3 patch 在 rebase 時優先順序：
1. 若 upstream 已修同 bug → **abandon** CK patch，加 ADR 結束條目
2. 若 upstream 改了同檔但非同 bug → 手動 cherry-pick CK patch
3. 若 upstream 完全沒動 → patch 自動保留

---

## 5. Upstream merge 衝突 SOP

```
1. git fetch origin
2. git checkout -b ck-merge-YYYYMMDD
3. git tag ck-pre-merge-YYYYMMDD            # 回退錨
4. git merge origin/main
5. 衝突檔分類：
   - pyproject.toml / 配置：依「upstream 為準 + CK 增量保留」原則對齊
   - L3 patch 衝突：依 §4 三選一
   - L1 衝突（不該發生）：標記為 incident，事後 ADR
6. 跑 pytest 完整 suite，記錄 regression
7. 寫 merge commit body：commits since 上次 merge、衝突分類、L3 patch 狀態
8. 推 fork/main
9. 若 7 天內無 regression report → tag stable-YYYYMMDD
```

最近一次依此 SOP 落地：2026-05-16 `54a97ad9c Merge origin/main`（771 commits），衝突 2 處（.gitignore / pyproject.toml）。

---

## 6. 與既存治理的關係

| 治理面 | 既存資產 | 本政策連結點 |
|---|---|---|
| 跨 repo ADR | `CK_AaaP/adrs/REGISTRY.md`（ADR-NNNN namespace） | **CK_Hermes fork 內部 ADR 用 `ADR-CK-NNN`**（不混入 0001-9999 namespace，避免 ADR 編號跨 repo 碰撞 — 既存 14 處碰撞已是教訓） |
| ADR-0020 Phase 1 | bridge tools | 本政策 §3 表列 |
| L21（runtime dispatching） | feedback memory + 待寫 patch plan | 將成為 **ADR-CK-001**：第一個 L3 patch 案例 |
| CONVENTIONS.md §7 | session 工作目錄分流 | 本政策不重複，依其要求「CK_Hermes session 從 `D:\CKProject\CK_Hermes\` 啟」 |

---

## 7. 例外條款

以下情況可不依本政策（仍需事後紀錄）：

- **upstream 已 merge 修同 bug 但尚未 release**：可暫 cherry-pick 過渡，下次 weekly rebase 自動失效
- **安全漏洞**：CVE / 已揭露 0day，先 patch 後 ADR（48h 內補）
- **CI 卡關**：upstream CI script 在 Windows 上失敗，可加 skip 條件，要 issue 回上游

---

## 8. 維護

- 本政策 quarterly review（每季）
- §3 客製化清單每次新增 CK 增量同 PR 更新
- L3 patch 累積 ≥ 5 個時觸發政策 v2 評審

---

## 關聯

- 第三波 retro：[`docs/plans/2026-05-20-architecture-retro-execution-plan.md`](docs/plans/2026-05-20-architecture-retro-execution-plan.md) §H-1
- 整合斷點審計：[`docs/plans/2026-05-20-integration-breakpoint-audit.md`](docs/plans/2026-05-20-integration-breakpoint-audit.md)
- Memory：[[feedback-integration-over-scope]]、[[feedback-pre-demo-functional-verification]]
- L21 lesson（待寫）：[[lesson-hermes-runtime-dispatching-bug-2026-05-22]]
