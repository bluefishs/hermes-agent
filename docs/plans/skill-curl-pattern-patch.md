# SKILL.md curl-pattern Patch — 解 P0 tool-calling 失效真因

> **日期**：2026-05-01
> **依據**：A/B/C/D 4 trials 證據 + hermes codebase grep 確認
> **影響**：5 個 ck-* bridge skill（missive/lvrland/pile/showcase/observability）
> **執行 session**：各業務 repo（CK_Missive / CK_lvrland / CK_PileMgmt / CK_Showcase / CK_DigitalTunnel）
> **工時**：每 skill 5–10 min；全部 30 min

## 真因（4 layers，第 3 層才是 P0）

| 假設 | 證據 | 結論 |
|---|---|---|
| L1: 13K prompt context 過大 | Trial C: 12990 tokens 仍 ✅ tool_call | ❌ 否定 |
| L2: qwen2.5:7b model 能力不足 | Trial D: OpenAI tools schema 全 ✅ | ❌ 否定 |
| **L3: ck-* SKILL.md 沒教 model 用 terminal/curl** | grep `register_all` in hermes codebase = 0 hits；arxiv skill 有 curl 範例 | ✅ **真因** |
| L4: SOUL meta 觀察者人格疊加抑制 | SOUL「不主動搶話、有問先問回去」 | 🟡 次因（疊加效應）|

## 設計慣例校正

Hermes（NousResearch fork）的 skill 設計：
- **SKILL.md 是 prompt context 注入**，不是 tool registry
- Skill **不獨立 register 為 OpenAI tool**
- Model 看 SKILL.md 後用 hermes core toolset（`terminal`/`web_extract` 等）自行呼叫 backend
- ck-* `tools.py` 內的 `register_all(registry)` 是 **CK 自定義 convention，hermes 不認**

對比：
- ✅ **Hermes 內建 arxiv skill**：SKILL.md 有清楚的 `curl "https://..."` 範例，model 直接學會
- ❌ **CK ck-missive-bridge**：SKILL.md 只列「tool name → endpoint」對照表，靠 `tools.py` 自動 register（但實際 hermes 不呼叫 register_all）

## ck-missive-bridge SKILL.md Patch（範本）

把現有的「工具清單」段（line 32–49 左右）後面**追加一節**：

```markdown
## 呼叫範例（給 model 學習）

### Pattern A — RAG 公文查詢（最常用）

\`\`\`bash
curl -s -X POST \\
  -H "Authorization: Bearer ${MISSIVE_API_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "<USER_QUESTION>"}' \\
  "${MISSIVE_BASE_URL}/api/ai/rag/query"
\`\`\`

回傳 JSON 結構：
\`\`\`json
{"results": [{"title": "...", "content": "...", "score": 0.87}]}
\`\`\`

### Pattern B — KG 實體搜尋

\`\`\`bash
curl -s -X POST \\
  -H "Authorization: Bearer ${MISSIVE_API_TOKEN}" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "<ENTITY_NAME>", "limit": 10}' \\
  "${MISSIVE_BASE_URL}/api/ai/graph/entity"
\`\`\`

### Pattern C — 健康檢查（工具測試）

\`\`\`bash
curl -s "${MISSIVE_BASE_URL}/api/health"
\`\`\`

### 操作慣例

- 必定使用 `terminal` tool 跑 curl，不要用自然語言「我將呼叫」描述
- `MISSIVE_BASE_URL` 與 `MISSIVE_API_TOKEN` 從環境變數讀取
- 若 backend 不可達，告知使用者「Missive 後端目前無回應」，不杜撰答案
```

把上方 patch 加到 ck-missive-bridge SKILL.md 後，model 看到後就會學會用 terminal/curl 呼叫，不再用「我將呼叫」假裝。

## 5 個 ck-* skill 統一 patch 模板

