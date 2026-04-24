# Master Integration Plan v2 — Hermes 共同大腦 + Multi-Agent Bottom-Up

> **版本**：v2（取代 v1 wiki-only 計畫）
> **產出**：2026-04-19
> **架構主軸**：Hermes = 共同大腦 + 導師；各專案 agent 各自獨立成長；回饋由下而上萃取
> **硬約束**：零付費開發；Missive-first；繁體中文 zh-TW；Session 工作目錄分流
> **狀態**：P0 已啟動，P1 需使用者最終確認後才動真實檔案

---

## 0. 架構總覽

```
┌──────────────────────────────────────────────────────────────┐
│  Hermes Meta Profile（共同大腦 + 導師）                      │
│  HERMES_HOME = ~/.hermes/profiles/meta/                      │
│                                                              │
│  ├─ SOUL.md                   — 導師人格（聆聽 ≫ 說教）        │
│  ├─ wiki/                     — Karpathy LLM Wiki 萃取池      │
│  │   ├─ SCHEMA.md                                            │
│  │   ├─ index.md                                             │
│  │   ├─ log.md                                               │
│  │   ├─ briefings/YYYY-MM-DD.md  — 每日各 agent 萃取彙整     │
│  │   ├─ patterns/*.md         — 跨 agent 浮現 pattern         │
│  │   └─ (layer 1/2 標準 Karpathy 結構)                        │
│  ├─ cron/                                                    │
│  │   ├─ 07:30 awakening     — 讀昨日 briefing 播給使用者      │
│  │   ├─ 22:30 extraction    — 掃各 agent tags → 彙整 briefing │
│  │   └─ 每月 1 日 anti-echo  — 本地 qwen2.5 自審附和 pattern   │
│  └─ skills/                  — meta level（llm-wiki）         │
└──────────▲────────▲────────▲────────▲────────────────────────┘
           │ 萃取   │ 萃取   │ 萃取   │ 萃取
           │ (tag)  │ (tag)  │ (tag)  │ (tag)
     ┌─────┴──┐ ┌───┴───┐ ┌──┴───┐ ┌──┴─────┐
     │Missive │ │LvrLand│ │ Pile │ │Showcase│
     │ Agent  │ │ Agent │ │ Agent│ │  Agent │
     │Profile │ │Profile│ │Profile│ │ Profile│
     │(按需啟)│ │(按需) │ │(按需)│ │ (按需) │
     ├────────┤ ├───────┤ ├──────┤ ├────────┤
     │SOUL   ←─ CK_Missive/SOUL.md（canonical）             │
     │wiki/   │ │wiki/  │ │wiki/ │ │wiki/   │
     │tags/   │ │tags/  │ │tags/ │ │tags/   │
     │skills/ │ │skills/│ │skills│ │skills/ │
     └────────┘ └───────┘ └──────┘ └────────┘
     各 agent 獨立成長，不受上層指令干預
     回饋透過 tags/ 由下而上
```

## 1. 決策總覽（v1 → v2 差異）

| # | 問題 | v1 決定 | **v2 決定** |
|---|---|---|---|
| D1 | Wiki 位置 | 單一 `~/.hermes/wiki` | **meta profile 的 wiki 是萃取池；各 agent 有自己 wiki** |
| D2 | Wiki 範圍 | 單一 | **Meta 1 + Agent N（共 5 個 wiki）** |
| D3 | Missive / Wiki 界線 | 同 v1：Missive 業務真相；Wiki meta | 不變 |
| D4 | Wiki 擁有者 | Hermes agent 寫 | 各 agent 寫自己 wiki；meta 只萃取 |
| D5 | 既有 memory 遷入 | 單向遷 | 依領域分配到對應 agent wiki 或 meta wiki |
| D6 | 語言 | zh-TW 硬規則 | 不變；各 SOUL 頂端都加宣告 |
| D7 | 生長方向 | （未明示）| **Bottom-up**：agent 自主成長、meta 不下令 |
| D8 | Agent 實體化 | （未明示）| **I-1 Hermes profile 隔離**（單容器、按需切 profile） |
| D9 | SOUL 落地 | 單一 `~/.hermes/SOUL.md` | **各 repo `{Repo}/SOUL.md`（canonical）** + profile 符號鏈接 |
| D10 | Agent 啟動時機 | 常駐 | **按需激活**：使用者提問命中 domain 才載入 profile |
| D11 | Missive 特殊性 | —  | 首發 pilot；與生產 CK_Missive backend 共用 endpoint（skill 呼叫 public API） |

