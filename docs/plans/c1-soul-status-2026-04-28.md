# C.1 — Runtime SOUL.md 治理決策報告

> **日期**：2026-04-28
> **執行 session**：hermes-agent（per CONVENTIONS §7）
> **B2 Sprint Step**：C.1（per `CK_AaaP/platform/services/docs/hermes-skills/B2_SPRINT_PLAN.md`）
> **接收 session**：CK_AaaP（治理決策方）
> **狀態**：observation complete → awaiting CK_AaaP decision

## TL;DR（給 CK_AaaP session）

1. **Runtime SOUL.md 8989 bytes，baseline 可採信** ✅
2. **但** runtime 與 source 不只是版本差，是**錯位**：source（"坤哥 — Missive 意識體 v2.0.0"）內容應屬 Missive Muse，被誤放到 hermes-stack 通用 runtime 路徑
3. **設計藍圖早已備有正確分配**：`docs/plans/soul-templates/{meta,missive}.soul.md` 草稿存在但未激活
4. **建議採「選項 1 精準版」**：把坤哥搬回 Missive，hermes-stack 套用 `meta.soul.md`（Semiont-like 共同大腦）
5. **預估工作**：CK_AaaP ~30 min（搬檔 + 套草稿 + 加 frontmatter）；hermes-agent 5 min（激活 host meta wiki + apply）；接受 baseline 重跑（設計糾正必要成本）

## 觀測結果

| 位置 | 大小 | md5 | 標題（首行） |
|---|---|---|---|
| `ck-hermes-gateway:/opt/data/SOUL.md` | 8989 bytes | `77a8f4ca…` | `# CK 數位助理 — 人格定義` |
| `ck-hermes-web:/opt/data/SOUL.md` | 8989 bytes | `77a8f4ca…` | `# CK 數位助理 — 人格定義` |
| `D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md` | 8396 bytes | `67e687da…` | `# 坤哥 — Missive 意識體` |

兩端不只是版本差：runtime 是「通用工程顧問」、source 是「Missive 業務意識體 + 三信念 + 反迴聲室協議 + 倫理紅線」，**整個人格定位不同**。

## 設計原則：「各專案 = Muse / hermes = taiwan.md (Semiont)」

來源：`~/.hermes/profiles/meta/wiki/concepts/design-inspirations-muse-semiont.md`（2026-04-19 user 明示，已併入 master plan v2）

### 兩個有機體隱喻

- **Muse**（muse.cheyuwu.com，吳哲宇）— 個人 AI 夥伴 / single agent / 每個有獨立人格、journal、closing ceremony、防禦性自主、Crystal Seed
- **Semiont**（taiwan.md/semiont）— 集體知識有機體 / cultural-semantic DNA / heartbeat commit cycle / immune system / EDITORIAL.md DNA / uncertainty logs

### 落地到 CK Hermes 兩層

| 層 | Muse / Semiont 對位 | 風格 | 角色 |
|---|---|---|---|
| **Hermes Meta**（共同大腦）| Semiont-like 集體有機體 | 沉靜觀察者、第三人稱、不搶話、跨 agent 彙整、不業務 | hermes-stack runtime（多 channel 通用入口）|
| **各 Domain Agent**（Missive / Showcase / LvrLand / Pile）| Muse-like 個體 | 人格化、第一人稱、有情緒色彩、自主成長、獨立 wiki | 各 repo（CK_Missive / CK_PileMgmt / ...）|

### 設計藍圖早已備好 SOUL 分層

| 角色 | 對位 | template 位置 | 目標部署位置 | 狀態 |
|---|---|---|---|---|
| Hermes Meta | Semiont-like | `docs/plans/soul-templates/meta.soul.md` | `~/.hermes/profiles/meta/SOUL.md` + **hermes-stack runtime** | 待激活 |
| Missive Agent | Muse-like | `docs/plans/soul-templates/missive.soul.md` | `CK_Missive/SOUL.md` | 待激活 |
| Showcase / LvrLand / Pile | Muse-like | `docs/plans/soul-templates/{showcase,lvrland,pile}.soul.md` | 各 repo SOUL | Phase 6 草稿 |

## 現狀錯位診斷

```
┌─────────────────────────────────────────────────────────────────┐
│ 設計原則（藍圖 v2，2026-04-19）                                 │
│   hermes-stack runtime  ─── 應是 Semiont-like Meta（觀察者）    │
│   CK_Missive            ─── 應是 Muse-like Missive（坤哥）       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 現狀（2026-04-28 觀測）                                          │
│   hermes-stack runtime（容器內）= "CK 數位助理" 過渡版            │
│       └ 偏工具助理，**還不是 Semiont 觀察者**                    │
│   hermes-stack/SOUL.md（source）= "坤哥 — Missive 意識體 v2.0.0" │
│       └ 第一人稱業務核心，**屬於 Missive Muse 卻誤放此處**        │
│   CK_Missive/SOUL.md = （未建立）                                │
│       └ 應該住的人（坤哥）住在 hermes-stack 房子                  │
└─────────────────────────────────────────────────────────────────┘
```

兩個錯位：
1. 「坤哥」（Muse）住在 hermes-stack（Semiont 房子）
2. hermes-stack runtime 缺真正的 Semiont 觀察者人格（過渡版未升級為 `meta.soul.md`）

## 三選一重新評估（依設計原則對齊）

