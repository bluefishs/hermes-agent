# Shadow Baseline — Anthropic Provider Tag 補強指南

> **日期**：2026-04-29
> **執行 session**：CK_Missive
> **對應 roadmap**：#8 shadow baseline model_tag
> **狀態**：審視校正 + 補強 SOP

## 重要校正（針對先前覆盤）

先前覆盤建議「為 baseline 加 model_tag 欄位」是**部分誤判**：

1. ✅ `scripts/checks/shadow-baseline-report.cjs` 已有 `by_actual_llm` 分組（L100–105、L184–187）
2. ✅ `app/core/inference_provider_context.py` 已有 ContextVar 機制
3. ✅ `app/services/ai/agent/shadow_logger.py` 已有 `actual_llm_provider` 欄位 + auto-fill from context（L228–233）
4. ✅ `app/core/ai_connector.py` 已在 `_track_and_return` 自動 `set_actual_provider(provider)`（L264）

**結論**：報告層 + 紀錄層 + Context 層**全部就緒**。Anthropic 進來時只要走相同 helper，分組統計自動有效。

## 真正待補的兩件事

### 1. ai_connector 內加 Anthropic / Hermes escalate 路徑

shadow_logger.py L215 註解列舉合法 provider 是 `groq / ollama / nvidia / openai`——
**沒有 anthropic**。Anthropic 需要實際被 ai_connector 呼叫並 tag。

最低耦合做法：**走 Hermes Gateway，Missive 不直接呼叫 Anthropic**。Hermes 已經是 OpenAI-compat API，
帶 `model: claude-sonnet-4-6` 即觸發 escalate（H 條 patch infra 已備）。

```python
# app/core/ai_connector.py 新增分支（建議插在 prefer_local 路徑之後、Groq 路徑之前）
#
# Hermes Escalate 路徑（路線 B 強化版）—
# 觸發條件：task_type in ("escalate", "complex_reasoning") 或 caller 顯式請求
# Hermes Gateway 內部根據 model 參數路由到 Anthropic
if task_type in ("escalate", "complex_reasoning") and HERMES_GATEWAY_URL:
    try:
        logger.info("Hermes-escalate: 嘗試 Hermes Gateway 路徑 (model=claude-sonnet-4-6)")
        client = openai.AsyncOpenAI(
            base_url=HERMES_GATEWAY_URL.rstrip("/") + "/v1",
            api_key=HERMES_API_KEY,
        )
        resp = await client.chat.completions.create(
            model="claude-sonnet-4-6",
            messages=messages,
            temperature=temperature,
            timeout=60,
        )
        result = resp.choices[0].message.content or ""
        return await _track_and_return(result, "hermes-anthropic-escalate", "claude-sonnet-4-6")
    except Exception as e:
        logger.warning("Hermes-escalate failed, falling back: %s", e)
        _record_fallback("hermes-anthropic-escalate", "groq", "escalate_failed")
        # 落到下方 Groq 路徑
```

關鍵：`_track_and_return(result, "hermes-anthropic-escalate", ...)` 第二參數 `"hermes-anthropic-escalate"`
就是 actual_llm_provider 的值——**baseline by_actual_llm 自動分組**，無需改 .cjs。

### 2. shadow_logger.py 註解補正（純文件）

```python
# Line 215 註解：
- actual_llm_provider: **實體 LLM provider**（groq / ollama / nvidia / openai）。
+ actual_llm_provider: **實體 LLM provider**（groq / ollama / nvidia / openai /
+                       hermes-anthropic-escalate / hermes-groq / hermes-ollama）。
```

`hermes-*` 前綴標記「經 Hermes Gateway 路由」，與 Missive 直接呼叫的 `groq` / `ollama` 區別。

## 環境變數（CK_Missive .env 新增）

```bash
# Hermes Gateway escalate 整合（路線 B 強化版）
# Missive 把複雜 task 透過 Hermes Gateway 路由到 Anthropic
HERMES_GATEWAY_URL=http://host.docker.internal:8642
HERMES_API_KEY=<同 hermes-stack secrets/api_server_key.txt>
```

## CK_Missive session 採納步驟（30 min）

```bash
cd D:/CKProject/CK_Missive

# 1. 補 ai_connector escalate 分支（依上方 code patch）
# 編輯 app/core/ai_connector.py，加 HERMES_GATEWAY_URL/HERMES_API_KEY env 讀取 + escalate 分支

# 2. shadow_logger.py 註解補正
# 編輯 app/services/ai/agent/shadow_logger.py L215 註解

# 3. .env 加 HERMES_GATEWAY_URL / HERMES_API_KEY

# 4. 加 unit test
# tests/core/test_ai_connector_hermes_escalate.py
# - mock openai client，驗 task_type=escalate 走 Hermes 路徑
# - 驗 _track_and_return("hermes-anthropic-escalate", ...) 被呼叫
# - 驗 escalate 失敗時 fallback 到 Groq

# 5. commit
git add app/core/ai_connector.py \
        app/services/ai/agent/shadow_logger.py \
        tests/core/test_ai_connector_hermes_escalate.py \
        .env.example
git commit -m "feat(ai): add hermes-gateway escalate path for complex_reasoning tasks (route B)

新增 task_type=escalate/complex_reasoning 時走 Hermes Gateway 的路徑，
Hermes 內部根據 model=claude-sonnet-4-6 路由到 Anthropic。
shadow_logger 自動以 'hermes-anthropic-escalate' 標記，by_actual_llm 分組生效。

Refs: hermes-agent docs/plans/shadow-baseline-anthropic-tag-2026-04-29.md
      hermes-agent docs/plans/escalate-config-patch-2026-04-29.md (infra)"
```

## 驗收

```bash
# 1. 觸發 escalate
curl -H "X-API-Token: $MISSIVE_TOKEN" \
     http://localhost:8001/api/ai/agent/query_sync \
     -d '{"question": "/escalate 跨域分析", "channel": "test"}'

# 2. 確認 shadow_trace.db 有 hermes-anthropic-escalate 紀錄
python -c "import sqlite3; c=sqlite3.connect('backend/logs/shadow_trace.db'); \
           print(c.execute(\"SELECT actual_llm_provider, COUNT(*) FROM query_trace GROUP BY 1\").fetchall())"

# 3. 重跑 baseline 報告
node scripts/checks/shadow-baseline-report.cjs
# 預期 by_actual_llm 分組出現 hermes-anthropic-escalate 列
```

## 與 ADR-0014 GO/NO-GO 的關聯

ADR-0014 GO 判準：tool-calling success rate ≥ 70%（7 天）。

加上 escalate path 後，baseline 可以**分層比較**：
- `groq` 直接路徑：日常請求 success rate
- `hermes-groq` 路徑：經 Hermes 路由後的 success rate（驗證 Hermes 不衰減品質）
- `hermes-anthropic-escalate`：複雜任務 success rate（驗證 escalate 真有提升）

三個指標都 ≥ 70% → 路線 B 強化版穩定，ADR-0014 GO 強化證據。

## 變更歷史

- **2026-04-29** — 校正先前「需加 model_tag 欄位」誤判 + 真正工作清單

## 相關文件

- `app/core/ai_connector.py` — escalate 分支加在此
- `app/core/inference_provider_context.py` — ContextVar 機制（已就緒）
- `app/services/ai/agent/shadow_logger.py` — 自動填欄（已就緒）
- `scripts/checks/shadow-baseline-report.cjs` — by_actual_llm 已支援
- `hermes-agent/docs/plans/escalate-config-patch-2026-04-29.md` — Hermes 端 infra