## 2. 需求還原（與 v1 一致，補 v2 項）

### 技術
- T1–T5（同 v1）+ **T6** Hermes profile 機制實證可用；**T7** Tag-based 萃取 cron 穩定
### 流程
- P1–P3（同 v1）+ **P4** Agent pilot → rollout 漸進路徑（先 Missive，再 1 個一個）
### 策略
- S1–S4（同 v1）+ **S5** ADR-0020 Phase 1 的 4 bridge skills 改為 **bridge persona + skill 組合**（含 SOUL）
### 願景
- V1–V3（同 v1）+ **V4** 各 agent 展現不同人格；使用者可感知差異
- **V5** 共同大腦定期反射 pattern，形成「你的 agent 群體肖像」

## 3. Phase 結構（v2）

### Phase 0 — 盤點 + 計畫 + SOUL 模板（本日，零風險）
- [x] Inventory：Claude memory、`~/.hermes/`、各 repo SOUL/AGENTS（結果：無 SOUL，CLAUDE.md only）
- [ ] **本檔案** `master-integration-plan-v2-2026-04-19.md` ← 正在寫
- [ ] SOUL 骨架 4 份放 `docs/plans/soul-templates/`（未激活，CK_AaaP session 採納時才 push 到各 repo）

### Phase 1 — Meta wiki 骨架（本 session，需使用者授權）
1. `mkdir ~/.hermes/profiles/meta/wiki/{raw/{articles,transcripts,decisions},entities,concepts,comparisons,queries,briefings,patterns}`
2. 寫 `SCHEMA.md` / `index.md` / `log.md`
3. `~/.hermes/config.yaml` 加 `skills.config.wiki.path: ~/.hermes/profiles/meta/wiki`
4. 重啟 hermes-gateway 驗 `/skills` 含 llm-wiki
5. **不遷移既有 memory**（等 Phase 5 分流遷入）

### Phase 2 — Missive agent 首發（CK_AaaP + 本 session 合作）
1. **（CK_AaaP session）** 於 `CK_Missive/SOUL.md` 寫 Missive 專屬 SOUL
2. **（本 session）** `hermes profile create missive --home ~/.hermes/profiles/missive`
3. **（本 session）** 符號鏈接 `~/.hermes/profiles/missive/SOUL.md` → `CK_Missive/SOUL.md`
4. **（本 session）** `ck-missive-bridge` skill 對 missive profile 啟用
5. **（本 session）** Missive profile 建立自己的 `wiki/` + `wiki/tags/`
6. **（本 session）** 測試流程：`hermes profile switch missive` → 問「查公文」→ 驗 skill 呼叫成功 → 回答後由 agent 自行在 wiki/tags/escalate 或 wiki/daily/ 寫記錄
7. **驗收**：7 天實測，tool-calling 成功率 ≥ 70%

### Phase 3 — 萃取機制（cron）
3 個 cron 放 meta profile：
- **22:30 extraction**：掃 `~/.hermes/profiles/*/wiki/tags/escalate-*.md`、`cross-domain-*.md`、`pattern-emerging-*.md` 彙整到 `meta/wiki/briefings/YYYY-MM-DD.md`
- **07:30 awakening**：讀昨夜 briefing，若有新項目播給使用者（Telegram 或 wiki 頁）
- **每月 1 日 anti-echo**：本地 qwen2.5 自審最近 30 天各 agent 的 daily/ 是否出現「過度附和」

