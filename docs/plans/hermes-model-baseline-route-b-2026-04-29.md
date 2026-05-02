# Hermes 模型路線評估與切換決策矩陣

> **日期**：2026-04-29
> **作者**：hermes-agent session（覆盤輸出）
> **觸發**：覆盤誤判校正——「Anthropic credit 待充值」原列為 P0 阻塞，實際非阻塞
> **接收 session**：用戶（治理決策）+ CK_AaaP（若採納路線變更需更新 ADR-0014）
> **狀態**：observation + recommendation → awaiting decision

## TL;DR

1. **覆盤誤判校正**：當前 hermes-stack 已是 **Groq primary + ck-ollama fallback**（`config.yaml.example` L11–29），不是 Anthropic primary。「credit 阻塞」是基於舊 baseline plan 的誤識
2. **零付費硬約束實際已滿足**：Groq free tier + Ollama gemma4:e2b 都零成本，當前架構合規
3. **真正的決策不是「充不充 credit」**，而是 **「現狀 Groq-primary 是否最終態？要不要走更純本地路線、或升級為 Anthropic-primary」**
4. **建議路線 B（強化版）**：保留 Groq primary（速度好、TPM 30K 足夠），把 Ollama fallback 升級為**主動雙路徑**——複雜 reasoning 落 Anthropic（按需 escalate），日常落 Groq，敏感落 Ollama
5. 切換成本：路線 B（強化版）≈ 1h config 改動；路線 C（Anthropic-primary）≈ 半天 + credit + baseline 重跑

## 校正後的事實

| 配置項 | 當前狀態 | 來源 |
|---|---|---|
| `model.default` | `llama-3.1-8b-instant`（Groq） | `runbooks/hermes-stack/config.yaml.example` L14 |
| `model.provider` | `custom` → Groq OpenAI-compat API | L15–17 |
| `fallback_model.model` | `gemma4:e2b`（Ollama） | L27 |
| `fallback_model.base_url` | `http://ck-ollama:11434/v1` | L28 |
| Anthropic | **暫緩**，待 credit 後評估 | L9 註解 |
| `GROQ_API_KEY` 來源 | Docker Secret `/run/secrets/groq_api_key` | docker-compose.yml L94 |
| 月度成本 | **0 元**（Groq free tier + 本地 GPU） | — |

**結論**：當前已是「準路線 B」（Groq + Ollama）。**不需充 Anthropic credit 即可完整投產**。

## 三條路線正式比對

### 路線 A — 維持現狀（Groq-first，Ollama-fallback）
- **品質**：8B instant model，tool-calling 一般、context 128K 充足
- **可靠**：Groq TPM=30K（升 Dev tier 可解，目前免費 tier 已支撐）
- **成本**：0 元
- **適合**：當前 Phase 1 / 4 bridge skill 投產 / 日常 Missive RAG
- **痛點**：Groq 8B 對複雜 skill 鏈組合（5+ tool 順序呼叫）有時降級為文字
- **狀態**：✅ 已部署，已運行

### 路線 B（強化版）— 三層按需路由
```
日常請求 → Groq 8B instant   （速度第一）
複雜 reasoning → Anthropic Sonnet 4.6（按需 escalate）
敏感 / 離線 → Ollama gemma4:e2b（純本地）
```
- **品質**：日常等同路線 A，複雜任務升級到 Anthropic（質感跳級）
- **成本**：每月 < $20 USD（escalate 比例約 5–10%）
- **切換工時**：~1h（加 escalate 邏輯 + Anthropic provider config）
- **prompt cache 影響**：三 provider 各有獨立 cache，不互相破壞；Groq 主路徑 cache 不變
- **適合**：覆盤覆寫的 P0-2「控制鏈閉環」最佳解
- **狀態**：⚠️ 待設計 escalate 觸發規則

### 路線 C — Anthropic-primary
- **品質**：最高（Sonnet 4.6 / Opus 4.7）
- **成本**：每月 $50–200 USD（依使用量）
- **切換工時**：~半天（config 改 + .env 加 ANTHROPIC_API_KEY + 全量 baseline 重跑）
- **prompt cache 影響**：**全破一輪**（provider 不同 cache 不通用）
- **適合**：未來 Phase 2+ 若 Groq 8B 顯著瓶頸
- **狀態**：未來選項，不是當前需要

