# Integration Blocker Board — 跨 Session 單頁看板

> **日期**：2026-05-01
> **目的**：解決「roadmap 18 條條目雜陳、不知從哪動」問題；每個 session 啟動先讀此頁
> **更新規則**：完成一條 → 把該條從「actionable」搬到「done」並加 ✅ + 完成日期；新發現的依賴變化 → 改「blocked 原因」欄
> **真相源**：本檔 + `cross-session-execution-roadmap-2026-04-29.md`（細節）+ `CK_AaaP/adrs/REGISTRY.md`（ADR）

## 看板速覽（2026-05-01）

| 狀態 | 數量 | 主要區塊 |
|---|---|---|
| ✅ Done | 4 | hermes-agent 內部（lvrland skill / escalate helper / SOUL script / 4 bridge 契約驗證）|
| 🟢 Actionable now | 6 | 各 session 立即可動，無人決策依賴 |
| 🟡 Blocked-on-decision | 3 | 等用戶決策（路線 B/C 的 key） |
| 🔵 Sequenced future | 5 | 等其他 task 完成後才能動（依賴鏈在表內） |

---

## ✅ Done（hermes-agent session 已交付）

| # | 動作 | 完成日 | 產物 |
|---|---|---|---|
| ✅ 5 | lvrland-bridge tests + install.sh | 2026-04-29 | `tests/skills/test_ck_lvrland_bridge.py` 12/12；`docs/plans/ck-lvrland-bridge-stub/` 5 檔完整 |
| ✅ 7 | skill-side escalate 共用邏輯 | 2026-05-01 | `docs/plans/escalate-helpers/{complexity.py, README.md}` + `tests/skills/test_escalate_complexity.py` 20/20 |
| — | SOUL unblock script（Step 1+2）| 2026-04-28 | `docs/plans/unblock-soul-c1.sh`（CK_AaaP run step1，hermes-agent run step2）|
| — | 4 bridge skill 契約對齊驗證 | 2026-05-01 | 51 tests pass；全部符合 hermes-skill-contract-v2 |

---

## 🟢 Actionable Now（無依賴，立即可動）

按 session 分組，每條 30 min – 2h 工時。

### CK_AaaP session

| # | 動作 | 工時 | 進入點 |
|---|---|---|---|
| 2 | **C.1 SOUL Step 1**（搬坤哥回 Missive、套 meta.soul.md） | 30 min | `bash D:/CKProject/hermes-agent/docs/plans/unblock-soul-c1.sh step1` |
| A | **ADR-stale-check + pgvector-lint 一次上 CI**（M+K2）| 1.5h | `cp ../hermes-agent/docs/plans/adr-stale-check.py scripts/checks/`；K2 草稿在 `adr-0027-execution-plan-2026-04-29.md` |
| 4 | **ADR-0024 + lvrland-bridge 採納**（roadmap #4） | 1.5h | `cp -r ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/* platform/services/.../ck-lvrland-bridge/` 即可（stub 12/12 已綠）|
| 6 | **路線 B-冷 escalate config patch** | 30 min | `escalate-config-patch-2026-04-29.md` 5 patches，ANTHROPIC_API_KEY 留空 = 等同路線 A |
| 15 | **ADR 季度結算機制**（M 條，可與 A 合併 commit） | 與 A 合併 | 同上 |

### CK_Missive session

| # | 動作 | 工時 | 進入點 |
|---|---|---|---|
| K1 | **document_chunks 升 HNSW**（5/5 表一致） | 30 min（離峰）| `adr-0027-execution-plan-2026-04-29.md` SOP；alembic migration 模板已備 |
| 8 | **shadow baseline 加 model_tag**（依賴 #6 完成）| 1h | 等 #6 套用後再做 |
| 10a | **ADR-0019 觀測統一 pilot**（Missive 先行） | 2h | 各 service `ck_<svc>_<metric>` prefix + structlog JSON formatter |

### hermes-agent session（自己）

| # | 動作 | 工時 | 進入點 |
|---|---|---|---|
| 3 | **C.1 SOUL Step 2**（依賴 #2 完成） | 5 min | `bash docs/plans/unblock-soul-c1.sh step2` |

---

## 🟡 Blocked on Decision（等用戶 5 min 確認）

| # | 動作 | 等什麼 | 解鎖後立即可動 |
|---|---|---|---|
| 1 | **Hermes 模型路線 A / B-冷 / B / C** | 用戶 5 min 選一 | 推薦 B-冷（infra 鋪好、key 留空）→ 解鎖 #6/#7/#8 |
| 6\* | escalate config 套用真實 key | 路線 = B（含 key）| #8 baseline 才會看到 escalate sample |
| 14 | **Docker Secrets Missive Phase 2** | ADR-0017 Phase 2 排程 | 4h 工時，獨立 session |

\* #6 的 infra patch 在 B-冷 即可上線；只有「真實 key 寫入」需等用戶提供。

---

## 🔵 Sequenced Future（等前置 task 完成）

依賴鏈視覺化：

