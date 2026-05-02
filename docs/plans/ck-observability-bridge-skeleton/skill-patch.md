# CK_DigitalTunnel SKILL.md 「呼叫範例」段 — 直接複製貼上

> **目標 repo**：CK_DigitalTunnel（observability stack 主 repo）
> **目標檔**：`docs/hermes-skills/ck-observability-bridge/SKILL.md`
> **特殊性**：本 skill **multi-backend**（4 個 backend：Loki / Prom / Grafana / Alertmanager），與其他 4 個 ck-* skill 不同
> **前置**：CF Tunnel #13 上線 4 個 observability backend HTTPS endpoint
> **採納工時**：15 min（actions 多 + 4 backend env 配置）

## 直接複製到 ck-observability-bridge SKILL.md

```markdown
## 呼叫範例（給 model 學習）

⚠️ **執行模式**：本 skill 透過 `scripts/query.py` helper 對 4 個觀測棧 backend 發 HTTPS 請求。

**禁用**：curl / `python3 -c` / plain HTTP / `execute_code` tool（同其他 ck-* skill）

**必設環境變數（4 個 backend HTTPS endpoint）**：
| Env | 用途 | CF Tunnel 預設（path-based）|
|---|---|---|
| `OBS_LOKI_URL` | Loki LogQL 查詢 | `https://tunnel.cksurvey.tw/loki` |
| `OBS_PROMETHEUS_URL` | Prometheus 指標查詢 | `https://tunnel.cksurvey.tw/prometheus` |
| `OBS_GRAFANA_URL` | Grafana dashboard | `https://tunnel.cksurvey.tw/grafana` |
| `OBS_ALERTMANAGER_URL` | Alertmanager 警示 | `https://tunnel.cksurvey.tw/alertmanager` |
| `GRAFANA_USER` / `GRAFANA_PASS` | Grafana basic auth（可選）| — |
| `CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET` | CF Access service token（若啟用）| — |

### Loki actions（日誌查詢）

\`\`\`bash
# 過去 N 小時某 service 的日誌（query 需 LogQL syntax）
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py loki_query \
  --query '{job="hermes"}' --limit 50

# 已知 label keys
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py loki_labels
\`\`\`

### Prometheus actions（指標查詢）

\`\`\`bash
# Instant query
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py prom_query \
  --query 'up{job="hermes"}'

# Range query（需 start / end / step）
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py prom_query_range \
  --query 'rate(http_requests_total[5m])' \
  --start 1730000000 --end 1730003600 --step 15s
\`\`\`

### Grafana actions（dashboard 管理）

\`\`\`bash
# Grafana 自身健康
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py grafana_health

# 搜 dashboard / folder
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py grafana_search \
  --query "missive" --type dash-db --limit 10

# 取單一 dashboard
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py grafana_dashboard \
  --dashboard_id abcd1234
\`\`\`

### Alertmanager actions（警示管理）

\`\`\`bash
# 列當前 active alerts（可篩 active / silenced）
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py alert_active \
  --active true --silenced false

# 建立 silence（destructive — 限管理員）
# matchers 為 JSON array
python3 /opt/data/skills/ck-observability-bridge/scripts/query.py alert_silence_create \
  '{"matchers": [{"name":"alertname","value":"HighCPU","isRegex":false}], "startsAt":"2026-05-02T12:00:00Z", "endsAt":"2026-05-02T14:00:00Z", "comment":"maintenance window", "createdBy":"hermes"}'
\`\`\`

### 操作慣例（極其重要）

1. **必定 `terminal` tool**，不要 `execute_code`
2. **不用自然語言「我將呼叫」描述**——直接 emit terminal call
3. 4 個 backend env var 必須統一指向同一 CF Tunnel domain（path-based）或各自 subdomain
4. Loki query 用 LogQL syntax，**不是** SQL（{label="value"} |~ "regex"）
5. Prometheus query 用 PromQL，**不是** SQL（rate() / histogram_quantile() / ...）
6. silence 建立是 destructive，回應前確認使用者意圖
7. **回應一律繁體中文**，把 Loki/Prom 回的 JSON 整理為人類可讀摘要
```

## 採納步驟（CK_DigitalTunnel session 15 min，等 CF Tunnel #13 上線後）

```bash
cd D:/CKProject/CK_DigitalTunnel  # 確認此 repo 路徑

mkdir -p docs/hermes-skills/ck-observability-bridge/scripts
cp ../hermes-agent/docs/plans/ck-observability-bridge-skeleton/scripts/query.py \
   docs/hermes-skills/ck-observability-bridge/scripts/query.py
cp ../hermes-agent/docs/plans/skill-helper-template/install.sh \
   docs/hermes-skills/ck-observability-bridge/install-helper.sh

# 編輯 SKILL.md 加上方「呼叫範例」段
# 注意：4 個 OBS_* env var 必須在 hermes-stack docker-compose 設好

# CK_AaaP session 部署
cd D:/CKProject/CK_AaaP
bash ../CK_DigitalTunnel/docs/hermes-skills/ck-observability-bridge/install-helper.sh ck-observability-bridge

# 驗證（Loki health 最簡單）
curl -s -m 90 -X POST http://localhost:8642/v1/responses \
  -H "Authorization: Bearer ck-hermes-local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","input":"請查詢 Grafana 健康狀態","store":false}'
```

## 與其他 ck-* skill 的差異

| 面向 | 其他 4 skill | ck-observability-bridge |
|---|---|---|
| backend 數量 | 1 | **4** |
| ACTION_HANDLERS | 純 path | 加 `service` 欄位 + 部分 `path_template` |
| auth | 單一 token | Grafana basic auth + CF Access optional |
| env 數量 | 1-2 | 4 backend URL + 2 grafana auth + 2 CF Access |
| query syntax | NL question | LogQL + PromQL（model 需熟）|

**SKILL.md 特別段建議加**：LogQL / PromQL 速查（給 model 學）。

## ADR-0020 Phase 3 影響

ADR-0020 Phase 3 規劃 DigitalTunnel 觀測棧併入 `CK_AaaP/runbooks/platform/docker-compose.platform.yml`。
若採納本 patch 時觀測棧已遷入 AaaP，env 改為新 endpoint 即可，helper 結構不變。

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第八輪 iteration 預製，5/5 helper 系列收尾）