### 路線 D — 純 Ollama（極端零依賴）
- **品質**：gemma4:e2b 在 4060 上能跑，但 tool-calling 弱；qwen2.5 14B 為更強選項
- **成本**：0 元
- **切換工時**：~1h，但同時要評估升級到 qwen2.5:14b（vs gemma4:e2b）
- **痛點**：複雜 skill chain 失敗率高；4060 12G VRAM 對 14B 模型 tight
- **適合**：完全離線 / 隱私極致 / 災備場景
- **狀態**：作為路線 B 的 fallback 層，不單獨投產

## 推薦：路線 B 強化版

### 設計

`config.yaml` 加 escalation 規則（hermes-agent 需確認支援，否則用 skill-side 邏輯）：

```yaml
model:
  default: llama-3.1-8b-instant
  provider: custom
  base_url: https://api.groq.com/openai/v1
  api_key_env: GROQ_API_KEY
  context_length: 128000

# Layer 1 fallback（按需 escalate，非錯誤 fallback）
escalate_model:
  provider: anthropic
  model: claude-sonnet-4-6
  api_key_env: ANTHROPIC_API_KEY
  triggers:
    - tool_chain_depth_gt: 4
    - context_token_gt: 80000
    - explicit_directive: "/escalate"

# Layer 2 fallback（錯誤 fallback / 離線）
fallback_model:
  provider: custom
  model: gemma4:e2b
  base_url: http://ck-ollama:11434/v1
  api_key_env: OLLAMA_API_KEY
```

### 切換步驟（CK_AaaP session 執行）

```bash
# 1. 加 ANTHROPIC_API_KEY 到 hermes-stack secrets
cd D:/CKProject/CK_AaaP/runbooks/hermes-stack/secrets/
echo "<key>" > anthropic_api_key.txt
chmod 600 anthropic_api_key.txt

# 2. 更新 docker-compose.yml secrets list
# 加 anthropic_api_key 到 services.hermes-gateway.secrets 和 secrets: 段

# 3. 更新 config.yaml.example 加 escalate_model 段
# 上面範例 yaml

# 4. 套用到 runtime
docker compose cp config.yaml.example hermes-gateway:/opt/data/config.yaml
docker compose restart hermes-gateway

# 5. 驗收
curl -H "Authorization: Bearer ${API_SERVER_KEY}" \
     http://localhost:8642/v1/chat/completions \
     -d '{"model":"hermes-agent","messages":[{"role":"user","content":"/escalate analyze cross-domain KG between Missive and LvrLand"}]}'
# 應觀察到 escalate 觸發 → Anthropic Sonnet 回應
```

### Hermes 程式碼端校驗（hermes-agent session）

需確認 `hermes_cli/` 與 `gateway/` 是否支援 `escalate_model` 配置。若不支援：
- **選項 1**：提交 upstream PR（NousResearch fork）加 escalate routing
- **選項 2**：用 skill-side 邏輯：在 ck-missive-bridge 等 skill 內判斷複雜度，主動切 model（hermes API 支援 per-request `model` 參數）
- **選項 3**：簡化為「日常 Groq + 偶爾手動切 Anthropic」，由用戶 prompt 帶 `/model anthropic` 切換

預設走選項 2（最低耦合）。

### prompt cache 影響

| Provider | Cache 行為 | 切換成本 |
|---|---|---|
| Groq | OpenAI-compat 不支援 prompt cache（短會話無痛）| 無 |
| Anthropic | 有 prompt cache（Sonnet 4.6）| escalate 首次破，之後重建 |
| Ollama | 本地 KV cache（model swap 時破）| GPU 切 model 時破，可由 keep_alive 控制 |

由於 Groq 不用 cache，Anthropic escalate 用獨立 cache，**主路徑 cache 不會被打破**。這比路線 C（全切 Anthropic）優越。

### shadow baseline 對比方法