**Tag 清單標準（放在每個 agent wiki 的 SCHEMA.md）**：
- `#escalate` — 這事值得 meta brain 看
- `#cross-domain` — 跟其他 agent 有關
- `#pattern-emerging` — 觀察到某模式
- `#human-feedback` — 使用者明確教導
- `#conflict` — 與其他 agent 或使用者意見分歧
- `#quiet` — 純日誌，不需外部注意

### Phase 4 — Defensive autonomy（各 agent 加段）
每個 SOUL template 最末段加「你的自主權」：
1. 使用者請求刪 wiki 檔 → 先摘要該檔再確認
2. 使用者要求修改業務事實（公文金額等）→ 提醒「這是 Missive 真相源，你能查詢但不能修改」
3. 使用者要求刪 memory → 二次確認
4. 使用者指令與 SOUL 衝突時 → 以「我注意到...」提問，不直接拒絕也不盲從

### Phase 5 — 既有 memory 遷入分流
對映規則：

| 原始 Claude memory 檔 | 目標 agent wiki | 備註 |
|---|---|---|
| `feedback_*.md`（語言 / Missive-first / 零付費 / blueprint） | `meta/wiki/concepts/feedback-*.md` | 所有 agent 共享的行為準則 |
| `project_hermes_migration.md` | `meta/wiki/concepts/` + `meta/wiki/raw/decisions/adr-0014-snapshot.md` | meta-level |
| `project_hermes_soul_and_skill.md` | `missive/wiki/concepts/` | Missive 專屬 |
| `project_upstream_sync_*.md` | `meta/wiki/concepts/workflow-upstream-sync.md` | 基礎設施 |
| `project_hermes_local_only_path_*.md` | `meta/wiki/concepts/architecture-local-only.md` | 平台 |
| `project_hermes_self_evolution_pin.md` | `meta/wiki/concepts/reference-self-evolution.md`（帶 defer tag） | meta 觀察 |
| `reference_hermes_ui_endpoints.md` | `meta/wiki/concepts/reference-hermes-endpoints.md` | meta |
| `reference_hermes_upstream.md` | `meta/wiki/concepts/reference-upstream-fork.md` | meta |
| `reference_ckproject_root.md` | 刪除或合併到 `meta/wiki/index.md` |索引類 |
| `MEMORY.md` | 保留（Claude harness 載入用），內容精簡為 pointer → wiki | 硬需求 |

### Phase 6 — 其他 3 個 agent（CK_AaaP session 為主）
Showcase / LvrLand / Pile 各自：
1. CK_AaaP session 寫 `{Repo}/SOUL.md`
2. 本 session `hermes profile create <name>`
3. 對應 bridge skill 部署（目前只有 ck-missive-bridge；其他 3 個是 ADR-0020 Phase 1 產出）
4. 預計跨 W4–W8（ADR-0020 Phase 1 主節奏）

### Phase 7 — Crystal Seed 外放
- 整份架構 + 跨 agent 模板打包為 `CK_AaaP/runbooks/hermes-multi-agent-stack/`
- README 寫「一鍵啟動 CK 多 agent 共同大腦」
- 其他工程顧問公司可 fork 自訂各自 SOUL

## 4. 時序（W0 = 本週，2026-04-19 起）

