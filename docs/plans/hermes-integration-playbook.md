# Hermes 服務整合運用實戰指南 — Playbook + 斷點診斷

> **日期**：2026-05-01（v2 校正版）
> **session**：hermes-agent（runtime 實測產出 + A/B/C/D 4 trials）
> **配對**：integration-blocker-board.md（治理面）；本檔聚焦**運行面**
> **狀態**：v1 根因誤判 → v2 經實驗校正

## ⚠️ v1 → v2 重大校正（2026-05-01 第三輪 iteration）

**v1 結論被實驗推翻**。經 A/B/C/D 4 個 trials 證據：

| v1 假設 | 證據 | v2 結論 |
|---|---|---|
| 13K context 過大壓垮 7B | Trial C 12990 tokens 仍 ✅ | ❌ 否定 |
| qwen2.5:7b 能力不足 | Trial D OpenAI tools 全 ✅ | ❌ 否定 |
| 需縮 skill / 換 model / 啟 escalate | 實驗證明都不必要 | ❌ 過度設計 |

**v2 真因**：ck-* SKILL.md **沒寫 curl 範例教 model 用 terminal 呼叫**；CK 自定義的 `register_all(registry)` hermes 不認（grep 整 codebase 0 hits）。

**v2 真解**：每個 ck-* SKILL.md 加 5–10 行 curl pattern → 詳見 `docs/plans/skill-curl-pattern-patch.md`。

**勿動**：v1 推薦的「換 Groq primary」「啟 escalate」「skill lazy-load」**全部不必要**，是過度反應。Anthropic credit / 模型路線決策可解耦 P0。

## TL;DR（v2）

1. **Runtime 已 L2 全部署** — 6 個 ck-* skill 安裝、config 全 enabled、SOUL=meta、API:8642 ✅
2. **真實 P0**：SKILL.md 設計缺陷（沒教 model 怎麼呼叫）— **每 skill 30 min patch 即解**
3. **次因（非阻塞）**：SOUL 是 meta 觀察者人格 + 業務 bridge 同時掛，疊加抑制執行
4. **本週執行**：依 `skill-curl-pattern-patch.md` 對 5 個 ck-* skill 套 SKILL.md patch（業務 repo 各自 30 min）

## 現況快照（2026-05-01 測試）

| 項目 | 狀態 | 證據 |
|---|---|---|
| ck-hermes-gateway | ✅ Up 26h healthy | docker ps |
| ck-hermes-web | ✅ Up 26h healthy | docker ps |
| ck-ollama | ✅ qwen2.5:7b-ctx64k 主 / gemma4:e2b 備 | /api/tags |
| /v1/chat/completions | ✅ HTTP 200, 21–39s | curl 測試 |
| /v1/responses | ✅ HTTP 200, 24s | curl 測試 |
| /v1/models | ✅ 列 hermes-agent | curl 測試 |
| /health | ✅ {"status":"ok"} | curl 測試 |
| 6 ck-* skill 安裝 | ✅ /opt/data/skills/ck-*/ 全在 | docker exec ls |
| SOUL.md runtime | ✅ "Hermes Meta — 共同大腦" | docker exec head |
| Telegram bot | ⚠️ register fail (Frozen_method_invalid) | docker logs |
| **Tool-calling 觸發** | ❌ **不觸發** | function_call=None × 3 測試 |
| **繁中遵守** | ⚠️ **半破** | 多次回應簡體混雜 |
| **回應品質** | ❌ **崩壞** | "-basket" hallucination |

## 斷點根因分析

### 對照組

| 環境 | Prompt context | 回應 | 品質 | 時間 |
|---|---|---|---|---|
| Raw qwen2.5:7b 直打 ollama（4K context）| 4096 | 「我是一名中文語言助手。熱愛文字與知識分享。樂於助人...」 | ✅ 全繁體 / 流暢 | 3.5s |
| Hermes /v1/chat/completions | 13016 | 「为了查询中壢區... 我將通過 ck-missive-bridge 工具來執行此操作」 | ❌ 簡繁混雜 / 文字模擬 tool | 39s |
| Hermes /v1/responses | 13023 | 「-basket」（hallucination）| ❌ 完全崩壞 | 24s |

**結論**：問題不是 model 也不是 hermes，是**「7B model + 13K context」這個組合**。

### 13K context 從哪來

