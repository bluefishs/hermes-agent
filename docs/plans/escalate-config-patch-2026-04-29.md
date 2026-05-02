# Anthropic Escalate Config Patch（路線 B 強化版基礎建設）

> **日期**：2026-04-29
> **執行 session**：CK_AaaP（套用至 `runbooks/hermes-stack/`）
> **設計原則**：**ANTHROPIC_API_KEY 為空時自動回退路線 A**（現狀 Groq+Ollama），credit 充值與否都能上線
> **狀態**：ready-to-paste patch 草稿

## TL;DR

把 escalate 路徑（Anthropic API key + secrets 機制）一次性鋪好，但**不啟動**。
未來用戶確認路線 B 後，只要：
1. 把 Anthropic key 寫進 `secrets/anthropic_api_key.txt`
2. `docker compose restart hermes-gateway`
3. escalate 立即生效

不確認也沒影響——`groq_api_key.txt` 仍在，hermes 正常 Groq 回應。

## 4 個 Patch（依序套用）

### Patch 1 — `runbooks/hermes-stack/.env.example` § 1 補充

把第 30 行的 `# ANTHROPIC_API_KEY=` 註解改為**啟用提示**（不取消註解，但說明用法）：

```diff
 # =========================================================
 # 1. LLM Provider — Groq 為主、Ollama 兜底（Anthropic 暫緩）
 # =========================================================
 # 主 provider：Groq（config.yaml 已指定 llama-3.3-70b-versatile）
 # ⚠️ ADR-0017 Phase 1B：生產環境改用 secrets/groq_api_key.txt（取代下行 env）
 #    本 GROQ_API_KEY 僅作開發環境 fallback（無 secrets/ 檔案時生效）
 GROQ_API_KEY=
 # Fallback：本地 ck-ollama（不需真實 key，但 OpenAI SDK 要求非空）
 OLLAMA_API_KEY=ollama-local-no-auth
-# Anthropic 暫緩：credit 充值後再啟用，並改 config.yaml 的 model 區塊
-# ANTHROPIC_API_KEY=
+
+# Anthropic Escalate（路線 B 強化版）— **infra ready, 未啟用**
+# 啟用方式：把 key 寫進 secrets/anthropic_api_key.txt（gitignored），重啟 gateway
+# secrets-wrapper.sh 會偵測檔案存在性自動載入；檔不在則此功能停用、退回路線 A
+# 觸發路徑：客戶端請求帶 model: claude-sonnet-4-6 → gateway 路由到 Anthropic
+#         不帶或帶 llama-3.3-70b-versatile → 走 Groq（現狀）
+ANTHROPIC_API_KEY=
+
 # OPENAI_API_KEY=
 # OPENROUTER_API_KEY=
 # GOOGLE_API_KEY=
```

### Patch 2 — `runbooks/hermes-stack/secrets/anthropic_api_key.txt.example` 新增

```text
# Anthropic API key — Path B 強化版 escalate 用
#
# 取得：https://console.anthropic.com/ → API Keys
# 月度預算建議：$20 USD（escalate 比例約 5–10%）
#
# 使用：
#   1. 把這檔複製為 secrets/anthropic_api_key.txt（不帶 .example）
#   2. 把 line 1（這行 comment）刪掉
#   3. 把這行替換為實際 sk-ant-api03-... 字串
#   4. chmod 600 anthropic_api_key.txt
#   5. docker compose restart hermes-gateway
#
# 測試啟用：
#   curl -H "Authorization: Bearer $API_SERVER_KEY" \
#        http://localhost:8642/v1/chat/completions \
#        -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"hello"}]}'
#
# 移除：刪除實際檔，gateway 自動退回 Groq（路線 A）
# rm secrets/anthropic_api_key.txt && docker compose restart hermes-gateway
```

### Patch 3 — `runbooks/hermes-stack/docker-compose.yml` secrets 段補充

```diff
     env_file:
       - ${HERMES_HOST_DIR:-.}/.env
     entrypoint: ["/secrets-wrapper.sh"]
     command: ["gateway"]
     ports:
       - "8642:8642"
     volumes:
       - ${HERMES_HOST_DIR:-hermes_data}:/opt/data
       - ./secrets-wrapper.sh:/secrets-wrapper.sh:ro
     secrets:
       - api_server_key
       - groq_api_key
+      - anthropic_api_key   # 路線 B escalate；檔不存在時 secrets-wrapper 跳過載入
```

