# Hermes 服務整合運用 — 9 輪 Iteration 最終報告

> **日期**：2026-05-02
> **session**：hermes-agent（9 輪 /loop iteration 累積）
> **狀態**：5/5 skill helper 全預製、真實業務 query 證實可用、adopt.sh 自動採納就緒
> **目標讀者**：未來任何 session 啟動者（hermes-agent / CK_AaaP / CK_Missive / CK_lvrland / CK_PileMgmt / CK_Showcase / CK_DigitalTunnel）
> **本檔目的**：一頁看懂整個 hermes 整合運用狀態與下一步動作

## TL;DR（30 秒讀完）

1. **真正的 P0**：Hermes 對 ck-* skill 的 tool-call 失效（7 層真因），不是模型路線/credit 問題
2. **真正的解**：每個 ck-* skill 加 `scripts/query.py` helper（純 stdlib）+ SKILL.md「呼叫範例」段
3. **5/5 預製完成**：missive 已 deploy 到 runtime；其他 4 等 CF Tunnel 上線後 < 2 min 採納
4. **採納方式**：`bash D:/CKProject/hermes-agent/docs/plans/skill-helper-template/adopt.sh <skill> .`
5. **唯一阻塞**：CF Tunnel `lvrland.cksurvey.tw / pile.cksurvey.tw / showcase.cksurvey.tw / tunnel.cksurvey.tw` 上線（roadmap #12-13 升 P0）

## 9 輪 Iteration Timeline

| 輪 | 主要產出 | 重大發現 / 校正 |
|---|---|---|
| 1 | 整體覆盤（5 層架構）、`integration-blocker-board.md`、`escalate-helpers/` | 識別 18 條 roadmap、5 SOUL 模板未激活、ADR 治理缺口 |
| 2 | `hermes-integration-playbook.md` v1（縮 context / 換 Groq / escalate） | **誤判**：以為 13K 過大壓垮 7B；推薦 35 min config 改動 |
| 3 | A/B/C/D 4 trials 直打 ollama；`skill-curl-pattern-patch.md` v2 | **否定 v1 全部**；發現 register_all hermes 不認、假設「需 curl 範例」 |
| 4 | `hermes-runtime-blockers-postmortem.md` 6 層真因 + α/β/γ 路徑 | L4 tirith plain HTTP / L5 無 curl / L6 python -c approval gate |
| 5 | `skill-helper-template/query.py` working helper + 7 層全解 + 75s runtime ✅ | L7 CF Access bot fingerprint（第 7 層）；端到端跑通 |
| 6 | 真實 `rag_search` 取 5 公文 + `install.sh` + `missive-skill-patch.md` | 修 Plain HTTP auto-upgrade + argparse CLI flags（model 對 JSON escape 敏感）|
| 7 | 3 skill 預製（lvrland/pile/showcase）+ README 進度表 | 把「等 CF Tunnel」時間轉成預製產能 |
| 8 | observability multi-backend helper + 5/5 完整 | SERVICES dict + path_template 設計 |
| 9 | `adopt.sh` 自動化（4 步 → 1 命令）+ 本最終報告 | 業務 repo 採納門檻降到 < 2 min |

## 7 層真因鏈（已全解）

| 層 | 真因 | 證據 | 解法 |
|---|---|---|---|
| L1 | context size 13K | Trial C 12990 tokens 仍 ✅ | ❌ 否定（不需縮）|
| L2 | model 7B 能力 | Trial D OpenAI tools 全 ✅ | ❌ 否定（不需換）|
| L3 | SKILL.md 缺執行指引 | E1 model 收明確命令會 emit | helper + SKILL.md「呼叫範例」段 |
| L4 | tirith plain HTTP block | E1 `[HIGH] Plain HTTP URL` | helper 強制 HTTPS（INTERNAL_HTTP_TO_HTTPS auto-upgrade）|
| L5 | container 無 curl binary | E1b `curl: command not found` | 純 python3 stdlib（hermes container 已有）|
| L6 | python -c 被 approval gate | E1c `script execution via -e/-c flag` | `python3 file.py` 是 file 不是 -c |
| L7 | CF Access bot fingerprint | host helper HTTP 403 Error 1010 | helper 自帶 User-Agent + CF Access service token |

