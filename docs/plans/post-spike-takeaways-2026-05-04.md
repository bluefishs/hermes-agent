# Post-Spike Takeaways — 後續題索引與決議

> **日期**：2026-05-04
> **觸發**：Spike `spike-profile-isolation-2026-05-04.md` 完成
> **作用**：把 spike 揭露的後續工作收斂為單一索引，避免散落

---

## §1 Spike 結論回顧（一句話）

CLI 層 GO（HERMES_HOME swap 乾淨、隔離可信、無 GPU 洩漏），Docker gateway 層 NO-GO（容器內 HERMES_HOME 寫死）→ 必補方案 Y（entrypoint 動態讀 ACTIVE_PROFILE 並重啟容器）才能落地 Master Plan v2 Phase 2 的「按需切 profile = 體感不同 agent」。

詳見：
- 報告：`docs/plans/spike-profile-isolation-2026-05-04.md`
- 量測：`docs/plans/spike-results/`
- 方案 Y 設計：`docs/plans/hermes-multi-profile-docker-design-2026-05-04.md`

---

## §2 Phase 4 Cleanup 決議

**選項 (b) 保留驗證 7 天，2026-05-11 自動清除**。

| 項目 | 決議 |
|---|---|
| spike profile (`~/.hermes/profiles/spike/`) | **保留** 至 2026-05-11 |
| 量測 csv / 報告 / pointer | **永久保留**（spike 證據鏈） |
| Active profile | 仍為 `meta`（spike 期間未動 sticky） |
| 自動清除指令 | `python -m hermes_cli.main profile delete spike --yes` |

**理由**：
1. spike 物件對運作中容器零影響（容器 HERMES_HOME=/opt/data 寫死、與 host `~/.hermes/profiles/spike/` 完全解耦）
2. 使用者可自主重跑 isolation probe 驗證（§ Spike report §4.3）
3. 7 天足夠 ADR-0020 採納方案 Y 後比對（若採用，spike profile 可作為驗證樣板的副產物保存更久；若放棄方案 Y，正常清除）

---

## §3 Master Plan v2 §7 R1 更新建議

**不直接修改原 master plan**（保留歷史一致性），而是 **append 一段「2026-05-04 Spike 後修正」**：

### 建議補丁段（CK_AaaP session 採納時 inline）

```markdown
## 7.1 R1 風險 surface 更新（2026-05-04 spike 後）

| R1 子項 | 原 | 新 | 動作 |
|---|---|---|---|
| Profile CLI 切換 | M×H | L×L | 撤除 |
| KV cache 重建 | M×H | L×L | 撤除 |
| Context 隔離 | M×H | L×L | 撤除 |
| GPU memory delta | M×H | L×M | 縮減；GPU free 524 MiB 排除「方案 X 多容器」可行性 |
| **Docker gateway 不感知 profile（NEW）** | — | H×H | 新增 R1.x，必補方案 Y（見 hermes-agent#docs/plans/hermes-multi-profile-docker-design-2026-05-04.md） |
```

### 同時更新 §9 成功指標

```markdown
- [ ] **新**：方案 Y 採納後，10 次連續 /switch 成功率 ≥ 95%、切換時間 P95 ≤ 10 s
```

**動作**：等使用者授權，由本 session 改寫 master-plan-v2 文末加章節，或由 CK_AaaP session 在採納時 inline。

---

## §4 CLI 層 Missive Pilot 提早

Master Plan v2 W2 排定「Missive profile 首發試跑」。spike 後**可拆分**：

| 階段 | 路徑 | 啟動條件 | 工程量 |
|---|---|---|---|
| **W2a CLI 層 pilot** | `python -m hermes_cli.main -p missive chat ...` 走 CLI | CK_Missive/SOUL.md 已落地 + missive profile config.yaml 有 ck-missive-bridge | 0.5 h（純 SOUL 套用 + 5 prompt 驗證）|
| W2b Docker 層 pilot | 方案 Y 接通 + Telegram /switch missive | Y-1 + Y-2 完成 + 量化指標通過 | 4 h |

**好處**：W2a 可立即進行（只需 CK_AaaP session 放 SOUL）；不必等 Y-1/Y-2 完成。Master Plan v2 §9 「Missive agent 7 天 tool-calling 成功率 ≥ 70%」可從 W2a 開始計時。

**動作**：
- 本 session 寫一份 `docs/plans/cli-missive-pilot-2026-05-04.md` PoC 步驟（5 prompt 樣本 + 量測表 + 7 天追蹤格）
- 等 CK_AaaP session 確認 CK_Missive/SOUL.md 落地後啟動

---

## §5 Plan B（Hermes Gateway Metrics）啟動條件