| 週 | 本 session | CK_AaaP session | 根 session | 外部 |
|---|---|---|---|---|
| W0 | **本計畫寫完 + SOUL 模板**；使用者授權 Phase 1 | — | — | — |
| W1 | **Phase 1** meta wiki 骨架 | Missive SOUL 審稿 | — | — |
| W2 | **Phase 2** Missive profile 建立 + 首發測試 | Missive SOUL 細修 | — | upstream PR 追蹤 |
| W3 | **Phase 3** 萃取 cron 部署 + 7 天實測 | Showcase SOUL 起草 | — | — |
| W4 | **Phase 4** Defensive 段落；Phase 5 memory 遷移首輪 | Showcase SOUL + bridge skill | — | — |
| W5 | Missive 7 天 baseline 出 → ADR-0014 GO/NO-GO 支援 | ADR-0014 決議；LvrLand SOUL | 跨 repo 驗收 | — |
| W6 | 若 GO：Phase 6 首 Showcase agent；若 NO-GO：檢討 | Phase 6 繼續 | — | — |
| W7 | Phase 6 LvrLand agent（若 SOUL 完成） | — | — | — |
| W8+ | Phase 6 Pile agent；Phase 7 Crystal Seed runbook | — | — | — |

## 5. 相依關係

```
P0 盤點 ──► P1 meta wiki 骨架 ──► P2 Missive pilot ──► P3 萃取 cron
                │                        │
                │                        └──► P4 Defensive autonomy
                │
                └──► P5 memory 遷入（與 P2 並行可）
                                            │
                                            ▼
              ┌─ P6 Showcase agent（需 CK_AaaP 先給 SOUL + bridge skill）
              ├─ P6 LvrLand agent（同上）
              └─ P6 Pile agent（同上）
                           │
                           ▼
                 P7 Crystal seed 外放 runbook
```

硬依賴：P1 → P2 → P3；P5 可與 P2/P3 並行；P6 三個 agent 需 CK_AaaP 先給 SOUL + skill。

## 6. 零付費合規

| 動作 | 成本 | 合規 |
|---|---|---|
| Hermes profile 切換 | 0（內建功能） | ✅ |
| Meta wiki filesystem | 0 | ✅ |
| Cron 萃取 | 本地 qwen2.5 + filesystem | ✅ |
| Anti-echo 月審 | 本地 qwen2.5 | ✅ |
| 各 agent SOUL | markdown 寫作 | ✅ |
| Profile 隔離 GPU 負載 | 單一 qwen2.5 context 切換 | ✅ |

**全段零付費**。

## 7. 風險

| # | 風險 | L×I | 緩解 |
|---|---|---|---|
| R1 | `hermes profile` 機制在 container 內未充分測試 | M×H | Phase 2 先只做 Missive 試跑，profile 本身若不行可退回「單 SOUL + skill filter」 |
| R2 | GPU 切 profile 延遲（KV cache 重建） | M×M | 按需激活 + 最近 used profile keep warm（若需要） |
| R3 | SOUL symlink 在 Windows Docker 不穩 | M×M | 用 copy 代替 symlink（接受需手動 sync） |
| R4 | 各 agent tag 無 schema 統一，萃取失敗 | M×H | Phase 3 發布 tag taxonomy 做 SCHEMA.md 強制 |
| R5 | 各 repo SOUL 被 commit 到公開 repo 洩露 | M×H | SOUL 走 `.gitignore` or only CLAUDE.md 引用；SOUL 專業度高的內容不入 git |
| R6 | qwen2.5 生成 tag 不準確、萃取錯失重要事件 | H×M | 月度人工抽查；weekly tidy cron 掃錯位檔 |
| R7 | 使用者感受不到 bottom-up（覺得像 AI 胡說） | M×M | Phase 3 awakening 只在有實質萃取時播報；沈默就沈默 |
| R8 | Missive business 權限 token 散落 N profile | M×H | 統一用 `MCP_SERVICE_TOKEN` 走 env；刪 profile 時同步清 .env 段 |
| R9 | 多 wiki 互引 link rot（path 對 profile 路徑） | M×L | meta wiki 引 agent wiki 用相對路徑 `../missive/wiki/...` |
| R10 | 使用者疲於維護多 SOUL | H×M | SOUL 寫好後本不用常動；Crystal seed 原則「改一次後放著」 |
| R11 | 多 agent 浮現矛盾決策（Missive vs Showcase 說法不同） | M×M | meta SOUL 定仲裁規則（Missive 業務 > Showcase 治理 > Hermes 工程） |
| R12 | Phase 2 發現 Hermes profile 無法獨立 SOUL.md（只一份共用） | L×H | 改採 `/persona` slash command（Option Y）；或延伸 SOUL 包成 skill |

