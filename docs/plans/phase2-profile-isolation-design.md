# Master Plan v2 Phase 2 — Profile Isolation 設計探索

> **日期**：2026-05-02
> **session**：hermes-agent（第 10 輪 iteration）
> **狀態**：設計探索（非執行；先確認假設與路徑）
> **配對**：`master-integration-plan-v2-2026-04-19.md`（Phase 2 細節）+ `hermes-runtime-blockers-postmortem.md`（7 層真因）+ `hermes-integration-final-report.md`（9 輪 wrap-up）

## 為何 Phase 2 仍重要（即使 P0 已解）

9 輪 iteration 的 helper + adopt.sh **解掉 P0 tool-call 失效**，但留下 3 個次優問題：

| 次優問題 | 原因 | Phase 2 如何解 |
|---|---|---|
| Stochastic 行為 | qwen2.5:7b 在 13K context 偶選錯 tool（execute_code vs terminal）| 每 profile 只載 1 SKILL.md (~2K tokens)，model 視野清楚 |
| SOUL/skill 人格衝突 | meta SOUL（觀察者）+ 業務 ck-* bridge 同時掛 | meta profile 無 ck-* skill；domain profile 有業務人格 SOUL + 對應 skill |
| 簡體中文滲入（30%） | qwen2.5:7b 對 zh-TW follow ≈ 70%，與 prompt 雜訊正相關 | 小 prompt → 指令 follow 提升 |

**結論**：Phase 2 不是 P0 阻塞但是 **品質提升的下一里程碑**。

## 與 9 輪 Helper 結構的關係（不互斥）

| 元件 | 9 輪 helper | Phase 2 profile | 關係 |
|---|---|---|---|
| `query.py` | 1 份 / skill 在業務 repo `docs/hermes-skills/<skill>/scripts/` | 不變 | profile 切換不動 helper |
| SKILL.md | 注入到 hermes prompt context | 只有對應 profile 載入 | 從「6 個全載」降到「1 個對應 profile 載」|
| SOUL.md | 全 profile 共用 meta soul | 每 profile 各自 SOUL | meta = Semiont 觀察者；domain = Muse 業務人格 |
| backend HTTPS endpoint | 同 | 同 | 不變 |
| adopt.sh | 同 | 同 | 採納方式不變 |

**結論**：9 輪 helper 是 Phase 2 的下層設施。Phase 2 只切「上層 profile 隔離」，不重做下層。

## 6 Profile 結構

```
~/.hermes/profiles/
├── meta/                          ← Semiont-like 共同大腦
│   ├── SOUL.md                    ← 觀察者人格（已部署）
│   ├── wiki/                      ← Karpathy LLM Wiki（已部署）
│   ├── skills/                    ← 只載 llm-wiki + meta tool
│   └── config.yaml                ← model: qwen2.5:7b（共用）
│
├── missive/                       ← Muse-like Missive 業務 agent
│   ├── SOUL.md                    ← 「坤哥」Missive 意識體（per c1-soul-status）
│   ├── wiki/                      ← Missive 專屬 wiki
│   ├── skills/
│   │   └── ck-missive-bridge/     ← 只此一個 ck-* skill
│   └── config.yaml                ← model 同 meta（共用 ollama）
│
├── lvrland/                       ← Muse-like LvrLand 業務 agent
│   └── ... (同上 missive 結構)
│
├── pile/                          ← Muse-like PileMgmt 業務 agent
│   └── ...
│
├── showcase/                      ← Muse-like Showcase 治理 agent
│   └── ...
│
└── observability/                 ← Muse-like Observability 巡檢 agent
    └── ...
```

## Phase 2 實證 Plan（先 Missive pilot）

### Step 0 — 前置（已完成）

- ✅ Hermes 已支援 profile（CLI: `hermes profile create/switch/list/delete`）
- ✅ HERMES_HOME 路徑已建立：`~/.hermes/profiles/meta/`
- ✅ 5 SOUL 模板已備：`docs/plans/soul-templates/{meta,missive,lvrland,pile,showcase}.soul.md`

### Step 1 — Missive profile 建立（30 min）

```bash
# 從 hermes-agent session
hermes profile create missive --home ~/.hermes/profiles/missive

# 採用 Missive SOUL（per docs/plans/soul-templates/missive.soul.md）
cp docs/plans/soul-templates/missive.soul.md ~/.hermes/profiles/missive/SOUL.md

# 配置 missive profile 的 config.yaml（只啟 ck-missive-bridge）
cat > ~/.hermes/profiles/missive/config.yaml <<'EOF'
model:
  provider: custom
  model: qwen2.5:7b-ctx64k
  base_url: http://ck-ollama:11434/v1
  api_key_env: OLLAMA_API_KEY
  context_length: 65536

toolsets:
  enabled: [core, code]

skills:
  enabled:
    - ck-missive-bridge      # 只此一個

gateway:
  platforms:
    api_server:
      enabled: true
EOF

# 連結 ck-missive-bridge skill（symlink 或 cp）
mkdir -p ~/.hermes/profiles/missive/skills
cp -r ~/.hermes/skills/ck-missive-bridge ~/.hermes/profiles/missive/skills/
```

