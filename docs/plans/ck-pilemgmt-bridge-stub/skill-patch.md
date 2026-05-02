# CK_PileMgmt SKILL.md 「呼叫範例」段 — 直接複製貼上

> **目標 repo**：CK_PileMgmt
> **目標檔**：`docs/hermes-skills/ck-pilemgmt-bridge/SKILL.md`
> **前置**：CF Tunnel `pile.cksurvey.tw` 必須先上線（roadmap #13 P0）+ PileMgmt backend 補 `/api/ai/query`（ADR-0023 Tool 2）
> **採納工時**：5 min（health + celery_status 立即可用；ai_query 等 backend 補完）

## 直接複製到 ck-pilemgmt-bridge SKILL.md

```markdown
## 呼叫範例（給 model 學習）

⚠️ **執行模式**：本 skill 透過 `scripts/query.py` helper 對 PileMgmt backend 發 HTTPS 請求。

**禁用**：curl / `python3 -c` / plain HTTP / `execute_code` tool（同其他 ck-* skill）

### Pattern A — 健康檢查

\`\`\`bash
python3 /opt/data/skills/ck-pilemgmt-bridge/scripts/query.py health
\`\`\`

### Pattern B — Celery 工作佇列狀態

\`\`\`bash
# 全部佇列
python3 /opt/data/skills/ck-pilemgmt-bridge/scripts/query.py celery_status

# 特定佇列
python3 /opt/data/skills/ck-pilemgmt-bridge/scripts/query.py celery_status --queue_filter "pile_processing"
\`\`\`

回傳結構：
\`\`\`json
{"ok": true, "data": {
  "active": [...], "scheduled": [...], "reserved": [...], "workers": [...]
}}
\`\`\`

### Pattern C — NL 樁位查詢（⚠️ backend 待補）

\`\`\`bash
python3 /opt/data/skills/ck-pilemgmt-bridge/scripts/query.py ai_query --question "本月新增幾根樁"
\`\`\`

⚠️ **PileMgmt backend 尚未實作 `/api/ai/query`**（per ADR-0023 Tool 2 status: awaiting_backend）。
呼叫此 action 會回 `{"error": "backend_endpoint_missing", "status": 404, ...}`，告知使用者。

### 操作慣例

1. **必定 `terminal` tool**，不要 `execute_code`
2. 不用自然語言「我將呼叫」，直接 emit terminal call
3. `celery_status` 適合「樁管理今天卡住了嗎？」「現在跑哪些 job？」
4. `ai_query` 失敗時，告知使用者「PileMgmt 的 NL 查詢端點尚未上線」，建議改用其他工具
5. **回應一律繁體中文**
```

## 採納步驟（CK_PileMgmt session 5 min，等 CF Tunnel #13 上線後）

```bash
cd D:/CKProject/CK_PileMgmt
mkdir -p docs/hermes-skills/ck-pilemgmt-bridge/scripts
cp ../hermes-agent/docs/plans/ck-pilemgmt-bridge-stub/scripts/query.py \
   docs/hermes-skills/ck-pilemgmt-bridge/scripts/query.py
cp ../hermes-agent/docs/plans/skill-helper-template/install.sh \
   docs/hermes-skills/ck-pilemgmt-bridge/install-helper.sh

# 編輯 SKILL.md 加上方「呼叫範例」段
# git commit + CK_AaaP install + 驗證（同 lvrland 步驟）
```

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第七輪 iteration 預製）
