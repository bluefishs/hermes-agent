# ADR Stale Check 執行計劃（季度結算機制落地）

> **日期**：2026-04-30
> **執行 session**：CK_AaaP
> **對應 roadmap**：#15 ADR 季度結算 + 90 天 stale 警示
> **狀態**：腳本就緒 + ADR-0029 補充段提案

## 校正

- **ADR-0029（Governance Lessons Registry）2026-04-28 accepted** — 已是治理架構基礎
- 但**沒有 stale 自動偵測機制**——只有 lessons registry，無時間監控
- 本次 M 條補完 stale 自動掃描，與 ADR-0029 互補

## 已就緒

`docs/plans/adr-stale-check.py` — 165 行 Python 腳本，本機驗證通過：

```bash
$ python docs/plans/adr-stale-check.py --threshold 30
✅ ADR Stale Check passed (no in-flight ADR > 30d)
```

**功能**：
- 掃 6 個 repo 的 ADR 目錄（含 CK_AaaP / Missive / DigitalTunnel / PileMgmt / lvrland / Showcase）
- 找狀態為 `proposed/executing/Phase` 且 ≥ N 天前的 ADR
- 兩級嚴重度：`stale` (≥ 90d) / `critical` (≥ 180d)
- defer 豁免機制：ADR body 加 `**defer_until**: YYYY-MM-DD` 即跳過
- 三輸出格式：text / JSON / `--ci` 過 stale 即 exit 1

**設計優點**：
- 複用 generate-adr-registry.py 的 ADR parsing 邏輯（無重複造輪子）
- 採納時 import 即可，stand-alone 也能跑（fallback inline 解析）

## CK_AaaP session 採納步驟（30 min）

### Step 1 — 部署腳本

```bash
cd D:/CKProject/CK_AaaP

# 把腳本搬到 scripts/checks/ 子目錄
mkdir -p scripts/checks
cp ../hermes-agent/docs/plans/adr-stale-check.py scripts/checks/adr-stale-check.py
chmod +x scripts/checks/adr-stale-check.py

# 跑一次看現況
python scripts/checks/adr-stale-check.py --threshold 90
# 預期：列出所有 ≥ 90 天 in-flight ADR（如 #0015 NemoClaw 退場可能 critical）
```

### Step 2 — 整合到 check-doc-drift.sh CI 模式

```bash
# 編輯 scripts/check-doc-drift.sh，找 --ci 處理段，加：
#
#   # ADR stale check（per ADR-0029 補充段 / roadmap #15）
#   if [[ -f "$REPO_ROOT/scripts/checks/adr-stale-check.py" ]]; then
#       python "$REPO_ROOT/scripts/checks/adr-stale-check.py" --ci || EXIT_CODE=1
#   fi

# 驗證
bash scripts/check-doc-drift.sh 30 --ci
# 預期：exit 0（如無 90d+ stale）
```

### Step 3 — 補 ADR-0029 補充段（治理基線）

`adrs/0029-governance-lessons-registry.md` 末尾加新段「§ Stale Detection」：

```markdown
## § Stale Detection（2026-04-30 補強）

### 規範

ADR 從 proposed/executing 狀態起進入 90 天結算窗：

| 階段 | 範圍 | 動作 |
|---|---|---|
| Active | 0–89 天 | 正常推進 |
| **Stale** | 90–179 天 | 警示，要求季度結算（accept / reject / defer）|
| **Critical** | ≥ 180 天 | 強制決議；CI 過閘 |

### 三選一決議

| 動作 | 操作 |
|---|---|
| **Accept** | 狀態改 `accepted`，補 `**接受日期**: YYYY-MM-DD` |
| **Reject** | 狀態改 `rejected`，補 rationale 段（為何不採） |
| **Defer** | body 加 `**defer_until**: YYYY-MM-DD`（最多 90d）|

### 自動偵測

`scripts/checks/adr-stale-check.py` 掃 6 repo 全部 ADR，整合到 `check-doc-drift.sh --ci`。
過 stale 且未 defer → `exit 1`，CI 阻擋 PR merge。

### 範例

```bash
# CI 模式（門檻 90 天）
python scripts/checks/adr-stale-check.py --ci

# 手動季度檢視（門檻 30 天，強迫看到接近 stale 的）
python scripts/checks/adr-stale-check.py --threshold 30

# 機器可讀（接 dashboard）
python scripts/checks/adr-stale-check.py --json
```
```

### Step 4 — commit

```bash
git add scripts/checks/adr-stale-check.py \
        scripts/check-doc-drift.sh \
        adrs/0029-governance-lessons-registry.md
git commit -m "feat(governance): ADR stale auto-detection + ADR-0029 §Stale Detection (M / roadmap #15)

- adr-stale-check.py：掃 6 repo ADR，標 ≥90d in-flight 為 stale，≥180d 為 critical
- defer 豁免：ADR body 加 defer_until: YYYY-MM-DD 跳過
- 整合到 check-doc-drift.sh CI 模式（過 stale exit 1）
- ADR-0029 補 § Stale Detection 段，定義三選一結算流程

Refs: hermes-agent docs/plans/adr-stale-check.py
      hermes-agent docs/plans/adr-stale-check-execution-2026-04-30.md"
```

## 預期立即影響

跑 `--threshold 90` 預估會抓到（依 REGISTRY 在途 15 件）：

| FQID | 狀態 | 日期 | 預期 age（2026-04-30）|
|---|---|---|---|
| `CK_AaaP#0015` | 執行中 | 2026-04 | ~30d（未 stale）|
| `CK_AaaP#0017` | Phase | 2026-04-16 | 14d |
| `CK_AaaP#0018` | proposed | 2026-04-16 | 14d |
| `CK_AaaP#0019` | proposed | 2026-04-16 | 14d |
| `CK_AaaP#0020` | 執行中 | 2026-04-18 | 12d |
| ... | ... | ... | 全 < 90d |

**結論**：當前無 90d+ stale，腳本上線是「未來防線」而非立即清掃。

但若**改 30 天閾值**，會抓到上述全部 — 適合 M2 季度排程提醒：
```bash
# 季度警示（30 天「快滿」提醒，不擋 CI）
python scripts/checks/adr-stale-check.py --threshold 30
```

## 與 routine 的整合（可選）

未來可加 `schedule` 自動排程：
- 每月 1 號跑 `--threshold 60`，產生「下個月會 stale」清單，貼到 Slack/Telegram
- 每季 1 號跑 `--threshold 90 --ci`，列出必須結算項

## 變更歷史

- **2026-04-30** — 初版（hermes-agent session 起草）

## 相關文件

- `docs/plans/adr-stale-check.py` — 腳本本體
- `CK_AaaP/adrs/0029-governance-lessons-registry.md` — 治理架構 base
- `CK_AaaP/scripts/generate-adr-registry.py` — 複用的 parsing 邏輯
- `CK_AaaP/scripts/check-doc-drift.sh` — CI 整合點
