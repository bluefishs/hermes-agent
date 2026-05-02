# Hermes 服務整合運用 — 端到端驗收 SOP

> **日期**：2026-05-02
> **目的**：採納 ck-* skill helper 後，從用戶角度驗證 hermes 服務整合運用真的可用
> **適用對象**：CK_Missive / CK_lvrland / CK_PileMgmt / CK_Showcase / CK_DigitalTunnel session 採納完 helper 後
> **配對**：`docs/plans/hermes-integration-final-report.md`（整體狀態）+ `skill-helper-template/adopt.sh`（採納自動化）

## 三入口比對

| 入口 | URL | 狀態 | 適合場景 |
|---|---|---|---|
| **hermes-web 內建 UI** | http://localhost:9119/ | ✅ 已運行 | 用戶日常查詢、multi-turn 對話、stochastic 自動 retry |
| OpenAI-compat API | http://localhost:8642/v1/* | ✅ 已運行 | 程式整合 / 自動化 / 第三方 client (Open WebUI, LobeChat 等) |
| Telegram bot | (token gateway 內) | ⚠️ register fail | 移動裝置（待修 Frozen_method_invalid bug）|
| Open WebUI :3000 | (未部署) | ❌ 未啟用 | 可選擴展 |

**驗收主入口**：**hermes-web :9119**（multi-turn 自動 retry stochastic 行為）

## 採納後驗收清單

### Step 1 — 確認 helper 在 runtime（30 秒）

```bash
# 對應的 ck-* skill 名稱
SKILL=ck-missive-bridge   # 或其他

# 確認 helper file 存在 + 跑 health 成功
docker exec ck-hermes-gateway sh -c "ls -la /opt/data/skills/$SKILL/scripts/ && python3 /opt/data/skills/$SKILL/scripts/query.py health"
```

預期：
- `query.py` 列出（約 5–10KB）
- health JSON 回 `{"ok": true, "data": {"status": "healthy", ...}}`

❌ 失敗對策：
- query.py 不在 → 跑 `bash <repo>/docs/hermes-skills/<skill>/install-helper.sh <skill>` 重 deploy
- HTTPS 不通 → 確認 CF Tunnel 對應 subdomain 上線

### Step 2 — OpenAI-API 直測（驗證 model 能 emit terminal call，1 min）

```bash
cat > /tmp/_verify.json <<EOF
{
  "model": "hermes-agent",
  "input": "請查詢 ${SKILL/-bridge/} 後端的健康狀態，使用 terminal 工具執行對應 query.py 的 health action。",
  "store": false
}
EOF

curl -s -m 90 -X POST http://localhost:8642/v1/responses \
  -H "Authorization: Bearer ck-hermes-local-dev-key" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/_verify.json | \
  python -c "
import sys, json
d = json.load(sys.stdin)
for o in d.get('output', []):
    t = o.get('type')
    if t == 'function_call':
        print(f'✅ FUNCTION_CALL: {o.get(\"name\")} args={str(o.get(\"arguments\",\"\"))[:200]}')
    elif t == 'function_call_output':
        out = o.get('output', '')
        if isinstance(out, str):
            try:
                inner = json.loads(json.loads(out).get('output', '{}'))
                if inner.get('ok'):
                    print(f'✅ FUNCTION_OUTPUT ok=True (backend reachable)')
                else:
                    print(f'⚠️  FUNCTION_OUTPUT error: {inner.get(\"message\",\"\")[:200]}')
            except Exception as e:
                print(f'   raw: {str(out)[:200]}')
"
```

預期：兩個 ✅ 或一個 ✅ + 一個帶具體 backend 訊息的 ⚠️

❌ 若 model 沒 emit function_call：
- 是 stochastic 行為（model 偶爾選錯 tool）
- **請改用 hermes-web :9119 multi-turn UI 測**（自動 retry）

### Step 3 — hermes-web :9119 真實互動（multi-turn 體驗，5 min）

1. 開瀏覽器訪問 http://localhost:9119/
2. 輸入用戶查詢（範例見下方對應 skill 的 query 清單）
3. 觀察 hermes 是否真的呼叫 backend（會看到 inline tool progress）
4. 若第一次 model 用文字模擬「我將呼叫」而非真執行，**回覆「請真的執行 terminal 命令取得資料」即可**——multi-turn UI 會 retry

#### Missive query 範例（CF Tunnel 已上）

| 用戶 query | 預期觸發 | 預期結果 |
|---|---|---|
| 「missive 後端健康嗎？」 | `query.py health` | 回 healthy + timestamp |
| 「查中壢區簽約的公文」 | `query.py rag_search --question "中壢區簽約"` | 5 個公文 sources |
| 「乾坤公司有什麼相關文件？」 | `query.py entity_search --name 乾坤` | KG 實體 + 關聯 |
| 「本月新增幾件公文」 | `query.py agent_query --question "本月新增公文"` | 統計 |

