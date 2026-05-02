# 12 輪 Iteration 產出 — Commit Organization

> **日期**：2026-05-02
> **session**：hermes-agent（第 12 輪 iteration）
> **目的**：把 33 個 untracked 檔案分類為 commit-ready batches，給用戶清楚的 commit 順序與 message 模板
> **背景**：12 輪 /loop iteration 累積，從覆盤 → 7 層真因 → working code → 5/5 預製 → 6/6 profile dir → 整體 wrap-up

## TL;DR

33 untracked files 分為 **6 個建議 commit batches**：

| # | Batch | 檔案數 | 主題 | 優先 |
|---|---|---|---|---|
| 1 | 治理面 ADR + Roadmap | 7 | 第 1 輪輸出，無 working code 但有 process value | P2 |
| 2 | escalate helpers + 測試 | 3 | 路線 B 共用 helper（與 P0 解耦但仍有用）| P2 |
| 3 | lvrland bridge stub + tests | 6 | Phase 1 lvrland-bridge 完成（B2 Sprint A.5）| **P1** |
| 4 | 7 層真因 postmortem + A/B/C/D 實驗 | 5 | 9 輪 iteration 證據鏈 + 過時 v1/v2 標明 | **P0** |
| 5 | 5/5 skill helper template + adopt.sh + final report | 14 | **核心可交付物** — working code + 自動採納 + e2e SOP | **P0** |
| 6 | Phase 2 profile isolation 設計 | 1 | 下階段路徑 | P2 |

**總工時**：用戶按順序 commit ~ 30 min。

## Batch 1 — 治理面 ADR + Roadmap（P2，文件性質）

```bash
git add docs/plans/integration-blocker-board.md \
        docs/plans/cross-session-execution-roadmap-2026-04-29.md \
        docs/plans/route-decision-card.md \
        docs/plans/hermes-model-baseline-route-b-2026-04-29.md \
        docs/plans/adr-0024-ck-lvrland-bridge-skill-draft.md \
        docs/plans/adr-0027-execution-plan-2026-04-29.md \
        docs/plans/adr-stale-check-execution-2026-04-30.md

git commit -m "docs(plans): governance roadmap + ADR drafts (iteration 1 output)

第 1 輪 iteration 治理面產出：
- integration-blocker-board.md：18 條 roadmap 跨 session 看板
- cross-session-execution-roadmap-2026-04-29.md：細節版
- route-decision-card.md：模型路線 A/B/C 決策卡（與 P0 解耦）
- hermes-model-baseline-route-b-2026-04-29.md：路線 B 評估
- adr-0024-ck-lvrland-bridge-skill-draft.md：lvrland skill 規範草稿
- adr-0027-execution-plan-2026-04-29.md：pgvector index policy 推進
- adr-stale-check-execution-2026-04-30.md：ADR 季度結算機制

純 governance 文件，與 hermes 服務整合運用 P0（7 層真因）解耦。
保留作 process reference。"
```

## Batch 2 — Escalate Helpers（P2，與 P0 解耦但仍有用）

```bash
git add docs/plans/escalate-helpers/ \
        docs/plans/escalate-config-patch-2026-04-29.md \
        docs/plans/shadow-baseline-anthropic-tag-2026-04-29.md \
        tests/skills/test_escalate_complexity.py

git commit -m "feat(skill-helpers): escalate complexity heuristic + config patch

路線 B 強化版共用 helper：
- escalate-helpers/complexity.py：純 stdlib，4 ck-* skill 共用 complexity hint
- escalate-helpers/README.md：採納步驟
- tests/skills/test_escalate_complexity.py：20/20 tests passing
- escalate-config-patch-2026-04-29.md：CK_AaaP infra 5 patches
- shadow-baseline-anthropic-tag-2026-04-29.md：baseline 加 model_tag 設計

⚠️ 與 P0 tool-call 失效解耦（仍是好設計但不解 P0；P0 解法見 batch 5）
未來若用戶選路線 B（Anthropic escalate）採納此段。"
```

## Batch 3 — LvrLand Bridge Stub + Tests（P1，B2 Sprint A.5）⭐

