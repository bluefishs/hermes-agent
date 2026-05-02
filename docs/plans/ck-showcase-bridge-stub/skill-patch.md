# CK_Showcase SKILL.md 「呼叫範例」段 — 直接複製貼上

> **目標 repo**：CK_Showcase（注意 ADR-0020 Phase 2 計劃遷入 CK_AaaP/platform/services/）
> **目標檔**：`docs/hermes-skills/ck-showcase-bridge/SKILL.md`
> **前置**：CF Tunnel `showcase.cksurvey.tw` 必須先上線（roadmap #13 P0）
> **採納工時**：10 min（actions 多，需驗證每個 endpoint）

## 直接複製到 ck-showcase-bridge SKILL.md

```markdown
## 呼叫範例（給 model 學習）

⚠️ **執行模式**：本 skill 透過 `scripts/query.py` helper 對 Showcase 治理 API 發 HTTPS 請求。
8 actions 對應 8 endpoints。

**禁用**：curl / `python3 -c` / plain HTTP / `execute_code` tool

### Pattern A — 健康檢查

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py health
\`\`\`

### Pattern B — 受管專案清單（無 args）

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py managed_projects
\`\`\`

### Pattern C — ADR 跨 repo 地圖查詢

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py adr_map_query
\`\`\`

### Pattern D — 治理健康度（需 project_id）

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py governance_health --project_id ck_missive
\`\`\`

### Pattern E — 平臺指標（window 預設 30d）

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py platform_metrics --window 7d
\`\`\`

### Pattern F — Skill 同步狀態（需 project_id）

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py skills_sync_status --project_id ck_missive
\`\`\`

### Pattern G — Agent 清單（需 project_id）

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py agents_list --project_id ck_missive --status_filter active
\`\`\`

### Pattern H — 安全掃描（destructive — 需 token + safe_mode）

\`\`\`bash
SHOWCASE_API_TOKEN=<token> \
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py security_scan --safe_mode true
\`\`\`

### Pattern I — SSO 狀態（需 project_id）

\`\`\`bash
python3 /opt/data/skills/ck-showcase-bridge/scripts/query.py sso_status --project_id ck_missive
\`\`\`

### 操作慣例

1. **必定 `terminal` tool**，不要 `execute_code`
2. 不用自然語言「我將呼叫」描述
3. 大部分 actions 為 read-only（無需 token），`security_scan` 寫入需 token
4. 治理類查詢（governance_health / sso_status / skills_sync_status）需 `project_id` 為已知 repo 名稱
5. **回應一律繁體中文**
```

## 採納步驟（CK_Showcase session 10 min，等 CF Tunnel #13 上線後）

```bash
cd D:/CKProject/CK_Showcase
mkdir -p docs/hermes-skills/ck-showcase-bridge/scripts
cp ../hermes-agent/docs/plans/ck-showcase-bridge-stub/scripts/query.py \
   docs/hermes-skills/ck-showcase-bridge/scripts/query.py
cp ../hermes-agent/docs/plans/skill-helper-template/install.sh \
   docs/hermes-skills/ck-showcase-bridge/install-helper.sh

# 編輯 SKILL.md 加上方「呼叫範例」段
# 注意：8 個 endpoint 路徑要對到 Showcase backend 真實 schema
# 採納前先 host 端跑一次 health 確認 endpoint 對

# git commit + CK_AaaP install + 驗證
```

## ADR-0020 Phase 2 影響

ADR-0020 Phase 2 規劃 Showcase 治理 API 遷入 `CK_AaaP/platform/services/`。
若採納本 patch 時 Showcase 已遷移，**SHOWCASE_BASE_URL 改為 `https://aaap-platform.cksurvey.tw`** 或新 endpoint。
路徑保持不變即可。

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第七輪 iteration 預製）