### Step 2 — 切 profile + e2e 測試（10 min）

```bash
hermes profile switch missive

# 預期：prompt token ~5K（vs meta profile 13K）
# 預期：tool-call 觸發率 90%+（vs meta profile 70%）
# 預期：簡體中文滲入 < 10%

curl -s -m 90 -X POST http://localhost:8642/v1/responses \
  -H "Authorization: Bearer ck-hermes-local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","input":"請查中壢區簽約的公文","store":false}'
```

### Step 3 — 對照組 baseline（30 min）

把 meta profile（當前 runtime）視為對照組，跑 10 次同樣業務 query：

| Metric | meta profile（當前）| missive profile（pilot 預期）|
|---|---|---|
| prompt_tokens | ~13K | ~5K |
| tool-call 觸發率 | ~70%（stochastic）| ~90% |
| 簡體中文混入率 | ~30% | < 10% |
| 平均響應時間 | 75s | < 60s |
| user 滿意度（主觀）| 中 | 高 |

### Step 4 — 5 profile rollout（依序，每個 1 週實測）

成功 missive 後依序：lvrland → pile → showcase → observability

每個約 30 min 建立 + 7 天實測。

## 與 ADR-0020 Phase 1/2/3 對齊

| ADR-0020 Phase | 內容 | 與 profile isolation 關係 |
|---|---|---|
| Phase 0（已完成）| 治理對齊 | 無關 |
| **Phase 1**（進行中）| Hermes 4 bridge skill | **本 9 輪 iteration 完成**（5/5 helper 預製）|
| Phase 1.5（提案）| profile isolation pilot | **本檔提案**：在 Phase 2 前先做 |
| Phase 2 | Showcase 治理 API 遷入 AaaP | 不受 profile 影響（後端遷移）|
| Phase 3 | DigitalTunnel 觀測棧併入 docker-compose.platform.yml | 不受 profile 影響 |
| Phase 4（最終）| 一鍵 git clone + docker compose up | 自動含 profile 配置 |

**建議**：把 profile isolation 視為 ADR-0020 Phase 1.5（在 Phase 1 完成後、Phase 2 之前的次階段）。

## 風險（per Master Plan v2 R1-R12）

| # | 風險 | 緩解 |
|---|---|---|
| R1 | profile 機制在 docker container 內未充分測試 | Step 1 單獨 missive pilot 試水溫；不行退回 single SOUL + skill filter |
| R2 | GPU 切 profile 時 KV cache 重建延遲 | 按需激活 + ollama keep_alive 設大 |
| R3 | SOUL symlink 在 Windows Docker 不穩 | 用 cp 代替 symlink，接受手動 sync |
| R12 | profile 機制無法獨立 SOUL | 改採 `/persona` slash command Option Y |

## 預期收益（Phase 1.5 完成後）

1. **Stochastic 行為大幅改善**：每 profile prompt 5K → tool-call 觸發率 70% → 90%
2. **SOUL 人格清晰**：meta = 觀察者 / domain = 業務專家；用戶可感知差異（V4 願景）
3. **簡體中文減少**：30% → < 10%
4. **未來增加新 ck-* skill 不會稀釋既有 profile context**：與其他 skill 隔離

## 不做（暫緩）

- **per-profile 不同 model**：保持共用 qwen2.5:7b（GPU 限制）；除非用戶決定 escalate 路線
- **profile 自動切換**：用戶手動 `hermes profile switch <name>`，避免 runtime 自動 reroute 的複雜度
- **跨 profile 共享 wiki/skill**：每 profile 完全獨立（只共用 ollama backend）

## 工時與優先序

| Step | 工時 | 優先 | 阻塞 |
|---|---|---|---|
| 1 missive pilot | 30 min | P1 | Hermes profile 機制實證需 |
| 2 e2e 測試 | 10 min × 10 trials = 100 min | P1 | Step 1 完成 |
| 3 baseline 對照 | 100 min | P1 | Step 1 完成 |
| 4 rollout 4 profile | 30 min × 4 + 7 days × 4 = 1 個月 | P2 | Step 1-3 證明 missive pilot 成功 |

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第 10 輪 iteration；探索性設計，待用戶授權執行）

## 相關

- `docs/plans/master-integration-plan-v2-2026-04-19.md` — Phase 2 原始設計
- `docs/plans/c1-soul-status-2026-04-28.md` — SOUL 治理（Missive Muse 移到 CK_Missive）
- `docs/plans/soul-templates/{meta,missive,lvrland,pile,showcase}.soul.md` — 5 SOUL 模板
- `docs/plans/hermes-runtime-blockers-postmortem.md` — 7 層真因（解 P0；本檔解次優）
- `docs/plans/hermes-integration-final-report.md` — 9 輪 wrap-up
- `CK_AaaP/adrs/0020-aaap-platform-with-hermes-control-plane.md` — 平臺化 ADR