```bash
git add docs/plans/ck-lvrland-bridge-stub/ \
        tests/skills/test_ck_lvrland_bridge.py

git commit -m "feat(skill): B2 Sprint A.5 — ck-lvrland-bridge stub + 12 tests

per ADR-0024 (proposed)：
- 3 tools functional: lvrland_health / lvrland_query_sync / lvrland_price_trends
- ACTION_HANDLERS 對應 LvrLand /api/v1/ai/query / /api/v1/analytics/price-volume-trends
- tests: 12/12 ✅（含 stub_http fixture / fallback / error paths / register_all）
- + scripts/query.py helper（Phase 1.5 採納用，待 CF Tunnel #12）
- + skill-patch.md：CK_lvrland session 採納步驟

接續 ck-missive-bridge / ck-observability-bridge / ck-showcase-bridge / ck-pilemgmt-bridge
完成 ADR-0020 Phase 1 4 bridge skill 矩陣。

Refs: hermes-agent docs/plans/ck-lvrland-bridge-stub/SKILL.md"
```

## Batch 4 — 7 層真因 Postmortem + A/B/C/D 實驗證據（P0 證據）⭐

```bash
git add docs/plans/_ab_lab/ \
        docs/plans/hermes-runtime-blockers-postmortem.md \
        docs/plans/hermes-integration-playbook.md \
        docs/plans/skill-curl-pattern-patch.md

git commit -m "docs(diagnosis): hermes runtime tool-call 失效 7 層真因完整證據鏈

12 輪 iteration 中 3-4 輪實證鏈：
- _ab_lab/run_ab.py + run_trial_d.py：4 trials 直打 ollama 證據
- _ab_lab/results.json + results_d.json：實驗結果
- _ab_lab/_soul.md + _missive_skill.md：實驗 fixtures
- hermes-runtime-blockers-postmortem.md：6+1 層真因（L1-L7）+ α/β/γ 路徑

過時 playbook（已標明 v1→v2 校正）：
- hermes-integration-playbook.md：v1（縮 context / 換 model / escalate）已否定
- skill-curl-pattern-patch.md：v2（curl pattern）已否定（curl 不存在 + L4-L6 堵死）

→ 真實 P0 解法見 batch 5 (skill-helper-template/)"
```

## Batch 5 — 5/5 Skill Helper Template + adopt.sh + Final Report（P0 核心可交付物）⭐⭐⭐

```bash
git add docs/plans/skill-helper-template/ \
        docs/plans/ck-observability-bridge-skeleton/scripts/ \
        docs/plans/ck-observability-bridge-skeleton/skill-patch.md \
        docs/plans/ck-pilemgmt-bridge-stub/scripts/ \
        docs/plans/ck-pilemgmt-bridge-stub/skill-patch.md \
        docs/plans/ck-showcase-bridge-stub/scripts/ \
        docs/plans/ck-showcase-bridge-stub/skill-patch.md \
        docs/plans/hermes-integration-final-report.md \
        docs/plans/hermes-acceptance-sop.md

git commit -m "feat(skill-helpers): 5/5 ck-* skill helper 預製 + adopt.sh + final report

12 輪 iteration 累積核心可交付物：

1. skill-helper-template/ — Missive helper（已 pilot 部署到 runtime ✅）
   - query.py：純 stdlib，繞 hermes 7 道閘
   - install.sh / adopt.sh：runtime 部署 + 業務 repo 採納自動化
   - missive-skill-patch.md：CK_Missive SKILL.md 直接複製貼上
   - README.md：5/5 採納就緒度表 + 4 步完整解阻塞最小路徑

2. ck-{lvrland,pile,showcase}-bridge-stub/scripts/query.py + skill-patch.md
   3 skill 預製，等 CF Tunnel #12-13 上線後 5–10 min 採納

3. ck-observability-bridge-skeleton/scripts/query.py + skill-patch.md
   multi-backend 設計（Loki/Prom/Grafana/Alertmanager），9 actions

4. hermes-integration-final-report.md：9 輪 wrap-up 一頁總覽
5. hermes-acceptance-sop.md：採納後 e2e 驗收（hermes-web :9119 為主入口）

驗證：missive 端到端通過 hermes runtime 75s 取真實業務 query（rag_search 5 公文）。

採納路徑：
  業務 repo session: bash docs/plans/skill-helper-template/adopt.sh <skill> .

Refs: hermes-runtime-blockers-postmortem.md (7 層真因)
      hermes-integration-final-report.md (整體狀態)"
```

