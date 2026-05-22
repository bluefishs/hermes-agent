# L21 — Hermes Runtime Dispatching Diagnose Plan

> 觸發：2026-05-22 用戶實測 demo，連續 12 層 diagnostic 揭穿 hermes-stack 三容器 healthy 但全鏈不通
> Memory：[[feedback-pre-demo-functional-verification]]、[[feedback-integration-over-scope]]
> 政策框架：[`CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)
> 性質：**診斷優先，patch 後置** — 不預設 memory 中的根因斷言為真

---

## 0. 為什麼是「診斷」而非「patch」

[feedback_pre_demo_functional_verification.md](C:\Users\User1\.claude\projects\D--CKProject-CK-Hermes\memory\feedback_pre_demo_functional_verification.md) 寫的根因「hermes runtime hard-coded fallback to openrouter，無視所有配置」**是觀察推論，非代碼證據**。

代碼 spot check 給出反例：

| 觀察 | memory 推論 | 代碼實況 |
|---|---|---|
| `:8642 OpenAI API 一律 401` | hard-coded fallback to openrouter | `gateway/platforms/api_server.py:760-772` 的 401 是 **Gateway Bearer auth 失敗**（API_SERVER_KEY 不對），完全在 LLM 路由之前 |
| `:9119 沒對話 UI` | feature flag `--tui` 未啟 | 待查 `hermes_cli/web_server.py` 是否真有 TUI 模式 flag |
| `:3000 Open WebUI Exit 137` | port 被 missive frontend 佔 | 跨 stack port 衝突，與 hermes 本身無關 |

→ 三個現象可能是 **三個獨立 bug** 而非一個 runtime dispatching bug。先分離、再定根因。

---

## 1. 三條獨立調查線

### 🔵 線 A — `:8642` 401 真實鏈路

**假設樹**：

```
401 root cause
├─ A1: API_SERVER_KEY env 未設於 server，client 仍送 Bearer → check_auth 早返
│       fix：hermes-stack/.env 注入 API_SERVER_KEY；客戶端用對應 token
├─ A2: API_SERVER_KEY 兩端不同步（server 從 secrets/，client 從別處）
│       fix：對齊 secrets 載入路徑
├─ A3: 真到了 LLM 上游 → openrouter API key 401（這才是 memory 推論的場景）
│       fix：查 _resolve_runtime_agent_kwargs 解到哪個 provider，是否真錯走 openrouter
└─ A4: client 根本沒帶 Authorization header（curl 漏寫）
        fix：客戶端
```

**判定步驟**（≤ 30 min）：

```bash
# 1. 客戶端 curl 確認帶了 Bearer
curl -v http://localhost:8642/v1/chat/completions \
  -H "Authorization: Bearer $API_SERVER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"hi"}]}'

# 2. 看 hermes-gateway container log，401 是 _check_auth 還是 upstream
docker logs hermes-gateway 2>&1 | grep -E "401|Bearer|Invalid API key" | tail -20

# 3. 如果是 _check_auth：check container env
docker exec hermes-gateway env | grep -E "API_SERVER_KEY|HERMES_INFERENCE_PROVIDER"

# 4. 如果是 upstream LLM 401：看 _resolve_runtime_agent_kwargs 解到哪
docker exec hermes-gateway python -c "from gateway.run import _resolve_runtime_agent_kwargs; import json; print(json.dumps({k:v for k,v in _resolve_runtime_agent_kwargs().items() if k!='api_key'}, default=str))"
```

**判定產出**：A1 / A2 / A3 / A4 哪一條為真。

---

### 🔵 線 B — `:9119` 對話 UI 缺失

**假設樹**：

```
9119 沒對話 UI
├─ B1: hermes-web 服務只開 status 不開對話端點（設計如此，非 bug）
│       fix：對話本應走 :8642 OpenAI API 或 :3000 Open WebUI
├─ B2: 對話端點存在但需 explicit flag (--ui chat / HERMES_WEB_MODE=chat) 未啟
│       fix：hermes-stack/.env 注入對應 flag
└─ B3: 對話端點存在但前端 build 漏（dist 缺）
        fix：rebuild image
```

**判定步驟**（≤ 20 min）：

```bash
# 1. hermes_cli/web_server.py 看路由表
grep -n "app.router.add\|@app\.route\|router.add" hermes_cli/web_server.py

# 2. 對 :9119 列可用路徑
curl -s http://localhost:9119/ | grep -E "chat|prompt|message" | head -10
curl -s http://localhost:9119/_routes 2>/dev/null || echo "no _routes endpoint"

# 3. 看 dist 結構
docker exec hermes-web ls -la /app/web/dist 2>/dev/null || docker exec hermes-web find / -name "index.html" 2>/dev/null | head -5
```

**判定產出**：對話 UI 應該在哪個 port + 怎麼啟。

---

### 🔵 線 C — `:3000` Exit 137 + port 衝突

**假設樹**：

```
3000 Open WebUI Exit 137
├─ C1: 同 host 已有 missive frontend 佔 :3000 (CK_Missive PM2)
│       fix：hermes-stack docker-compose 改 ports: "3001:8080"
├─ C2: OOM (137 = SIGKILL，常見 memory limit)
│       fix：docker-compose 加 mem_limit
└─ C3: 配置依賴 hermes-gateway 但啟動順序未保證
        fix：depends_on + healthcheck condition
```

**判定步驟**（≤ 15 min）：

```bash
# 1. 跨 host 看誰佔 :3000
netstat -ano | findstr :3000   # Windows
# OR
lsof -iTCP:3000 -sTCP:LISTEN   # POSIX

# 2. Exit 137 原因
docker inspect open-webui --format '{{json .State}}' | jq .

# 3. 看 compose port mapping
grep -A 3 "open-webui:" CK_AaaP/runbooks/hermes-stack/docker-compose.yml
```

**判定產出**：是 port 衝突還是 OOM 或 dependency。

---

## 2. 三線交叉判定矩陣

| 結果 | A 線 | B 線 | C 線 | 結論 |
|---|---|---|---|---|
| **單獨 A1/A2** + B1 + C1 | 配置漂移 | 設計如此 | port 衝突 | **零 patch，純 config 修復**；memory 推論誤判 |
| **A3** + 任何 B/C | LLM 路由 bug | — | — | **L3 patch 候選** — 觸發 ADR-CK-001 |
| **A4** + 任何 B/C | client side | — | — | 客戶端問題，hermes 無關 |
| A1 + **B3** + C3 | 配置 | image build | depends_on | **stack 設定 bug**，CK_AaaP 端修 |

---

## 3. ADR-CK-001 觸發條件

僅當 §2 結論落在「**L3 patch 候選**」（A3 + 真實 runtime bug）才寫 ADR-CK-001。準入要點（依 [`CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md) §2）：