```diff
 secrets:
   api_server_key:
     file: ./secrets/api_server_key.txt
   groq_api_key:
     file: ./secrets/groq_api_key.txt
+  anthropic_api_key:
+    file: ./secrets/anthropic_api_key.txt
   webui_secret_key:
     file: ./secrets/webui_secret_key.txt
```

> **⚠️ Docker secrets `file:` 需檔存在才能 compose up**。處理方式：
>
> **選項 A（推薦）**：先 `cp secrets/anthropic_api_key.txt.example secrets/anthropic_api_key.txt`，
> 把內容置為單行佔位 `EMPTY_DISABLED_PLACEHOLDER`，secrets-wrapper.sh 偵測此值跳過 export。
>
> **選項 B**：用 `external: true` 並由 docker secret 命令管理（更彈性，但需 swarm mode）。
>
> 採用選項 A：

```diff
 secrets:
   api_server_key:
     file: ./secrets/api_server_key.txt
   groq_api_key:
     file: ./secrets/groq_api_key.txt
+  anthropic_api_key:
+    file: ./secrets/anthropic_api_key.txt   # 預設置 EMPTY_DISABLED_PLACEHOLDER
   webui_secret_key:
     file: ./secrets/webui_secret_key.txt
```

### Patch 4 — `runbooks/hermes-stack/secrets-wrapper.sh` 加 Anthropic 偵測

```diff
 #!/bin/sh
 # Docker Secrets bridge for Hermes Gateway
 # 從 /run/secrets/* 讀取並 export 為 env，再 exec 上游 entrypoint。
 # 目的：避免 patch upstream Dockerfile/entrypoint，同時讓密碼不出現於 docker inspect。
 # Phase 1B（ADR-0017）：API_SERVER_KEY / GROQ_API_KEY
+# 路線 B 強化版（2026-04-29）：ANTHROPIC_API_KEY（可選）
 # 限制：env 仍存在於 /proc/1/environ；完全消除需 upstream 改 _FILE 慣例。
 set -e

 if [ -f /run/secrets/api_server_key ]; then
     API_SERVER_KEY=$(cat /run/secrets/api_server_key)
     export API_SERVER_KEY
 fi

 if [ -f /run/secrets/groq_api_key ]; then
     GROQ_API_KEY=$(cat /run/secrets/groq_api_key)
     export GROQ_API_KEY
 fi

+# Anthropic（路線 B）— 偵測 placeholder，避免空值或佔位 key 污染 env
+if [ -f /run/secrets/anthropic_api_key ]; then
+    _anthropic_value=$(cat /run/secrets/anthropic_api_key | head -1 | tr -d '\n\r')
+    case "$_anthropic_value" in
+        ""|"EMPTY_DISABLED_PLACEHOLDER"|"#"*)
+            # 空值 / 佔位 / 註解開頭 → 視為未啟用，不 export
+            ;;
+        *)
+            ANTHROPIC_API_KEY="$_anthropic_value"
+            export ANTHROPIC_API_KEY
+            ;;
+    esac
+    unset _anthropic_value
+fi
+
 exec /opt/hermes/docker/entrypoint.sh "$@"
```

### Patch 5 — `runbooks/hermes-stack/config.yaml.example` 註解補充（非必須）

`model` 區塊上方加一段註解說明 escalate 用法：

```diff
 # ── LLM 模型 ──────────────────────────────────────────────
-# 主 provider：Groq（OpenAI-compatible，需 GROQ_API_KEY）
-# Anthropic 暫緩（待 credit 充值後再評估切回）
+# 主 provider：Groq（OpenAI-compatible，需 GROQ_API_KEY）
+# Escalate：Anthropic Sonnet 4.6（路線 B 強化版）
+#   - 客戶端請求帶 `model: claude-sonnet-4-6` → gateway 路由 Anthropic
+#   - ANTHROPIC_API_KEY 為空 → 自動退回 Groq（route A 行為）
+#   - 啟用：secrets/anthropic_api_key.txt 寫入真實 key，重啟 gateway
 model:
   default: llama-3.3-70b-versatile
```

> 註：實際 escalate 路由邏輯由 hermes-gateway 內 OpenAI-API model 參數判斷自動處理（NousResearch fork 標準支援）；config.yaml 本身不需要 `escalate_model` 段。