前次規劃見聊天紀錄。Spike 後**可立即啟動**，建議納入下一輪本 session 工作：

| 步驟 | 工程量 | 依賴 |
|---|---|---|
| 1. 確認 gateway 框架（FastAPI 推測） | 5 min | — |
| 2. 加 prometheus-client | 5 min | pyproject.toml |
| 3. 寫 `gateway/metrics.py` | 30 min | — |
| 4. 在 tool dispatcher / profile switcher / LLM client 埋點 | 1 h | gateway 既有結構 |
| 5. /metrics route | 15 min | — |
| 6. pytest | 30 min | — |
| 7. 手動驗 + promtool check | 15 min | — |

**總計**：~3 h；可獨立 commit。

**啟動建議**：方案 Y Y-1 PoC 結束後啟動（避免雙重 in-flight 拖久）。

---

## §6 Plan C（Docker Secrets PoC）啟動條件

| 步驟 | 工程量 | 跨 session |
|---|---|---|
| 1. `gateway/secrets.py` `read_secret()` | 30 min | 本 session |
| 2. 全 gateway 替換 `os.environ.get(...)` 呼叫 | 1 h | 本 session |
| 3. pytest | 30 min | 本 session |
| 4. docker-compose.platform.yml 加 `secrets:` 段 | 30 min | **CK_AaaP session**（hermes-stack 路徑） |
| 5. `secrets/` 目錄 + .gitignore + README | 15 min | CK_AaaP session |
| 6. e2e 驗（刪 .env 三 key 仍可用） | 30 min | 本 session |

**總計**：~3 h（本 session ~2 h）。

**啟動建議**：與 Plan B 並行；secrets 與 metrics 完全獨立。

---

## §7 跨 Session 接力協議（依 CONVENTIONS §7）

| 工件 | 起源 session | 採納 session | 觸發 |
|---|---|---|---|
| spike report | hermes-agent | CK_AaaP（採納至 ADR-0020） | 立即可採 |
| 方案 Y 設計 | hermes-agent | CK_AaaP（pull 進 hermes-stack 治理） | Y-1 PoC 通過後 |
| Master Plan v2 R1 補丁段 | hermes-agent | CK_AaaP（inline 至原 master plan） | 待使用者授權 |
| CLI Missive pilot 步驟 | hermes-agent | CK_AaaP（提供 CK_Missive/SOUL.md） | 待 SOUL 落地 |
| Plan B/C 設計 | hermes-agent | hermes-agent（自己實作） | 使用者啟動 |

**紀律**：本 session 不 push CK_AaaP / CK_Missive 任何檔案。所有跨 repo 動作走「設計 → 採納 → 實作」三段。

---

## §8 時程建議（W0 = 本週 2026-05-04）

| 週 | hermes-agent session | CK_AaaP session |
|---|---|---|
| W0 | ✅ Spike 完成 / ✅ 方案 Y 設計 / ✅ post-spike takeaways | — |
| W0+1d | Plan B 啟動（gateway metrics）；CLI Missive pilot 步驟文件 | 採納 spike + 方案 Y 至 ADR-0020；推 CK_Missive/SOUL.md |
| W1 | Plan B 完成；Plan C 啟動 | 方案 Y entrypoint patch 部署（hermes-stack）；採納 R1 補丁 |
| W2 | Plan C 完成；CLI Missive pilot 啟動 7 天計時 | Y-2 router 腳本 + Telegram /switch |
| W3 | Missive pilot 中段觀察 | Y-3 Web UI panel（選配）|
| W4 | Missive 7 天結算（tool-calling 成功率 baseline） | ADR-0014 GO/NO-GO 評估 |

---

## §9 待你裁示

| # | 決策 | 預設 |
|---|---|---|
| 1 | Phase 4 cleanup 是否採選項 (b) 保留 7 天 | **是** |
| 2 | 方案 Y Y-1 entrypoint patch 何時啟動 | **W0+1d**（CK_AaaP session 採納後本 session 提供 patch） |
| 3 | Master Plan v2 R1 補丁段，由本 session 直接 append 還是等 CK_AaaP session inline | **等 CK_AaaP**（保留治理紀律） |
| 4 | Plan B 是否本 session 立即啟動 | **是**（與方案 Y 並行不衝突） |
| 5 | Plan C 是否本 session 立即啟動 | **是**（secret 與 metric 獨立） |
| 6 | CLI Missive pilot 步驟文件是否本 session 立即起草 | **是**（純設計，零風險） |

如全採預設，請覆「全採預設」即可。否則請逐項調整。

---

**完成**：post-spike 後續題索引就緒；方案 Y 設計文件就緒；等候使用者裁示啟動下一輪。
