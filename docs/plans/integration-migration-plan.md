# CK_AaaP × hermes-agent 整合移轉藍圖

> **狀態**：blueprint（hermes-agent session 起草，由 CK_AaaP session 接力執行）
> **產生**：2026-04-25
> **規範源**：ADR-0020 + Master Plan v2 + ADR-0020 Phase 1 擴範圍提案
> **設計隱喻**：Taiwan.md 概念 — 各 agent = Muse / Hermes Meta = taiwan.md 集體有機體
> **硬約束**：零付費 / Missive-first / 繁中 zh-TW / Session 工作目錄分流

## 0. 為何要做這件事

當前狀況：
- hermes-agent fork 累積 12 份 `docs/plans/*.md` + 1 份 `scripts/adr-query-poc.py` — 大部分是 **CK 治理性內容**，污染 fork 的 upstream-clean 紀律
- CK 治理 ADR / Runbook / skill source-of-truth 散在 4 處（hermes-agent / CK_AaaP / CK_Missive / 各業務 repo）
- 缺少統一「跨 repo 移轉協議」，每次想搬東西都要重討論

整合目標：
- **hermes-agent** = pure upstream-clean **runtime engine**（只放程式碼補丁 + 與 fork 維護有關的文件）
- **CK_AaaP** = 治理 + 平台基礎，**所有 CK 業務 / 跨 repo / 平台計畫的 source of truth**
- **各 domain repo**（CK_Missive / CK_PileMgmt / ...）= 各自 `SOUL.md` + `docs/hermes-skills/ck-<domain>-bridge/`
- **`~/.hermes/`** = host runtime，大部分為 symlink 指向 source of truth

## 1. 檔案分類矩陣

### 1.1 移到 CK_AaaP（治理 / 跨 repo / 平台計畫）

| 來源（hermes-agent） | 目標（CK_AaaP） | 理由 |
|---|---|---|
| `docs/plans/master-integration-plan-v2-2026-04-19.md` | `CK_AaaP/docs/plans/master-integration-plan-v2.md` | 跨 repo 主計畫 |
| `docs/plans/adr-0020-phase1-extension-proposal.md` | `CK_AaaP/docs/plans/adr-0020-phase1-extension-proposal.md`（採納時轉為 ADR-0026/0027/0028）| 治理提案 |
| `docs/plans/skill-ck-adr-query-design.md` | `CK_AaaP/docs/hermes-skills/ck-adr-query/SKILL.md` + `references/design.md` | Skill source of truth（per ADR-0018） |
| `scripts/adr-query-poc.py` | `CK_AaaP/docs/hermes-skills/ck-adr-query/poc/adr-query-poc.py` | Skill 實作前置 |
| `docs/plans/cron-prompts.md` | `CK_AaaP/runbooks/hermes-stack/cron-prompts.md` | hermes-stack 部署資產 |
| `docs/plans/crystal-seed-bootstrap.md` | `CK_AaaP/runbooks/crystal-seed/README.md` | 對外 fork-able 模板 |
| `docs/plans/soul-templates/meta.soul.md` | `CK_AaaP/runbooks/hermes-stack/SOUL.meta.md`（已激活，作 canonical 留底）| Meta SOUL 模板 |
| `docs/plans/soul-templates/missive.soul.md` | `CK_Missive/SOUL.md`（屬 CK_Missive session 寫入）| Missive SOUL canonical |
| `docs/plans/soul-templates/showcase.soul.md` | `CK_AaaP/runbooks/soul-templates/showcase.soul.md`（暫存，等 Phase 6 採納時遷至 CK_Showcase/SOUL.md，但 ADR-0020 計畫 Showcase 歸入 AaaP，可能直接落 `CK_AaaP/SOUL.showcase.md`）| 待 ADR-0020 Phase 2 釐清 |
| `docs/plans/soul-templates/lvrland.soul.md` | `CK_AaaP/runbooks/soul-templates/lvrland.soul.md`（暫存，等 Phase 6） | 同上 |
| `docs/plans/soul-templates/pile.soul.md` | `CK_AaaP/runbooks/soul-templates/pile.soul.md`（暫存，等 Phase 6） | 同上 |

### 1.2 保留於 hermes-agent（fork 維護 / upstream 互動）

| 檔案 | 理由 |
|---|---|
| `docs/plans/upstream-sync-cadence.md` | fork 自身節奏 |
| `docs/plans/upstream-sync-2026-04-25.md` | fork sync 紀錄 |
| `docs/plans/upstream-feature-eval-2026-04-18.md` | upstream 功能評估 |
| `docs/plans/upstream-pr-entrypoint-chown.md` | 即將送 NousResearch 的 PR |
| `docs/plans/upstream-pr-web-build.md` | 早期 PR draft |
| `docs/plans/hermes-skill-contract-v2.md` | hermes-agent 實作者 quick reference |
| `docs/plans/integration-migration-plan.md` | **本檔**（移轉協議；移轉完成後再決定是否搬走） |