- [ ] upstream 同 bug 確認尚未修：`gh issue list --repo NousResearch/hermes-agent --search "openrouter fallback"`
- [ ] 無 L1/L2 替代：plugin 點是否可接管 provider 解析？
- [ ] upstream PR 草稿
- [ ] CK 端的最小 patch（傾向 monkey-patch in plugin > 改 core）

---

## 4. 排除（明確不在本診斷範圍）

- 不修 hermes-stack docker-compose（CK_AaaP session 動）
- 不重 build hermes image（CK_AaaP session 動）
- 不動 Missive 端 PM2 port 設定
- 不啟動 ADR-CK-001 寫作（直到 §2 結論明確）

---

## 5. 執行序

| 序 | 動作 | session | 工時 | DoD |
|---|---|---|---|---|
| ① | 線 A 4 步診斷 | CK_AaaP（host 端可 docker exec）| 30 min | A1/A2/A3/A4 判定 |
| ② | 線 B 3 步診斷 | CK_AaaP | 20 min | B1/B2/B3 判定 |
| ③ | 線 C 3 步診斷 | CK_AaaP（host）| 15 min | C1/C2/C3 判定 |
| ④ | 寫 §2 結論 | CK_Hermes（本 session 可接）| 10 min | 矩陣某格被選中 |
| ⑤ | 依結論分流：config 修 → CK_AaaP；ADR-CK-001 → CK_Hermes | — | depends | — |

**總工時上界**：1.5h 診斷 + （若 L3）2-4h patch 寫作 + upstream PR

---

## 6. 寫進 wiki lesson 的時機

[feedback_pre_demo_functional_verification.md](C:\Users\User1\.claude\projects\D--CKProject-CK-Hermes\memory\feedback_pre_demo_functional_verification.md) 指明要寫 `[[lesson-hermes-runtime-dispatching-bug-2026-05-22]]`。**等 §4 結論明確再寫**，避免結論先於分析（呼應本檔 §0「不預設 memory 斷言為真」）。

---

## 7. 與第三波 v2 計畫的接點

| v2 計畫項 | 本診斷如何接 |
|---|---|
| ③ Ollama fallback 啟動 | 線 A 若結論是 A3（LLM 路由 bug），Ollama fallback 變成更迫切的繞道 |
| ④ 真實端到端跑通 | 必須 §2 結論「零 patch」或「ADR-CK-001 patch 已上」才能跑 |
| H-1 CK_FORK_POLICY.md | ✅ 已先於本檔落地，為 §3 提供決策框架 |
| R3 real-stack probe e2e | 本檔 §2 矩陣定案後，R3 才知道要 probe 什麼 |

---

## 8. 等待

本檔產出 = R1 完成。實際線 A/B/C 診斷需要 **host 端 docker access**（CK_AaaP session）。

下一個本 session 可動的：R3（real-stack probe e2e）和 R4（CROSS_SESSION_NEXT_3.md）— 但 R3 需要在 §2 結論之後才能寫對 endpoint。

**建議**：先收 R4（單頁 checklist），把線 A/B/C 列為待 CK_AaaP session 接手的第一動作。