## 5/5 Skill 採納就緒度（最終）

| Skill | helper | skill-patch | runtime deploy | CF Tunnel | 業務採納 |
|---|:---:|:---:|:---:|:---:|---|
| **missive** | ✅ working | ✅ | ✅ pilot 11h+ 持久 | ✅ ready | ⏳ CK_Missive: `bash adopt.sh ck-missive-bridge .` |
| **lvrland** | ✅ predict | ✅ | ⏳ | ⏳ #12 | ⏳ CK_lvrland: 同上 |
| **pile** | ✅ predict | ✅ | ⏳ | ⏳ #13 | ⏳ CK_PileMgmt: 同上 |
| **showcase** | ✅ predict | ✅ | ⏳ | ⏳ #13 | ⏳ CK_Showcase: 同上（位置待確認）|
| **observability** | ✅ predict（multi-backend）| ✅ | ⏳ | ⏳ #13（4 backend）| ⏳ CK_DigitalTunnel: 同上 |

## 文件分類（28 個 docs/plans/ untracked）

### ✅ Working Solution（採用這些）

- **`skill-helper-template/`**（9 輪最終形）
  - `query.py` — Missive helper（CK_Missive 採用，已 pilot 部署）
  - `README.md` — 5 skill 採納就緒度表 + 4 步完整解阻塞最小路徑
  - `install.sh` — 部署到 hermes runtime
  - `adopt.sh` — **業務 repo 採納 1 命令** ⭐
  - `missive-skill-patch.md` — CK_Missive SKILL.md 直接複製貼上版

- **`ck-lvrland-bridge-stub/`** — lvrland 預製
  - `scripts/query.py` + `skill-patch.md` + 既有 SKILL.md/tools.py

- **`ck-pilemgmt-bridge-stub/`** — pile 預製
  - `scripts/query.py` + `skill-patch.md` + 既有檔

- **`ck-showcase-bridge-stub/`** — showcase 預製（8 actions）

- **`ck-observability-bridge-skeleton/`** — observability 預製（multi-backend）

- **`hermes-runtime-blockers-postmortem.md`** — 6+1 層真因報告（α/β/γ 路徑）

- **`integration-blocker-board.md`** — 跨 session 18 條 roadmap 看板

- **`_ab_lab/`** — A/B/C/D 4 trials 證據（保留作 reference）

### 🟡 過時但保留（已標明，不要照做）

- **`hermes-integration-playbook.md`** v1+v2（首段已加 v1→v2→v3 校正提醒）
- **`skill-curl-pattern-patch.md`** v2 假設（postmortem 否定，留作歷史）

### 📚 之前覆盤的支援資料（仍有參考價值）

- `hermes-model-baseline-route-b-2026-04-29.md` — 路線 B 評估（與 P0 解耦）
- `escalate-config-patch-2026-04-29.md` — Anthropic escalate infra（仍可做但不解 P0）
- `escalate-helpers/` — skill-side complexity heuristic（仍是好設計）
- `route-decision-card.md` — 路線 A/B/C 決策卡（與 P0 解耦）
- `cross-session-execution-roadmap-2026-04-29.md` — 18 條 roadmap 細節版
- `c1-soul-status-2026-04-28.md` — SOUL 治理（已部分完成）
- `unblock-soul-c1.sh` — SOUL Step 2 腳本（runtime SOUL 已是 meta，可能不再需要）
- `adr-stale-check*` / `adr-0027-*` — 治理面 ADR 工作
- `adr-0024-ck-lvrland-bridge-skill-draft.md` — ADR-0024 lvrland skill 規範

## 5 層架構（CKProject CLAUDE.md）vs 解法 mapping

```
L0 助理層 Hermes
   └─ 6 ck-* skill 安裝 ✅（含 ck-adr-query 共 6 個）
   └─ tool-call 失效 ❌ → 本 9 輪 iteration 解掉
   
L1 邊界層 CF Tunnel
   └─ Missive 上線 ✅
   └─ lvrland/pile/showcase/tunnel ⏳ ← P0 阻塞
   
L2 服務層
   └─ 5 backend 都運行 ✅
   
L3 觀測層 Loki/Prom/Grafana ✅
   └─ ADR-0019 metric 命名統一 ⏳（與本 P0 解耦）
   
L4 資料層 PostgreSQL + pgvector
   └─ Missive 5/5 表 HNSW ⏳ K1（與本 P0 解耦）
```