### 1.3 Runtime（`~/.hermes/`）— host-specific，**不**進 git repo

| 檔案 | 處理 |
|---|---|
| `~/.hermes/SOUL.md`（CK 助理 v1）| 保持 host file，不動；移轉完成後改成 symlink → `CK_AaaP/runbooks/hermes-stack/SOUL.md`（CK_AaaP canonical） |
| `~/.hermes/profiles/meta/SOUL.md`（已激活）| 移轉完成後改 symlink → `CK_AaaP/runbooks/hermes-stack/SOUL.meta.md` |
| `~/.hermes/profiles/meta/wiki/`（13 concept + log + daily + briefings）| 保持 host file，**不入 repo**（含使用者私人模式辨識，不適合公開） |
| `~/.hermes/skills/`（runtime skill 部署）| 由 `install.sh` 從各 source of truth 部署 |
| `~/.hermes/cron/jobs.json`（cron 持久化）| 保持 host file |

## 2. 三階段執行（雙寫 → 切換 → 清理）

### Phase A — 雙寫期（1-2 週）

**目標**：CK_AaaP 取得所有檔案，原 hermes-agent 副本**保留**作為回滾依據。

由 **CK_AaaP session** 執行：

```bash
cd D:/CKProject/CK_AaaP

# 1. 建立目標目錄
mkdir -p docs/plans
mkdir -p docs/hermes-skills/ck-adr-query/poc
mkdir -p docs/hermes-skills/ck-adr-query/references
mkdir -p runbooks/crystal-seed
mkdir -p runbooks/soul-templates

# 2. 複製跨 repo 計畫（不 git mv，因跨 repo 用 cp）
cp ../hermes-agent/docs/plans/master-integration-plan-v2-2026-04-19.md \
   docs/plans/master-integration-plan-v2.md

cp ../hermes-agent/docs/plans/adr-0020-phase1-extension-proposal.md \
   docs/plans/adr-0020-phase1-extension-proposal.md

# 3. 複製 skill source of truth
cp ../hermes-agent/docs/plans/skill-ck-adr-query-design.md \
   docs/hermes-skills/ck-adr-query/references/design.md

cp ../hermes-agent/scripts/adr-query-poc.py \
   docs/hermes-skills/ck-adr-query/poc/adr-query-poc.py

# 4. 複製 hermes-stack 資產
cp ../hermes-agent/docs/plans/cron-prompts.md \
   runbooks/hermes-stack/cron-prompts.md

cp ../hermes-agent/docs/plans/crystal-seed-bootstrap.md \
   runbooks/crystal-seed/README.md

# 5. 複製 SOUL templates
cp ../hermes-agent/docs/plans/soul-templates/meta.soul.md \
   runbooks/hermes-stack/SOUL.meta.md.template

cp ../hermes-agent/docs/plans/soul-templates/showcase.soul.md \
   runbooks/soul-templates/showcase.soul.md
cp ../hermes-agent/docs/plans/soul-templates/lvrland.soul.md \
   runbooks/soul-templates/lvrland.soul.md
cp ../hermes-agent/docs/plans/soul-templates/pile.soul.md \
   runbooks/soul-templates/pile.soul.md

# missive.soul.md 屬 CK_Missive session（寫到 CK_Missive/SOUL.md）

# 6. 修檔內 cross-ref 路徑（hermes-agent → CK_AaaP）
# 用 sed 或 manual 替換以下 pattern：
#   `docs/plans/skill-ck-adr-query-design.md` → `docs/hermes-skills/ck-adr-query/references/design.md`
#   `scripts/adr-query-poc.py` → `docs/hermes-skills/ck-adr-query/poc/adr-query-poc.py`
#   `docs/plans/master-integration-plan-v2-2026-04-19.md` → `docs/plans/master-integration-plan-v2.md`

# 7. Commit
git add docs/ runbooks/
git commit -m "feat(integration): import hermes-agent governance/skill/runbook artifacts (Phase A)

- docs/plans/: master plan v2, ADR-0020 Phase 1 extension proposal
- docs/hermes-skills/ck-adr-query/: skill design + PoC (source of truth per ADR-0018)
- runbooks/hermes-stack/cron-prompts.md, SOUL.meta.md.template
- runbooks/crystal-seed/README.md (fork-able stack template)
- runbooks/soul-templates/: showcase/lvrland/pile drafts

hermes-agent originals preserved during 2-week dual-write window."

# 8. 通知 hermes-agent session：Phase A 完成，可進 Phase B
```

由 **CK_Missive session** 執行（並行於 CK_AaaP）：

