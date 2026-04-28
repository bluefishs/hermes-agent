# C.1 — Runtime SOUL.md 狀態報告

> **日期**：2026-04-28
> **執行 session**：hermes-agent（per CONVENTIONS §7）
> **B2 Sprint Step**：C.1（per `CK_AaaP/platform/services/docs/hermes-skills/B2_SPRINT_PLAN.md`）

## 觀測結果

| 位置 | 大小 | md5 | 標題（首行） |
|---|---|---|---|
| `ck-hermes-gateway:/opt/data/SOUL.md` | 8989 bytes | `77a8f4ca…` | `# CK 數位助理 — 人格定義` |
| `ck-hermes-web:/opt/data/SOUL.md` | 8989 bytes | `77a8f4ca…` | `# CK 數位助理 — 人格定義` |
| `D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md` | 8396 bytes | `67e687da…` | `# 坤哥 — Missive 意識體` |

## 結論

### ✅ Plan §C.1 既有判準

> 若 < 1000 bytes → 容器跑空 placeholder，**現有所有 baseline 報告不可採信**
> 若 > 8000 bytes → 過去手動 docker cp 過，OK

Runtime SOUL 為 8989 bytes（>> 1000）→ **歷史 baseline 報告可採信**。

### ⚠️ 計畫未預料的情境：runtime 與 source 是兩種 SOUL 設計

兩端**不只是版本差**，而是兩種人格定義：

- **Runtime**（兩個 hermes-stack 容器內，先前手動 cp）：
  - 標題：`CK 數位助理 — 人格定義`
  - 定位：通用工程顧問助理；首段為「語言強制規則」
  - 沒有 frontmatter

- **Source-of-truth**（CK_AaaP/runbooks/hermes-stack/SOUL.md，2026-04-20 寫入）：
  - 標題：`坤哥 — Missive 意識體人格定義`
  - 定位：Missive 業務核心意識體（v2.0.0，含三信念 / 反迴聲室協議 / 倫理紅線）
  - 有 frontmatter（`type: soul`, `version: 2.0.0`, `tags: [agent, identity, persona, kunge, missive]`）
  - `sync_targets: [CK_AaaP/runbooks/hermes-stack/SOUL.md]`（自指；未列容器路徑）

兩者的差異不是迭代演進，而是**設計目標分流**：source 看似為 Missive agent 而設，但路徑卻放在通用 hermes-stack runtime 下，這個矛盾落在 CK_AaaP session 的治理範圍。

## 動作建議（治理決策）

C.1 的觀測就此停步；下列三選一由 **CK_AaaP session** 拍板，hermes-agent session 不擅自執行：

1. **保留 runtime 為通用 CK 助理人格** — 把 source 的「坤哥」搬到 `CK_Missive/SOUL.md`（per Missive bridge skill 規範方位置），並把 hermes-stack source 替換為通用 CK 助理版本。
2. **承認 source = 新統一人格** — 用 `python -m hermes_cli.sync_soul --apply` 推進兩個容器；接受運行人格從「通用 CK 助理」轉為「坤哥 — Missive 意識體」。
3. **分流：hermes-gateway 走 source（坤哥），hermes-web 保留 CK 助理** — 需給 `sync_soul.py` 加 per-container source 設定。

## 工具 ready（C.2 交付物）

```bash
# Dry-run + diff（預設）
python -m hermes_cli.sync_soul

# 指定 source / 目標容器
python -m hermes_cli.sync_soul --source <path> --containers ck-hermes-gateway,ck-hermes-web

# 真正寫入容器（需明確帶 --apply）
python -m hermes_cli.sync_soul --apply
```

工具預設 dry-run 是有意設計：SOUL.md 是 prompt cache 的 load-bearing 段，意外 sync 會立刻影響所有對話。`--apply` 為顯式 opt-in。

## 變更歷史

- **2026-04-28** — B2 Sprint C.1 觀測（hermes-agent session）