#### LvrLand query（待 CF Tunnel #12）

| 用戶 query | 預期 |
|---|---|
| 「lvrland 健康嗎？」 | health |
| 「中壢區房價走勢」 | ai_query → text_response |
| 「在地圖上顯示桃園區」 | ai_query → tool_call: map_highlight |
| 「桃園市 8 行政區成交量」 | price_trends |

#### PileMgmt query（待 CF Tunnel #13）

| 用戶 query | 預期 |
|---|---|
| 「樁管理今天卡住了嗎？」 | celery_status |
| 「現在跑哪些工作」 | celery_status active |
| 「本月新增幾根樁」 | ai_query（**backend 未實作，回 backend_endpoint_missing**）|

#### Showcase query（待 CF Tunnel #13）

| 用戶 query | 預期 |
|---|---|
| 「列出所有受管專案」 | managed_projects |
| 「查 ck_missive 的治理健康度」 | governance_health |
| 「平台過去 7 天指標」 | platform_metrics --window 7d |

#### Observability query（待 CF Tunnel #13）

| 用戶 query | 預期 |
|---|---|
| 「missive 過去 1h 有什麼 errors」 | loki_query --query '{job="missive"} \|~ "ERROR"' |
| 「hermes 是否上線」 | prom_query --query 'up{job="hermes"}' |
| 「列當前 active alerts」 | alert_active |

### Step 4 — 觀察 multi-turn 自動 retry 行為（10 min，重點）

stochastic 是 single-shot 路徑的問題。**multi-turn UI 通常自動回復**：

1. 第一輪 user：「請查中壢區公文」
2. 若 model 用 `execute_code` 或 `python -c`（fail 模式）→ 顯示 error
3. **再 user：「請改用 terminal 工具直接執行 python3 query.py 命令」**
4. Model 第二輪通常會 emit 正確的 terminal call
5. 取真實資料

如果第二輪仍 fail：
- 可能 SKILL.md 「呼叫範例」段沒套上
- 或 helper 在 container 內缺
- 跳回 Step 1 / Step 2 排查

### Step 5 — 用戶體驗驗收標準

採納後 1 週內觀察：

| 指標 | 目標 |
|---|---|
| 業務 query 回實際資料的比例 | ≥ 70%（multi-turn 1–2 turn 內） |
| 用戶判斷「比直接打 backend 好用」 | 主觀 ≥ 60% |
| 簡體中文混入比例 | ≤ 30%（qwen2.5:7b 限制；需要時人工指出「請改繁體」）|
| Hermes 整體響應時間 | ≤ 90s/turn（含 ollama inference + backend call）|

未達標 → 考慮：
- SOUL 加更強硬的「禁簡體」段
- 路線 B-冷 升 B（Anthropic Sonnet 4.6 escalate）
- Master Plan v2 Phase 2 profile isolation（只載 1 SKILL.md，prompt 更乾淨）

## 5 個 ck-* skill 採納後的整合運用清單（最終態）

當 5/5 採納完成 + CF Tunnel #12-13 上線：

```
用戶（hermes-web :9119）
    │
    ▼
「查中壢區公文」 → ck-missive-bridge: rag_search → 5 公文
「中壢區房價」 → ck-lvrland-bridge: ai_query → 估價
「樁管狀態」 → ck-pilemgmt-bridge: celery_status → 工作清單
「ck_missive 治理健康度」 → ck-showcase-bridge: governance_health → 指標
「過去 1h missive errors」 → ck-observability-bridge: loki_query → 日誌
「跨域分析公文 vs 房價」 → 多 ck-* skill chain（multi-turn）
```

## ⚠️ 已知 stochastic 行為清單

採納後可能遇到：

| 現象 | 原因 | 對策 |
|---|---|---|
| model 用「我將呼叫」文字模擬 | qwen2.5:7b 在 13K context 偶發 | multi-turn 直接回「請真執行命令」|
| model 選 `execute_code` 而非 `terminal` | sys.argv 拿不到 args | SKILL.md 明示「禁用 execute_code」|
| 簡體中文混入 | qwen2.5:7b 對 zh-TW 約 70% follow | multi-turn 指出 / 升模型 |
| JSON args escape 損壞 | model 對 inline JSON 敏感 | helper 已支援 CLI flags `--question "..."` 較穩 |
| Approval gate 突然出現 | 寫入操作（如 silence_create）需 user confirm | 預期行為，user 確認即可 |

## 變更歷史

- **2026-05-02** — 初版（hermes-agent 第 10 輪 iteration；用 hermes-web :9119 為主入口而非 Open WebUI）

## 相關

- `docs/plans/hermes-integration-final-report.md` — 9 輪整體狀態 + 後續 session 動作
- `docs/plans/skill-helper-template/adopt.sh` — 採納自動化
- `docs/plans/skill-helper-template/README.md` — 5/5 採納就緒度
- `docs/plans/hermes-runtime-blockers-postmortem.md` — 7 層真因