| Skill | env vars | 主要 endpoint | curl pattern |
|---|---|---|---|
| ck-missive-bridge | MISSIVE_BASE_URL / MISSIVE_API_TOKEN | /api/ai/rag/query / /api/ai/graph/entity | Pattern A/B/C |
| ck-lvrland-bridge | LVRLAND_BASE_URL / LVRLAND_API_TOKEN | /api/v1/ai/query / /api/v1/analytics/price-volume-trends | 仿 A/C |
| ck-pilemgmt-bridge | PILE_BASE_URL / PILE_API_TOKEN | /api/v1/ai/query / /api/v1/celery/status | 仿 A/C |
| ck-showcase-bridge | SHOWCASE_BASE_URL | /api/skills/list / /api/agents/list / /api/security/scan | 多 GET pattern |
| ck-observability-bridge | LOKI_BASE_URL / PROM_BASE_URL / GRAFANA_BASE_URL | /loki/api/v1/query_range / /api/v1/query | 多端 GET pattern |

每個 skill 把對應 curl 範例加到 SKILL.md，並標明 `必定使用 terminal tool 跑 curl，不要用自然語言描述呼叫`。

## SOUL 校正建議（次優先）

當前 runtime SOUL = `meta.soul.md`（Semiont-like 觀察者）：
- 「不主動搶話、有問先問回去」這條會讓 model 在 ck-* tool-call 時也猶豫
- meta 應該用「不直接處理業務」自然會延後到「business agent 處理」

**Master Plan v2 Phase 2 解法**（最終態）：
- meta profile：只啟 llm-wiki，不掛 ck-* bridge
- missive profile：只啟 ck-missive-bridge，SOUL 換業務人格（坤哥）
- 其他 profile 同理

**短期 hack**：在 SOUL 加一段：

```markdown
## 例外：當使用者明確要求查業務資料時
即使你是 meta 觀察者，使用者明確問業務問題（公文、案件、房價、樁位、ADR 等），
你**必須**直接呼叫對應 ck-* skill 的 curl 命令取得真實資料，**不要**只「反思」或
「提問回去」。提供事實後再加你的觀察反思，不能用「反思」迴避執行。
```

## 驗證 SOP（CK_Missive session 跑一次即可）

```bash
cd D:/CKProject/CK_Missive

# 1. 套 SKILL.md patch
# 把上方 Pattern A/B/C 加到 docs/hermes-skills/ck-missive-bridge/SKILL.md

# 2. 部署到 hermes runtime（CK_AaaP session 跑 docker cp）
docker cp docs/hermes-skills/ck-missive-bridge/SKILL.md \
          ck-hermes-gateway:/opt/data/skills/ck-missive-bridge/SKILL.md
docker compose restart hermes-gateway   # 約 30s

# 3. 驗證
curl -s -m 60 -X POST http://localhost:8642/v1/responses \
  -H "Authorization: Bearer ck-hermes-local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","input":"請查詢 Missive 後端的健康狀態","store":false}' | \
  python -c "import sys,json; d=json.load(sys.stdin); [print(o.get('type'),o.get('name','')) for o in d.get('output',[])]"

# 預期看到（成功）：
#   function_call terminal
#   function_call_output {"stdout":"...health response..."}
#   message
#
# 仍失敗則回頭看 SOUL 校正段。
```

## 與 Phase 2 Profile 隔離的關係

本 patch 是「短期內讓現狀 runtime 能用」的修補。**Master Plan v2 Phase 2** 的最終解才是：
- 一個 meta profile + 4 個 domain profile
- 每個 profile 只掛自己 SOUL + 自己 bridge skill
- 各自人格 + 各自工具 → 沒有「meta 觀察者拿業務 bridge」的尷尬

但 Phase 2 工時 1 週。本 patch 30 min 就讓 runtime 能用，CP 值高。

## 變更歷史

- **2026-05-01** — 初版（hermes-agent session 第三輪 iteration 產出，A/B/C/D trials 證據）

## 相關

- `docs/plans/_ab_lab/run_ab.py` + `run_trial_d.py` — 實驗證據腳本
- `docs/plans/_ab_lab/results.json` + `results_d.json` — 實驗結果
- `docs/plans/hermes-integration-playbook.md` — 之前的 playbook（**根因診斷需校正**，本檔取代）
- `/opt/data/skills/research/arxiv/SKILL.md`（hermes runtime）— 對照範本
- `/opt/hermes/agent/prompt_builder.py:196` — TOOL_USE_ENFORCEMENT_MODELS 證據