```
    [#2 SOUL Step1] ──► [#3 SOUL Step2] ──► [#1 GO/NO-GO 7d baseline]
                                                       │
    [#4 ADR-0024]  ──► [#5 lvrland tests ✅] ─────────┤
    [#7 escalate ✅] ─► [#6 config patch] ─► [#8 baseline tag] ──► ADR-0014 GO/NO-GO
                                                       │
    [#K1 HNSW]     ──► [K6 ADR-0027 accepted] ────────┤
    [#A stale-CI]  ──► [#15 季度結算機制] ─────────────┤
                                                       ▼
                                              Phase 1 收尾完成
                                                       │
            ┌──────────────────────────────────────────┤
            ▼                                          ▼
    [#11 資料層 ADR-002X]                    [#12 CF lvrland subdomain]
            │                                          │
            ▼                                          ▼
    [#16 Showcase 遷入 AaaP] ◄───────── [#13 CF pile/hermes/tunnel]
            │
            ▼
    [#17 觀測棧併入 docker-compose.platform.yml]
            │
            ▼
    [#18 一鍵 git clone + docker compose up]  ← ADR-0020 最終態
```

| # | 動作 | 等什麼 | session |
|---|---|---|---|
| 11 | 資料層 3-PG 分級評估 ADR-002X | Phase 1 收尾 | CK_AaaP |
| 12 | CF Tunnel `lvrland.cksurvey.tw` | LvrLand 公網就緒 | CK_AaaP + CK_lvrland |
| 13 | CF Tunnel pile/hermes/tunnel subdomain | #12 完成 | CK_AaaP + 各 repo |
| 16 | Showcase 治理 API 遷入 CK_AaaP/platform/services/ | #11 + #15 | CK_AaaP（1 週工時） |
| 17 | DigitalTunnel 觀測棧併入 docker-compose.platform.yml | #16 | CK_AaaP（1 週工時） |
| 18 | 一鍵啟動驗收 | #16 + #17 | 根 session（半天）|

---

## 每 session 啟動「下一動作」決策樹（精簡版）

```
切到 CK_AaaP？
  優先動 #2 (30 min) → 立刻可開 hermes-agent 跑 #3
  其次 A (1.5h，A 與 #15 合併最有效率)
  再其次 #4 (1.5h，stub 已就位、純複製採納)
  再其次 #6 (30 min，B-冷可即上)

切到 CK_Missive？
  優先 #K1 (30 min 離峰窗口) → 立刻 ADR-0027 → accepted
  其次 #10a (2h，ADR-0019 pilot 自家先行示範)
  等 #6 完成才動 #8

切到 hermes-agent？
  本 session 已交付 5/7/SOUL-script/契約驗證/blocker-board
  等 CK_AaaP 完成 #2 才能跑 #3
  等 CK_AaaP 完成 #6 才能驗證 escalate-helpers 在 runtime 整合

切到 CK_lvrland / CK_PileMgmt？
  #10 (各自 ADR-0019 觀測統一)
  等 CF Tunnel 排程才動 #12/#13

用戶？
  #1 (5 min 路線決策) — 解鎖 #6/#7/#8 串聯
```

---

## 整合最大效益建議（一條動作多個收益）

| 合併動作 | 一次 commit 收益 |
|---|---|
| #2 + #3 連跑 | SOUL 治理一氣呵成；baseline 重跑只破一次 cache（vs 分兩次破兩次）|
| A + #15 | M 條（adr-stale-check）+ K2（pgvector-lint）一次 PR 上 CI；都是 governance |
| K1 + K6 | document_chunks 升 HNSW 完成同 commit 升 ADR-0027 為 accepted |
| #4 + #5 已綠採納 | 採納就是純複製（stub 12/12 + tests 都已就位），即收即用 |
| #6 + escalate-helpers | infra patch + skill helper 同 PR 採納；驗收一次走完 |

**真正最大效益的順序**：
1. CK_AaaP 1 次 session 連跑 `#2 + A + #15 + #4 + #6` ≈ **4h 一次清掉 5 條**
2. hermes-agent 1 次 session 跑 `#3` ≈ **5 min 解鎖 SOUL**
3. CK_Missive 1 次 session 跑 `K1 + K6` ≈ **30 min 5/5 表 HNSW**
4. 用戶 5 min 決策 `#1` → 解鎖 #6 完整啟動

→ **本週可全部關閉 P0/P1**，剩 P2/P3 在 sequenced future。

---

## 變更歷史

- **2026-05-01** — 初版（hermes-agent session 第二次覆盤輸出，整合 #5 入 actionable 看板）

## 相關

- `docs/plans/cross-session-execution-roadmap-2026-04-29.md` — 細節版（18 條全表）
- `docs/plans/route-decision-card.md` — #1 路線決策卡
- `docs/plans/c1-soul-status-2026-04-28.md` — #2/#3 SOUL 治理脈絡
- `docs/plans/escalate-config-patch-2026-04-29.md` — #6 patch（5 段 ready）
- `docs/plans/escalate-helpers/README.md` — #7 skill-side helper（本 session 完成）
- `docs/plans/adr-0027-execution-plan-2026-04-29.md` — #K1/K2/K6 SOP
- `docs/plans/adr-stale-check-execution-2026-04-30.md` — #A/M 季度結算 SOP
- `CK_AaaP/CONVENTIONS.md` §7 — Session 啟動位置規範