## 觸發 escalate 的方式（用戶/skill 端）

選一即可：

### 方式 A — Open WebUI 手動切模型
1. Open WebUI 設定 → Models 加 Anthropic provider
2. 對話時選 `claude-sonnet-4-6`
3. 用戶手動觸發

### 方式 B — Skill-side 邏輯（推薦）
ck-missive-bridge / ck-showcase-bridge 等 skill 內判斷複雜度：

```python
# skill 內偽代碼（例：tools.py 內 query 處理）
def _should_escalate(question: str, tool_chain_depth: int) -> str:
    if tool_chain_depth > 4:
        return "claude-sonnet-4-6"
    if len(question) > 2000:
        return "claude-sonnet-4-6"
    if "/escalate" in question:
        return "claude-sonnet-4-6"
    return ""  # 預設走 Groq
```

skill 在 outbound 請求時帶 `model` 參數即可。

### 方式 C — Telegram bot `/escalate` 指令
Telegram 用戶輸入 `/escalate <問題>` 觸發路由。

## CK_AaaP session 一鍵套用

```bash
cd D:/CKProject/CK_AaaP/runbooks/hermes-stack

# 1. 寫 anthropic_api_key.txt.example
cat > secrets/anthropic_api_key.txt.example <<'EOF'
# Anthropic API key — Path B 強化版 escalate 用
# (見 escalate-config-patch-2026-04-29.md)
EMPTY_DISABLED_PLACEHOLDER
EOF

# 2. 預建 placeholder 真實檔（compose up 需檔存在）
cp secrets/anthropic_api_key.txt.example secrets/anthropic_api_key.txt
chmod 600 secrets/anthropic_api_key.txt

# 3. 套 docker-compose.yml patch（手動編輯，依 Patch 3 diff）

# 4. 套 secrets-wrapper.sh patch（手動編輯，依 Patch 4 diff）

# 5. 套 .env.example / config.yaml.example 註解（依 Patch 1 / 5 diff）

# 6. 重啟 gateway 驗收 secrets-wrapper 不報錯
docker compose restart hermes-gateway
docker logs ck-hermes-gateway 2>&1 | head -20
# 預期：無 ANTHROPIC_API_KEY 相關 error；Hermes 正常啟動

# 7. commit
git add runbooks/hermes-stack/
git commit -m "feat(hermes-stack): add anthropic escalate infra (route B-enhanced, key empty by default)

預鋪路線 B 強化版基礎設施：secrets 機制 + secrets-wrapper 偵測。
ANTHROPIC_API_KEY 預設空，行為等同路線 A（Groq+Ollama）。
未來 credit 充值後僅需替換 secrets/anthropic_api_key.txt 內容 + restart。

Refs: hermes-agent docs/plans/hermes-model-baseline-route-b-2026-04-29.md
      hermes-agent docs/plans/escalate-config-patch-2026-04-29.md"
```

## 驗收

- [ ] `docker compose up -d` 在 anthropic_api_key.txt 是 placeholder 時不報錯
- [ ] `docker exec ck-hermes-gateway env | grep ANTHROPIC` 無輸出（key 未啟用時不污染 env）
- [ ] 替換為真實 key 後 `restart`，`env | grep ANTHROPIC` 出現實際值
- [ ] 客戶端帶 `model: claude-sonnet-4-6` 時 gateway 確實路由到 Anthropic（用 mitmproxy 或網路抓包驗證）

## 回滾

```bash
# 退回路線 A
rm secrets/anthropic_api_key.txt
# 從 docker-compose.yml 移除 anthropic_api_key 段
# 從 secrets-wrapper.sh 移除 ANTHROPIC_API_KEY 偵測段
docker compose up -d --force-recreate hermes-gateway
```

或更輕量：把 `anthropic_api_key.txt` 改回 `EMPTY_DISABLED_PLACEHOLDER`，restart 即可（不必改 yaml/wrapper）。

## 變更歷史

- **2026-04-29** — 路線 B 基礎設施 patch 起草（hermes-agent session）

## 相關文件

- `docs/plans/hermes-model-baseline-route-b-2026-04-29.md` — 路線評估
- `docs/plans/cross-session-execution-roadmap-2026-04-29.md` #6 — roadmap entry
- `CK_AaaP/adrs/0017-docker-secrets.md` — Phase 1B 機制