| 元件 | 估算 token |
|---|---|
| SOUL.md（meta.soul.md 完整版） | ~1500 |
| ck-missive-bridge SKILL.md（v2.0 完整） | ~2500 |
| ck-lvrland-bridge SKILL.md | ~1200 |
| ck-pilemgmt-bridge SKILL.md | ~1500 |
| ck-showcase-bridge SKILL.md | ~2000 |
| ck-observability-bridge SKILL.md | ~2000 |
| ck-adr-query SKILL.md | ~1000 |
| llm-wiki SKILL.md | ~800 |
| Hermes system boilerplate（toolset core/code）| ~500 |
| **合計** | **~13000** ✅ |

### 為什麼 7B model 撐不住

- 7B model 的 **effective instruction following** 在 ~4–8K 最佳
- > 10K 後注意力散漫、容易 hallucinate
- qwen2.5:7b-ctx64k 雖然標稱 64K，但 64K 是「能讀」≠「能 follow」
- Hermes 約定的 tool-calling syntax（`<tool_call>...</tool_call>` 或 XML schema）需要強 instruction-following 才會輸出
- 7B 在 13K 已下降到「自然語言 fallback」模式

## 三條優化路徑（⚠️ v2：A 仍可行但非 P0；B/C 不必要）

> v1 把 A/B/C 列為 P0 修復路徑，v2 校正：**P0 修復走 `skill-curl-pattern-patch.md`**，下方 A/B/C 只在「想優化」時才考慮。

### 路徑 A — Skill Lazy-Load（**v2 降為次優先**：縮 prompt 可加快回應，非必要）

**做法**：把 `config.yaml` 的 `skills.enabled` 從 6 個降到 **1 個 pilot**（建議 ck-missive-bridge 業務量最大）。

```yaml
skills:
  enabled:
    - ck-missive-bridge   # 主力 pilot
    # - ck-pilemgmt-bridge        # 暫停
    # - ck-observability-bridge   # 暫停
    # - ck-showcase-bridge        # 暫停
    # - ck-lvrland-bridge         # 暫停
    # - ck-adr-query              # 暫停
    # - llm-wiki                  # 暫停
```

**預期效果**：
- prompt token 13K → ~5–6K
- tool-calling 觸發率提升（7B 在 5–6K 通常 OK）
- 其他 domain query 不能 route（用戶要切 profile 才行）

**工時**：5 min config 改 + restart；1h 7 天觀察

**何時用**：當前可立即驗證模型能否在小 context 下正確 tool-call。

### 路徑 B — 換 Model（**MED 工時**）

選項：
1. **qwen2.5:14b**（Ollama 本地）— GPU VRAM 12G tight，可能 OOM
2. **qwen2.5-coder:7b**（Ollama）— tool-calling 訓練更強，繁中略弱
3. **Groq llama-3.1-8b-instant**（fallback 升 primary）— OpenAI tool-calling 訓練強，已是 fallback config
4. **Anthropic Sonnet 4.6**（escalate）— 最強，路線 B 路徑 6 已備 patch

**推薦**：先試 **Groq 升 primary**（路徑 C 的子集；本週 30 min 切換）

```yaml
model:
  provider: custom
  model: llama-3.1-8b-instant
  base_url: https://api.groq.com/openai/v1
  api_key_env: GROQ_API_KEY
  context_length: 128000

fallback_model:
  model: qwen2.5:7b-ctx64k
  provider: custom
  base_url: http://ck-ollama:11434/v1
  api_key_env: OLLAMA_API_KEY
  context_length: 65536
```

**預期**：tool-calling 觸發率 70–85%（覆盤 Phase 1 估）。

### 路徑 C — Profile 隔離 + Lazy Skill（**HIGH 工時，最終態**）

Master Plan v2 Phase 2 的目標：
- Hermes meta profile：只載 `llm-wiki`（觀察者，不業務）
- Missive profile：只載 `ck-missive-bridge`（按需切）
- LvrLand profile：只載 `ck-lvrland-bridge`（按需切）
- ...

**做法**：用 `~/.hermes/profiles/<name>/skills/` 隔離；用 `hermes profile switch <name>` 切換。

**預期**：每個 profile prompt token 5–7K，全部 tool-calling 正常。

**工時**：1 週（profile 機制實證未跑過）