## 8. Session 分流

| 動作 | Session |
|---|---|
| Meta wiki 建立、萃取 cron、anti-echo | **hermes-agent** |
| SOUL 模板起草 | **hermes-agent**（放 docs/plans/soul-templates/） |
| 各 repo SOUL 正式落地 | **CK_AaaP**（push 進 `CK_Missive/SOUL.md` 等） |
| Showcase / LvrLand / Pile bridge skill 規格 | **CK_AaaP** |
| bridge skill 實作 | **hermes-agent** |
| 跨 repo 整合驗收 | **根 session** |
| ADR-0014 baseline 決議 | **CK_AaaP** |

## 9. 成功指標

- [ ] Missive agent 試跑 7 天 tool-calling 成功率 **≥ 70%**
- [ ] Meta wiki 累積 ≥ **10 個萃取條目**（跨 30 天）
- [ ] Hermes `profile list` 顯示 ≥ **2 個**（meta + missive）
- [ ] 各 agent daily/ 連 **14 天**有自主寫入
- [ ] 無跨 profile 污染（`/dump` 檢查 context 不含他 profile 記憶）
- [ ] **V4 可感知**：使用者可明確說出某 agent 「語氣 / 專精 / 關注點」與其他不同
- [ ] **V5 可感知**：使用者能從 briefing 看到「我自己的模式」被反射
- [ ] Anti-echo 月審首跑無系統性「純附和」警訊
- [ ] 零付費合規 audit 通過

## 10. 回滾

| Phase | 回滾 |
|---|---|
| P1 meta wiki | 刪 `~/.hermes/profiles/meta/wiki/`；config.yaml 關 skill |
| P2 Missive profile | `hermes profile delete missive`；skill 復歸 default profile |
| P3 cron | `hermes cron remove` 三個 job |
| P4 Defensive | git revert SOUL 段落 |
| P5 memory 遷移 | 原 Claude memory 保留 1 個月；可 `git checkout` 回指針 |
| P6 其他 agent | 同 P2 逐個回滾 |
| P7 Crystal seed | 刪 runbook 目錄；架構仍可用 |

## 11. 複雜度

| Phase | 工時 | 複雜度 |
|---|---|---|
| P0 盤點 + 模板 | 1.5h | LOW |
| P1 meta wiki | 1h | LOW |
| P2 Missive pilot | 3h | **MED-HIGH**（profile 機制驗證有不確定） |
| P3 萃取 cron | 2h | MED |
| P4 Defensive | 1.5h | LOW |
| P5 memory 遷移 | 2h | MED |
| P6 三 agent × 3 | 6h（需 CK_AaaP session 先有 SOUL） | MED |
| P7 Crystal seed runbook | 1h | LOW |
| **總計（跨多 session）** | **~18h** | **MEDIUM** |

## 12. 關鍵 Open Questions（可後續再回）

1. `hermes profile` 在 Docker 容器內是否能完整隔離（需 Phase 2 實證）
2. SOUL 放 repo 是否要 `.gitignore`？（專業內容是否願意入 git）
3. 使用者覺得 bottom-up 到什麼程度才算「成長」？量化指標還是純主觀？
4. 月度 anti-echo 由本地 qwen2.5 做，信度有限，是否接受為「粗篩」而非權威？

---

**下一步執行（依序，需使用者授權每個外部可見動作）**：
1. 現在 → Phase 0.3 SOUL 模板起草（純 docs/plans/，零風險）
2. 授權 → Phase 1 建 meta wiki 骨架
3. 授權 → Phase 2 Missive profile 試跑（需 CK_AaaP session 配合寫 Missive SOUL）