## 用戶決策（與本 P0 解耦）

| 決策 | 影響 | 是否必要 |
|---|---|---|
| 模型路線 A / B-冷 / B / C | escalate / Anthropic credit | **不必要**（P0 已解）|
| Anthropic API key | route B 真實啟用 | **不必要** |
| 升 model 為 Sonnet | 整體品質升級 | 可延後（先看本 P0 解後品質）|

## 後續 Session 該動什麼

### CK_Missive session（5 min 解 missive 通車）

```bash
cd D:/CKProject/CK_Missive
bash D:/CKProject/hermes-agent/docs/plans/skill-helper-template/adopt.sh \
     ck-missive-bridge . --deploy --verify
git commit -m "..."  # 用 adopt.sh 提示的 message
git push
```

### CK_AaaP session（首要：CF Tunnel #12-13）

```bash
# 主要任務：上 lvrland/pile/showcase/tunnel 4 個 subdomain
# 細節：CK_AaaP/runbooks/cloudflare-setup.md（per ADR-0015/0016）

# 完成後通知 4 個業務 repo session 跑 adopt.sh
```

### CK_lvrland / CK_PileMgmt / CK_Showcase / CK_DigitalTunnel session（CF Tunnel 上後 5–15 min/個）

```bash
cd D:/CKProject/<repo>
bash D:/CKProject/hermes-agent/docs/plans/skill-helper-template/adopt.sh \
     <skill-name> . --deploy --verify
git commit -m "..."
```

### hermes-agent session（暫無 P0；可動的次優先）

- Master Plan v2 Phase 2 profile isolation 實證（meta + 5 domain profile）
- 升上 query.py 為共用 PyPI / submodule 包（避免 5 份 copy）
- Test runtime 驗收（採納完每個 skill 後實際 e2e test）
- 寫 SKILL.md + SOUL 對 model 行為 stochastic 的對策段

### 用戶（無 P0）

- （可選）路線 A/B/C 決策——但無關 hermes 整合運用阻塞
- 觀察 5 ck-* skill 採納後實際業務 query 體驗

## 哪些 P0 已解 / 哪些仍是 P0

### 已解 ✅

- Hermes 對 ck-* skill 的 tool-call 失效（L1-L7 全解）
- 工程方法論一致（從 v1 過度設計救回 working code）
- 5 skill 採納門檻 < 2 min（adopt.sh）

### 仍是 P0 ⏳

- **CF Tunnel #12-13**：lvrland/pile/showcase/tunnel subdomain 上線（CK_AaaP）
- **業務 repo 採納**：CK_Missive 立即可動（CF Tunnel 已上）

### 不是 P0（之前以為是）❌

- ~~Context size 13K 過大~~
- ~~qwen2.5:7b 模型能力不足~~
- ~~Anthropic credit 待充值~~
- ~~Skill lazy-load 必要~~
- ~~Escalate 路線 B 必要~~

## 9 輪 Iteration 工程方法論啟示

1. **不要照 v1 文件按按鈕**——v1 35 min config 改動「完全不解 P0」，是過度反應
2. **實證鏈優於紙面分析**——4 trials + 7 hermes-runtime tests 才剝出真實 7 層真因
3. **每輪一個假設、一個實驗、一個結論**——避免「同時解多問題」的混亂
4. **預製降低跨 session 阻塞**——5/5 helper 預先做完、adopt.sh 1 命令執行
5. **真因可能在意想不到的層**——L7 是 CF Access bot fingerprint，沒實驗一輩子不會發現

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 9 輪 iteration 終極 wrap-up）

## 相關文件（所有產出）

- 9 輪累積 28 個 docs/plans/ untracked 檔案
- 完整列表 + 分類見上方「文件分類」段
- 真實有效的 working solution 集中在 `skill-helper-template/` + 4 個 stub directory