```bash
cd D:/CKProject/CK_Missive
cp ../hermes-agent/docs/plans/soul-templates/missive.soul.md SOUL.md

# 編輯 SOUL.md 以符合 CK_Missive 真實 persona（Muse-like 業務 agent）
# Commit
git add SOUL.md
git commit -m "feat(soul): adopt missive agent SOUL canonical"
```

### Phase B — 切換期（1 週）

**目標**：CK_AaaP 文件成為唯一被引用的 source of truth；hermes-agent 副本標 deprecated。

由 **hermes-agent session** 執行：

```bash
cd D:/CKProject/hermes-agent

# 1. 在 hermes-agent 副本頂端加 deprecation banner
for f in docs/plans/master-integration-plan-v2-2026-04-19.md \
         docs/plans/adr-0020-phase1-extension-proposal.md \
         docs/plans/skill-ck-adr-query-design.md \
         docs/plans/cron-prompts.md \
         docs/plans/crystal-seed-bootstrap.md; do
  sed -i '1i\
> ⚠️ **DEPRECATED** — 已移至 CK_AaaP；此副本將於 2026-05-09 刪除\
> Source of truth：見 CK_AaaP 對應檔（grep `migrated-to:` 查目標路徑）\
\
' "$f"
done

# 2. 同樣在 soul-templates/*.md 加 banner

# 3. Commit
git add docs/plans/
git commit -m "chore(integration): mark hermes-agent CK governance docs as deprecated (Phase B)

CK_AaaP now the source of truth. Originals retained for 2 weeks for rollback.
Removal scheduled 2026-05-09."

git push fork main
```

由 **使用者** 執行（人為驗證）：
- [ ] CK_AaaP 副本可被 ADR registry script 找到
- [ ] CK_AaaP 副本內 cross-ref 連結都通
- [ ] hermes-stack 容器 restart 後讀新位置正常（cron-prompts、SOUL templates）

### Phase C — 清理期（移轉完成後 1 週）

**目標**：刪除 hermes-agent 副本，fork 回到 upstream-clean。

由 **hermes-agent session** 執行（**等使用者 2026-05-09 之後明確授權**）：

```bash
cd D:/CKProject/hermes-agent

# 1. 刪除已移轉的檔案
git rm docs/plans/master-integration-plan-v2-2026-04-19.md
git rm docs/plans/adr-0020-phase1-extension-proposal.md
git rm docs/plans/skill-ck-adr-query-design.md
git rm docs/plans/cron-prompts.md
git rm docs/plans/crystal-seed-bootstrap.md
git rm -r docs/plans/soul-templates/
git rm scripts/adr-query-poc.py

# 2. 保留：upstream-* / hermes-skill-contract-v2 / integration-migration-plan(本檔)

# 3. Commit
git commit -m "chore(integration): remove migrated CK governance artifacts (Phase C)

Files now live in CK_AaaP under docs/plans/, docs/hermes-skills/, runbooks/.
hermes-agent fork reverts to upstream-clean engine-only role."

git push fork main
```

### Phase D — Runtime symlink 安排（移轉完成後）

由 **使用者** 或 **hermes-agent session** 執行（取決於 host 路徑可達性）：

```bash
# Windows host：用 mklink 或 PowerShell New-Item -ItemType SymbolicLink
# 或 Linux/WSL2：ln -s

# 1. 根 SOUL → CK_AaaP runbook canonical
mv ~/.hermes/SOUL.md ~/.hermes/SOUL.md.bak
ln -s /d/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md ~/.hermes/SOUL.md

# 2. Meta SOUL → CK_AaaP canonical
mv ~/.hermes/profiles/meta/SOUL.md ~/.hermes/profiles/meta/SOUL.md.bak
ln -s /d/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.meta.md ~/.hermes/profiles/meta/SOUL.md

# 3. Phase 2 Missive profile（須先建 profile）
hermes profile create missive --home ~/.hermes/profiles/missive
ln -s /d/CKProject/CK_Missive/SOUL.md ~/.hermes/profiles/missive/SOUL.md

# 4. Skills（透過 install.sh 而非 symlink — install 時 cp 進 ~/.hermes/skills/）
cd /d/CKProject/CK_AaaP/docs/hermes-skills/ck-adr-query
bash install.sh   # 由 CK_AaaP session 撰寫
```

驗證 `fix(skills): follow symlinked category dirs consistently`（v2026.4.23）已在 image 內 — 應已生效。

## 3. 跨 session 接力協議

### 3.1 Session 觸發原則