## 推薦執行序

| 步驟 | 路徑 | 工時 | 預期解 |
|---|---|---|---|
| 1 | A（lazy load 6→1）| 5 min | 立刻驗證 7B model 在小 context 下 tool-calling 能力 |
| 2 | B-子集（Groq 升 primary）| 30 min | 即使 6 skill 全載也能正常 tool-call |
| 3 | C（profile 隔離）| 1 週 | 最終態，每 domain 一個獨立 agent |

**最大效益**：1 + 2 同 commit 可一次解決：「Groq primary + 只啟 1 skill」→ 即驗證 + 即恢復服務。

## 立即可動 SOP（步驟 1+2 合併）

```bash
# 1. 備份當前 config
docker exec ck-hermes-gateway sh -c 'cp /opt/data/config.yaml /opt/data/config.yaml.bak.$(date +%Y%m%d-%H%M%S)'

# 2. 在 host 端編輯 config（CK_AaaP runbook 為 source）
cd D:/CKProject/CK_AaaP/runbooks/hermes-stack
# 編輯 config.yaml.example：
#   - model 段：Groq 升 primary，qwen2.5 降 fallback
#   - skills.enabled：降到 1（ck-missive-bridge）

# 3. 套到 runtime
docker compose cp config.yaml.example hermes-gateway:/opt/data/config.yaml

# 4. restart（破 prompt cache）
docker compose restart hermes-gateway

# 5. 驗證
curl -s -m 60 -X POST http://localhost:8642/v1/responses \
  -H "Authorization: Bearer ck-hermes-local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","input":"請呼叫 missive_health 工具確認 backend 狀態","store":false}' | \
  python -c "import sys,json; d=json.load(sys.stdin); [print(o.get('type'),o.get('name','')) for o in d.get('output',[])]"

# 預期看到：
#   function_call missive_health
#   function_call_output
#   message
```

## Open WebUI 整合（用戶端）

未測但已知配置（per CK_AaaP runbook）：
- Open WebUI :3000（外部 docker-compose 啟動）
- Backend = `http://localhost:8642/v1`（Hermes API）
- API key = `ck-hermes-local-dev-key`

驗證步驟：
1. 開 http://localhost:3000
2. Settings → Connections → OpenAI API Connections
3. 確認 base URL 與 key
4. 對話列出 model = `hermes-agent`
5. 問題若觸發 tool-call，會看到 inline `hermes.tool.progress` UI

若 tool-call 失敗（同 API 直測）→ 同樣是 prompt context 問題。

## Telegram bot 失敗修復（次優先）

```
WARNING gateway.platforms.telegram: [Telegram] Could not register Telegram command menu: Frozen_method_invalid
```

可能原因：upstream telegram lib 與 frozen dataclass 不相容。**待 upstream sync 排程**（per `upstream-sync-cadence.md`）。

短期繞過：可在 config.yaml 把 `gateway.platforms.telegram.enabled: false`，避免 log spam。

## 監測腳本（每日 health）

放 `~/.hermes/cron/daily-health.sh`：

```bash
#!/usr/bin/env bash
# 每日 09:00 自動測 hermes 整合運用健康度
ENDPOINT="http://localhost:8642/v1/responses"
KEY="ck-hermes-local-dev-key"
RESULT=$(curl -s -m 60 -X POST "$ENDPOINT" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","input":"請呼叫 missive_health 確認狀態","store":false}')

if echo "$RESULT" | grep -q '"type": "function_call"'; then
    echo "✅ tool-calling 正常觸發"
else
    echo "❌ tool-calling 失效；prompt context 或 model 問題"
    echo "   action: 檢查 docs/plans/hermes-integration-playbook.md"
fi
```

## Cross-Reference

- `docs/plans/integration-blocker-board.md` — 治理面看板
- `docs/plans/hermes-model-baseline-route-b-2026-04-29.md` — 路線 B 評估
- `docs/plans/escalate-config-patch-2026-04-29.md` — Anthropic escalate infra patch
- `docs/plans/master-integration-plan-v2-2026-04-19.md` — Profile 隔離設計（路徑 C 細節）
- `D:/CKProject/CK_AaaP/runbooks/hermes-stack/config.yaml.example` — config source

## 變更歷史

- **2026-05-01** — 初版（hermes-agent runtime 實測 + 斷點診斷）