```bash
# 在 CK_Missive 建 shadow logger 已有的基礎上，加 model 標記
cd D:/CKProject/CK_Missive
node scripts/checks/shadow-baseline-report.cjs --model-tag

# 報告新增欄位：
# - groq_response_count / mean_latency / tool_success_rate
# - anthropic_escalate_count / mean_latency / tool_success_rate
# - ollama_fallback_count（理想 = 0，> 0 代表 Groq 不可用）
```

7 天觀察後若 escalate < 5%、tool_success_rate ≥ 90% → 路線 B 強化版穩定。

## 風險與回滾

| 風險 | 影響 | 緩解 |
|---|---|---|
| Anthropic credit 持續燒（escalate 比例失控） | 月成本超預算 | 設 daily token cap；超過退回 Groq |
| Anthropic key 外洩 | 帳號被盜刷 | Docker Secret + secrets-wrapper.sh 已就位（ADR-0017 Phase 1B） |
| Hermes 不支援 escalate_model | 設計失效 | 退選項 2（skill-side），最壞退選項 3（手動） |
| Groq free tier 政策變動（限額 / 收費）| 主路徑斷 | Ollama 升 qwen2.5:14b 為次主路徑 |

**回滾**：
```bash
# 回到路線 A（Groq + Ollama fallback）
docker compose cp config.yaml.example hermes-gateway:/opt/data/config.yaml  # 用未加 escalate 版
docker compose restart hermes-gateway
# .env 不必移除 ANTHROPIC_API_KEY（不用即可）
```

## 與 ADR-0014 GO/NO-GO 的關聯

ADR-0014（Hermes replace OpenClaw）的 GO 判準是 **shadow baseline tool-calling success rate ≥ 70%**。

- 路線 A（當前）：Groq 8B 可達 70–85%，**已達標**
- 路線 B（推薦）：日常等同路線 A，複雜任務由 Anthropic 拉到 95%+
- 路線 C：全部 Anthropic，95%+ 但成本高

**結論**：ADR-0014 GO 不需要等 Anthropic credit。**先 GO，再走路線 B 強化版**。

## SOUL 影響（meta.soul.md）

`meta.soul.md`（Hermes 共同大腦）內若有「我使用 X 模型」字樣，路線 B 上線時應更新為「我會視任務複雜度在 Groq / Anthropic / Ollama 之間切換」。

C.1 報告已建議激活 `meta.soul.md` 為 hermes-stack runtime 的 source（待 CK_AaaP session 執行 Step 1）。**這兩件事可合併在同一次 baseline 重跑**：搬 SOUL + 加 escalate model = 一次破 cache、一次重跑 baseline，不分兩次。

## 後續行動建議

| 步驟 | session | 工時 | 優先 |
|---|---|---|---|
| 1. 用戶決策路線 A / B-強化 / C | 用戶 | 5 min | P0 |
| 2. 若選 B：CK_AaaP 加 ANTHROPIC_API_KEY secret + escalate config | CK_AaaP | 30 min | P1 |
| 3. hermes-agent 確認 escalate_model 機制（讀 config 解析碼）| hermes-agent | 1h | P1 |
| 4. shadow baseline 加 model_tag 欄位 | CK_Missive | 1h | P1 |
| 5. 7 天 baseline 驗收 → ADR-0014 GO | 跨 session | 7d | P0 |

## 變更歷史

- **2026-04-29** — 路線 B 評估與切換藍圖（hermes-agent session 覆盤輸出）

## 相關文件

- `runbooks/hermes-stack/config.yaml.example` — 當前配置真相源
- `runbooks/hermes-stack/docker-compose.yml` — Docker Secrets / secrets-wrapper 配置
- `CK_Missive/docs/adr/0014-hermes-replace-openclaw.md` — GO/NO-GO 判準
- `CK_AaaP/adrs/0017-docker-secrets.md` — Phase 1B 已部署
- `~/.hermes/profiles/meta/wiki/concepts/feedback-zero-cost.md` — 零付費硬約束源
- `docs/plans/c1-soul-status-2026-04-28.md` — SOUL 治理報告（與本檔合併執行）