| 動作 | 由哪個 session |
|---|---|
| 寫 hermes-agent 任何檔案 | **hermes-agent session** |
| 寫 CK_AaaP 任何檔案 | **CK_AaaP session** |
| 寫 CK_Missive 任何檔案 | **CK_Missive session** |
| 寫 `~/.hermes/` runtime（除 wiki/）| 任一（host file，無 repo 邊界） |
| 寫 `~/.hermes/profiles/meta/wiki/` | **hermes-agent session**（記憶屬 fork 範圍） |
| 容器 docker compose 操作 | **CK_AaaP session**（compose.yml 在 CK_AaaP）|
| Hermes runtime CLI（`hermes cron list`...）| 任一 session（runtime 操作）|

### 3.2 接力訊號

各 session 完成階段後，在對應 wiki 留 ALIGN 訊號：
- hermes-agent session 完成 → 寫 `~/.hermes/profiles/meta/wiki/log.md`
- CK_AaaP session 完成 → 寫 `D:/CKProject/CK_AaaP/wiki/log.md`（若不存在則寫 commit message）
- 兩 session 啟動時先讀對方 log.md 最新 5 條

### 3.3 衝突處理

若兩 session 同時想動同一檔案：
- 以 **檔案實際所在 repo 的 session** 為主
- 另一 session 透過寫 plan 文件（如本檔）建議，**不直接動**

## 4. 驗收條件

| Phase | 驗收項 |
|---|---|
| A | CK_AaaP 7 個目標檔案存在 + cross-ref 通 + commit pushed |
| B | hermes-agent 副本頂端有 deprecation banner + commit pushed |
| C | hermes-agent fork 不再含 master-plan / adr proposal / skill design / poc |
| D | `~/.hermes/SOUL.md` 是 symlink → CK_AaaP；`hermes-gateway` 容器 restart 後讀取新 SOUL canonical |

## 5. 回滾計畫

| 階段 | 回滾路徑 |
|---|---|
| A 失敗 | CK_AaaP `git reset --hard HEAD~1`；hermes-agent 副本未動 |
| B 失敗 | hermes-agent `git revert <banner-commit>` |
| C 失敗 | hermes-agent `git revert <removal-commit>` 或 `git restore` |
| D 失敗 | `rm ~/.hermes/SOUL.md && mv ~/.hermes/SOUL.md.bak ~/.hermes/SOUL.md` |

每階段 commit 一個，便於 git revert。**禁止** squash 整個移轉成一個 commit。

## 6. 不在範圍

- ❌ 移轉 ADR-0020 Phase 2/3（Showcase / DigitalTunnel repo 實質歸併）— 屬遠期
- ❌ 移轉 hermes-agent 程式碼補丁（4 個 patches 永久屬 fork）
- ❌ 移轉 CK_Missive 業務 SOUL 至 CK_AaaP（CK_Missive 是 Muse-like 個體，SOUL 屬該 repo）
- ❌ 動 ~/.hermes/profiles/meta/wiki/ 進 git repo（私人記憶不公開）
- ❌ 動 upstream NousResearch（PR 是上行流，不影響整合）

## 7. 立即下一步（給使用者抉擇）

| 抉擇 | 動作 | 由誰 | 風險 |
|---|---|---|---|
| **A** 立刻啟動 Phase A | CK_AaaP session 執行 §2 Phase A 命令稿 | CK_AaaP session | 低 — 純複製 |
| **B** 先採納 ADR-0020 Phase 1 擴範圍提案再啟動 Phase A | 修訂 `CK_AaaP/adrs/0020-*.md` + 建 ADR-0026/0027/0028 | CK_AaaP session | 低 — 純文件 |
| **C** 先驗 missive.soul.md 在 CK_Missive 落地，再啟整體移轉 | CK_Missive session 寫 `CK_Missive/SOUL.md` | CK_Missive session | 中 — 涉業務 agent persona 設計 |
| **D** 暫停整合，先穩定 hermes-stack（hermes-web 還在 restart loop） | 修 docker-compose.yml `--insecure` | CK_AaaP session | 低 |

我建議 **D → B → A → C → Phase B → Phase C → Phase D**：
1. D：先把 hermes-web 修好（最快 5 分鐘）
2. B：採納 ADR proposal，名分先定
3. A：跨 session 並行複製
4. C：CK_Missive SOUL 寫好（最大有形價值）
5. B (本檔的 Phase B)：標 deprecated
6. C (本檔的 Phase C)：清理
7. D (本檔的 Phase D)：symlink

## 8. Cross-ref

- ADR-0020 主源：`CK_AaaP/adrs/0020-aaap-platform-with-hermes-control-plane.md`
- Phase 1 擴範圍提案：`docs/plans/adr-0020-phase1-extension-proposal.md`
- Master Plan v2：`docs/plans/master-integration-plan-v2-2026-04-19.md`
- 設計隱喻：`~/.hermes/profiles/meta/wiki/concepts/design-inspirations-muse-semiont.md`
- CONVENTIONS：`D:/CKProject/CK_AaaP/CONVENTIONS.md` §7（Session 工作目錄分流）