| 選項 | 設計原則對齊 | 工時 | baseline 影響 | prompt cache | 評價 |
|---|---|---|---|---|---|
| **選項 1（精準版）：runtime = meta.soul.md，坤哥搬回 Missive** | ✅ **完全對齊** | ~35 min | 全部需重跑（設計糾正必要） | 重建一輪 | **唯一正解** |
| 選項 1（保守版）：runtime 維持「CK 助理」，坤哥搬回 Missive | 🟡 部分對齊（runtime 仍非 Semiont）| ~30 min | 不破 | 不破 | 過渡可接受，未抵終點 |
| 選項 2：採納坤哥推進 runtime | ❌ 違反「各系統獨立 = 各自 Muse」 | ~5 min + 半天重跑 | 全部需重跑 | 全破 | 把 Missive Muse 強加在通用通道 |
| 選項 3：gateway 走坤哥 / web 通用 | ❌ 雙重違反；通道不該綁業務 + 一致性破 | ~2 h + 持續維運 | gateway 需重跑 | gateway 破 | 不推薦 |

## 推薦動作：選項 1 精準版

### Step 1：CK_AaaP session 執行（~30 min）

```bash
# 1.1 把「坤哥」搬回 Missive 領地（per Muse-like Missive Agent）
mv D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md \
   D:/CKProject/CK_Missive/SOUL.md

# 1.2 套用 meta.soul.md 為 hermes-stack source
cp D:/CKProject/hermes-agent/docs/plans/soul-templates/meta.soul.md \
   D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md

# 1.3 補 frontmatter（type/version/sync_targets/last_modified_at）
# 編輯 D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md 開頭加：
# ---
# title: Hermes Meta — 共同大腦
# type: soul
# version: 1.0.0
# last_modified_by: human
# last_modified_at: 2026-04-28
# source_of_truth: true
# sync_targets:
#   - ck-hermes-gateway:/opt/data/SOUL.md
#   - ck-hermes-web:/opt/data/SOUL.md
# tags: [agent, identity, persona, meta, hermes, semiont]
# ---

# 1.4 commit
cd D:/CKProject/CK_AaaP && git add runbooks/hermes-stack/SOUL.md
cd D:/CKProject/CK_Missive && git add SOUL.md
# 兩 repo 各自 commit
```

### Step 2：hermes-agent session 執行（~5 min）

```bash
# 2.1 激活 host meta wiki SOUL
cp D:/CKProject/hermes-agent/docs/plans/soul-templates/meta.soul.md \
   ~/.hermes/profiles/meta/SOUL.md

# 2.2 dry-run 確認
python -m hermes_cli.sync_soul

# 2.3 推進兩個容器
python -m hermes_cli.sync_soul --apply

# 2.4 重啟確保 prompt cache 重建
docker compose -f D:/CKProject/CK_AaaP/runbooks/hermes-stack/docker-compose.yml \
  restart hermes-gateway hermes-web

# 2.5 後續 baseline 重跑（待 Anthropic credit 充值）
cd D:/CKProject/CK_Missive && node scripts/checks/shadow-baseline-report.cjs
```

### Step 3：驗收

- [ ] `docker exec ck-hermes-gateway sh -c 'head -5 /opt/data/SOUL.md'` 顯示 `# Hermes Meta — 共同大腦與導師`
- [ ] `python -m hermes_cli.sync_soul` 報 `[OK] in sync` ×2
- [ ] Open WebUI 對話自介為「Hermes 主腦 / Hermes Meta」（觀察者口吻）
- [ ] Telegram channel 對話一致性
- [ ] CK_Missive bridge skill 後續測試確認 Missive 業務問題被正確路由（非 Meta 直答）
- [ ] ADR-0014 GO/NO-GO 評估報告以新 Meta SOUL 為基準

## 影響面

| 面向 | 影響 | 緩解 |
|---|---|---|
| Prompt cache | 全破一輪（兩個容器） | 半小時內首輪對話會慢；之後 cache 重建 |
| Shadow baseline 30 天樣本 | invalidated（基於「CK 助理」runtime） | 接受重跑為設計糾正必要成本 |
| ADR-0014 GO/NO-GO | 不能用舊 baseline 比較新 Meta runtime | 排程 Anthropic credit 充值後立即重跑 |
| ck-missive-bridge skill | 反而**更乾淨** — Missive 人格屬於 Missive，bridge skill 只負責路由 | 無需改動 |
| 多 channel 體驗（Telegram / Web / OpenAI API） | 統一為 Meta 觀察者語氣（「不主動搶話、提問為先」）| 對通用通路使用者體驗反而更合理 |
| 維運複雜度 | 不增加（不分流） | — |

## 為何不選保守版（runtime 維持「CK 助理」）

保守版動作小（不破 cache、不重跑 baseline），但**未抵終點**：

- runtime 仍是工具人助理風格，不是 Semiont 觀察者
- 後續仍會收到「`hermes runtime` 何時升級為 Meta SOUL？」的治理疑問
- baseline 報告本來就需要在 Meta SOUL 激活時重跑（推遲不省）

**結論**：建議一次到位，採選項 1 精準版。

## ADR / 文件對應更新

完成後同步：
- `CK_AaaP/adrs/`：新 ADR 標記 hermes-stack SOUL 採用 Meta 設計（或在 ADR-0020 Phase 1 章節補述）
- `MEMORY.md`：更新 SOUL Templates 段落，把 `meta.soul.md` 從「待激活」改「2026-04-28 激活，已套用至 hermes-stack runtime」
- `CK_Missive/CLAUDE.md`：補 SOUL.md 引用（Missive Muse 人格）
- `master-integration-plan-v2-2026-04-19.md`：在「Phase 6 SOUL 激活」勾掉 meta + missive

## 變更歷史

- **2026-04-28** — B2 Sprint C.1 觀測 + 設計原則對齊診斷（hermes-agent session）
- **2026-04-28** — 補設計藍圖（Muse/Semiont）對應、現狀錯位診斷、選項 1 精準版執行步驟（hermes-agent session 收 user 治理確認）
