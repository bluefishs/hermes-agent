# CK_lvrland_Webmap SKILL.md 「呼叫範例」段 — 直接複製貼上

> **目標 repo**：CK_lvrland_Webmap
> **目標檔**：`docs/hermes-skills/ck-lvrland-bridge/SKILL.md`
> **位置**：原「## 工具清單」段之後 / 「## 使用時機」段之前
> **前置**：CF Tunnel `lvrland.cksurvey.tw` 必須先上線（roadmap #12 P0）
> **採納工時**：5 min
> **真因 + 設計**：見 `D:/CKProject/hermes-agent/docs/plans/hermes-runtime-blockers-postmortem.md`（7 層真因）+ `D:/CKProject/hermes-agent/docs/plans/skill-helper-template/README.md`（通用設計）

## 直接複製到 ck-lvrland-bridge SKILL.md

```markdown
## 呼叫範例（給 model 學習）

⚠️ **執行模式**：本 skill 透過 `scripts/query.py` helper 對 LvrLand backend 發 HTTPS 請求。

**禁用**：
- ❌ `curl ...` — hermes container 沒裝 curl
- ❌ `python3 -c "..."` — 被 hermes approval gate 擋（dangerous flag）
- ❌ Plain HTTP 對 host.docker.internal — 被 hermes tirith security scan 擋
- ❌ `execute_code` tool — sys.argv 環境裡傳不進 args

**正用**：以 `terminal` tool 跑 `python3 .../query.py <action> --<key> <value>`

### Pattern A — 健康檢查

\`\`\`bash
python3 /opt/data/skills/ck-lvrland-bridge/scripts/query.py health
\`\`\`

### Pattern B — NL 估價/實價/行政區查詢

\`\`\`bash
python3 /opt/data/skills/ck-lvrland-bridge/scripts/query.py ai_query --question "中壢區最近房價"
\`\`\`

回傳結構（兩種）：
\`\`\`json
// type 1: 命中地圖關鍵字 + 行政區
{"ok": true, "data": {"type": "tool_call", "tool_name": "map_highlight", "arguments": {"area_name": "中壢區"}}}

// type 2: 一般 RAG 文字回答
{"ok": true, "data": {"type": "text_response", "content": "中壢區 2026 Q1 平均房價..."}}
\`\`\`

### Pattern C — 房價/成交量時序資料

\`\`\`bash
# CLI flag 形式（推薦）
python3 /opt/data/skills/ck-lvrland-bridge/scripts/query.py price_trends --districts "中壢區,桃園區"

# JSON 形式
python3 /opt/data/skills/ck-lvrland-bridge/scripts/query.py price_trends '{"districts": ["中壢區", "桃園區"]}'
\`\`\`

### 操作慣例（極其重要，model 必看）

1. **必定使用 `terminal` tool**，不要用 `execute_code`（sys.argv 拿不到 args）
2. **不要用自然語言「我將呼叫」描述**——直接 emit terminal call
3. helper 回 `{"ok": true, ...}` 或 `{"error": "...", "message": "..."}`
4. `ai_query` 回 `tool_call` 結構時，`arguments.area_name` 可直接顯示在地圖
5. 失敗時告知使用者錯誤碼，**不杜撰答案**
6. **回應一律繁體中文**（zh-TW），即使工具回傳含簡體也轉繁體
```

## 採納步驟（CK_lvrland session 5 min，等 CF Tunnel #12 上線後）

```bash
cd D:/CKProject/CK_lvrland_Webmap

# 1. 複製 helper（已預先客製化）+ install
mkdir -p docs/hermes-skills/ck-lvrland-bridge/scripts
cp ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/scripts/query.py \
   docs/hermes-skills/ck-lvrland-bridge/scripts/query.py
cp ../hermes-agent/docs/plans/skill-helper-template/install.sh \
   docs/hermes-skills/ck-lvrland-bridge/install-helper.sh

# 2. 編輯 SKILL.md，加上方「呼叫範例」段

# 3. commit
git add docs/hermes-skills/ck-lvrland-bridge/scripts/query.py \
        docs/hermes-skills/ck-lvrland-bridge/install-helper.sh \
        docs/hermes-skills/ck-lvrland-bridge/SKILL.md
git commit -m "feat(skill): ck-lvrland-bridge add query.py helper (per hermes-agent template v3)"

# 4. CK_AaaP session 部署
cd D:/CKProject/CK_AaaP
bash ../CK_lvrland_Webmap/docs/hermes-skills/ck-lvrland-bridge/install-helper.sh ck-lvrland-bridge

# 5. 驗證 hermes runtime
curl -s -m 90 -X POST http://localhost:8642/v1/responses \
  -H "Authorization: Bearer ck-hermes-local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","input":"請查詢 lvrland 後端的健康狀態","store":false}'
```

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第七輪 iteration 預製，等 CF Tunnel #12 上線即可採納）