## Batch 6 — Phase 2 Profile Isolation Design（下階段）

```bash
git add docs/plans/phase2-profile-isolation-design.md

git commit -m "docs(plans): Phase 2 profile isolation 設計探索（解 stochastic + SOUL conflict）

Master Plan v2 Phase 2 + ADR-0020 Phase 1.5 設計探索：
- 為何仍重要（即使 P0 已解）：stochastic / SOUL 人格衝突 / 簡中滲入 30%
- 與 9 輪 helper 結構不互斥（profile 切上層、helper 不動）
- 6 profile 結構：meta + missive + lvrland + pile + showcase + observability
- Missive pilot 4 步 plan
- 與 ADR-0020 Phase 1/2/3 對齊
- 預期收益：tool-call 70% → 90% / 簡體 30% → < 10%

⚠️ 探索性設計，待用戶授權執行 Missive pilot（30 min Step 1）。

註：Phase 1.5 Step 1 (建 missive profile dir) 已在第 11/12 輪本 session 執行，
    結構在 ~/.hermes/profiles/missive/（gitignored），未啟用 active_profile。"
```

## 不建議 Commit 的檔案（暫存實驗 / 不適合進 git）

| 檔案 | 原因 | 建議 |
|---|---|---|
| `docs/plans/_demo_payload.json` | curl 測試暫存 payload | 加入 .gitignore |
| `docs/plans/hermes-feel-the-power.sh` | 早期實驗腳本 | 確認用途後決定 |
| `docs/plans/unblock-soul-c1.sh` | SOUL Step 2 腳本，可能仍有效 | 確認 SOUL 治理現狀後決定 |
| `docs/plans/adr-stale-check.py` | adr-stale-check 腳本，治理用 | 與 batch 1 一起 commit 或 CK_AaaP 採納 |
| `docs/plans/config.yaml.l2-full` / `l2-pilot` | hermes config 草稿 | 確認用途；可能與 batch 5 整合 |

## 採納順序建議

| 順序 | Batch | 原因 |
|---|---|---|
| 1️⃣ | Batch 5 | **最高價值** — 核心可交付物，立即解 P0 |
| 2️⃣ | Batch 4 | 證據鏈，配合 batch 5 解釋為何這樣設計 |
| 3️⃣ | Batch 3 | lvrland-bridge stub（B2 Sprint 進度）|
| 4️⃣ | Batch 6 | 下階段路徑文件 |
| 5️⃣ | Batch 2 | escalate（與 P0 解耦但仍有用）|
| 6️⃣ | Batch 1 | governance roadmap（process value）|

## 一次性全 commit（不推薦但快）

若用戶想一次清掉，可：

```bash
# ⚠️ 不推薦：失去 commit history 的階段性
git add docs/plans/ tests/skills/test_ck_lvrland_bridge.py \
        tests/skills/test_escalate_complexity.py
git commit -m "docs+feat: hermes 服務整合運用 12 輪 iteration 累積產出"
```

## ~/.hermes/profiles/ 不入 git（runtime state）

第 11/12 輪在 ~/.hermes/profiles/ 建的 6 profile dir 是 **runtime state**，**不入 hermes-agent repo git**。
這些是用戶/部署 specific 設定，per ADR-0020 Phase 4 設計屬於 hermes-stack 個人/環境配置。

若要持久化 profile 配置給其他環境採用：
- SOUL.md 模板已在 `docs/plans/soul-templates/`（git tracked）
- Phase 1.5 啟用 SOP 在 `phase2-profile-isolation-design.md`（本輪 batch 6 commit）

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第 12 輪 iteration）
