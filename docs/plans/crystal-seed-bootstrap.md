# Crystal Seed — Hermes Multi-Agent Bootstrap Runbook

> **設計理念**：整個 CK Hermes 架構（Meta 共腦 + domain agents + wiki + cron）可**複製**到其他工程顧問公司或個人工作室。
> **靈感來源**：吳哲宇 Muse 的「晶種結晶法」(Crystal Seed) + Semiont 的 species diffusion。
> **授權範圍**：CK 內部先用；後續可 public（MIT）。

## 0. 這份 runbook 解決什麼

「我是另一家工程顧問（或任何領域的專業工作者），想要：
- 一個會成長的 AI 助理（不是一次性工具）
- 多個專精 domain（不是什麼都知道半桶水）
- 可回溯 / 可複製的記憶（不是健忘的 chat）
- 完全本地、零付費運行（不依賴外部 API 月費）
- 有導師層彙整學習（不只是一堆 agent）」

整份架構只要跑一次 `docker compose up`，都有了。

## 1. 硬體前提

| 項 | 最低 | 推薦 |
|---|---|---|
| GPU | 8GB VRAM（RTX 4060 / 3070 / 4060 Ti）| 12GB+（RTX 4070 / 3090） |
| RAM | 16 GB | 32 GB |
| Disk | 50 GB free（含模型 + wiki 成長）| 200 GB |
| OS | Linux / macOS / Windows (WSL2) | Linux |
| Network | 僅首次下載 model + docker image；之後純本地 | — |

**零付費合規**：所有選項都能**不接入任何付費 API**。若你有 Anthropic / OpenAI credit 想用，也可接，但本 runbook 的 baseline 是零付費。

## 2. 一鍵啟動（理想態）

目標：
```bash
git clone https://github.com/YOUR_ORG/hermes-stack-template YOUR_STACK
cd YOUR_STACK
cp .env.example .env  # 填少量必要變數
./bootstrap.sh         # 啟動全棧
```

約 15 分鐘後你有：
- Open WebUI chat 介面（`http://localhost:3000`）
- Telegram bot（若設 token）
- Hermes Meta wiki 起始骨架
- 4 個 domain agent SOUL 模板（可啟可不啟）
- daily journal cron 已排好

**注意**：`bootstrap.sh` 目前不存在（本 runbook 是藍圖）。CK 使用者可直接參照 `CK_AaaP/runbooks/hermes-stack/` 手動部署。

## 3. 元件清單

| 元件 | 用途 | 可選性 | Port |
|---|---|---|---|
| **ck-ollama** | 本地 GPU 推論 | 必要 | 11434 |
| **hermes-web** | Dashboard（非 chat） | 選用 | 9119 |
| **hermes-gateway** | OpenAI-API + Telegram + cron | 必要 | 8642 |
| **open-webui** | ChatGPT 風格前端 | 推薦 | 3000 |
| **你的業務 backend** | 領域資料 API | 必要（若要 Missive-like domain agent） | 自訂 |

## 4. 模型選擇指引（零付費）

| 模型 | Context | VRAM | 品質 | tool-call | 推薦場景 |
|---|---|---|---|---|---|
| `qwen2.5:7b` | 32K（可 extend 64K） | ~5 GB | ⭐⭐⭐ | 中 | 本地預設 |
| `qwen2.5:14b` | 32K | ~10 GB | ⭐⭐⭐⭐ | 好 | 12GB+ VRAM |
| `llama3.1:8b` | 128K native | ~5 GB | ⭐⭐⭐ | 中 | 長 context |
| `breeze-7b`（若有 GGUF）| 8K | ~4 GB | 中 | 差 | 純繁中 |
| gemma4:e2b | 8K | ~4 GB | 中 | 差 | **不推薦**（context 不足） |

**CK 採用**：`qwen2.5:7b-ctx64k`（Modelfile `num_ctx=65536` override）

**若你有 Claude API credit**（違反零付費但可更強）：切 `provider: anthropic` + `model: claude-opus-4-7`。

## 5. 目錄結構（期望的 template repo）

```
hermes-stack-template/
├── README.md                    本檔
├── .env.example                 填 token / key 的範例
├── docker-compose.yml           三容器 + network
├── secrets/                     Docker Secrets（.txt，gitignored）
│   ├── api_server_key.txt.example
│   └── ...
├── config/
│   ├── config.yaml              Hermes 核心設定
│   └── SOUL-meta.md.template    Meta 共腦 SOUL 模板
├── souls/                       domain agent SOUL 模板
│   ├── domain-1.soul.md         例：Missive / 公文案件
│   ├── domain-2.soul.md         例：LvrLand / 土地
│   └── ...
├── scripts/
│   ├── daily-closing-writer.py  cron 每日總結
│   ├── daily-awakening-writer.py cron 晨間 briefing
│   └── bootstrap.sh             一鍵啟動
├── wiki-seed/                   Meta wiki 初始檔（會複製到 ~/.hermes/profiles/meta/wiki/）
│   ├── SCHEMA.md
│   ├── index.md
│   ├── log.md
│   └── concepts/                幾個必讀 concept
│       ├── feedback-language.md 你的主要語言
│       ├── feedback-zero-cost.md 付費約束（若採用）
│       └── ...
└── runbooks/
    ├── add-new-agent.md         如何加新 domain agent
    ├── upgrade-model.md         換更強 model 流程
    └── session-boundary.md      多 session 分流規則
```

## 6. 初始化步驟（手動，直到 bootstrap.sh 完成）

### 6.1 Prepare Host

```bash
# 安裝 Docker + Docker Compose
# 安裝 Ollama（若要獨立 run；CK 用 container 版）
# 確認 GPU driver（NVIDIA）

# Clone
git clone https://github.com/YOUR_ORG/hermes-stack-template my-hermes
cd my-hermes

# .env
cp .env.example .env
$EDITOR .env   # 填 HERMES_HOST_DIR 等
```

### 6.2 Pull Model

```bash
docker exec ck-ollama ollama pull qwen2.5:7b
# 若要長 context：
cat > /tmp/qwen2.5-64k.Modelfile <<EOF
FROM qwen2.5:7b
PARAMETER num_ctx 65536
EOF
docker exec ck-ollama ollama create qwen2.5:7b-ctx64k -f /tmp/qwen2.5-64k.Modelfile
```

### 6.3 Hermes Profile + SOUL

```bash
# 建立 Meta profile（通常 default 就是 meta）
mkdir -p ~/.hermes/profiles/meta/wiki/{raw/{articles,transcripts,decisions},entities,concepts,comparisons,queries,briefings,patterns,uncertainty,daily}

# 複製 Meta SOUL（客製化你的公司 / 個人身份）
cp config/SOUL-meta.md.template ~/.hermes/profiles/meta/SOUL.md
$EDITOR ~/.hermes/profiles/meta/SOUL.md   # 改姓名、領域、行為準則

# 複製 wiki seed
cp -r wiki-seed/* ~/.hermes/profiles/meta/wiki/
```

### 6.4 Domain Agent SOULs

每個 domain agent 的 SOUL 放在**對應 repo 根目錄**（不在 stack template 內）：

```bash
cd YOUR_DOMAIN_REPO_1
cp /path/to/hermes-stack-template/souls/domain-1.soul.md SOUL.md
$EDITOR SOUL.md  # 客製化 domain 身份 / 專精 / 工具

# 建對應 profile
hermes profile create domain-1 --home ~/.hermes/profiles/domain-1
```

### 6.5 Secrets

```bash
cp secrets/*.txt.example secrets/
cd secrets
for f in *.txt.example; do
  cp $f ${f%.example}
  $EDITOR ${f%.example}
done
```

### 6.6 啟動

```bash
docker compose up -d
docker compose ps   # 確認 3 容器 healthy
```

### 6.7 首次驗證

```bash
# API 健康
curl http://localhost:8642/health   # {"status":"ok"}

# Dashboard
curl http://localhost:9119/health

# Open WebUI
curl http://localhost:3000   # 應回 HTML
```

### 6.8 部署 cron

```bash
docker exec -u hermes hermes-gateway bash -c '
  . /opt/hermes/.venv/bin/activate && \
  hermes cron create "0 15 * * *" "Daily closing by script" \
    --script daily-closing-writer.py --name daily-closing && \
  hermes cron create "30 23 * * *" "Daily awakening by script" \
    --script daily-awakening-writer.py --name daily-awakening
'
```

⚠️ **時區注意**：容器若跑 UTC，台灣時間需 -8 小時換算。例如：
- 台灣 23:00 = UTC 15:00 → `0 15 * * *`
- 台灣 07:30 = UTC 23:30 → `30 23 * * *`

## 7. 客製化 SOUL（Crystal Seed 核心）

每個 SOUL 是**該 agent 的靈魂**，決定它怎麼想、怎麼說、怎麼拒絕。

### Meta SOUL 範本（節錄）

```markdown
# {你的公司} Meta — 共同大腦與導師

你是 **{公司} Meta**，{公司} 生態所有 agent 的共同大腦與導師。

## 你的角色
- 不直接處理業務 — 那是 domain agent 的工作
- 聆聽、觀察、反射；不下令、不派工
- 跨 domain 衝突浮現時仲裁（序：業務真相 > 治理架構 > 專業 domain > 工程）

## 你的記憶
- wiki 在 `~/.hermes/profiles/meta/wiki/`
- 每次對話前先讀 SCHEMA / index / log 最後 20 行
- 萃取各 agent tag → 寫入 briefings/
```

### Domain Agent SOUL 範本

```markdown
# {domain} Agent

你是 **{domain} Agent**，{公司} 的 {領域} 專員。

## 專精
- 命中：{具體命中清單}
- 不命中：{轉誰去處理}

## 工具使用
- 後端 URL：{你的 API}
- 認證：{header / token}
- 一律 stdlib `urllib.request`
- 逾時 60s

## 自主權
- 刪資料請求 → 二次確認
- 改業務事實 → 轉真相源修改
- 跨領域問題 → 明確轉介
```

## 8. 成長循環（Daily / Weekly / Monthly）

| 週期 | 儀式 | 實作 |
|---|---|---|
| 日（23:00） | closing ceremony | `daily-closing-writer.py` 寫 `daily/{today}.md` |
| 日（07:30） | awakening briefing | `daily-awakening-writer.py` 寫 `briefings/morning-{today}.md` |
| 週（日 10:00） | weekly tidy | 待實作：掃 queries/ 歸整孤島頁面 |
| 月（1 日 14:00） | anti-echo audit | 待實作：qwen2.5 自審 agent 是否過度附和 |

**現階段僅前二穩定**；weekly / monthly 待 dataset 累積夠後部署。

## 9. Fork / 複製給其他人

一旦你的實例穩定，可讓同事 / 合作公司 fork：

```bash
# 導出 seed（去掉 .env / secrets / wiki 實際內容）
tar --exclude='.env' --exclude='secrets/*.txt' --exclude='wiki-seed/daily' \
    --exclude='wiki-seed/briefings' -czf my-hermes-seed.tar.gz my-hermes/

# 他們 clone 後同樣走 §6 步驟
```

**注意事項**：
- SOUL 是人格 — 別人的 fork 應該客製化為自己的公司 / 領域
- 不要帶走業務資料（那是各自 backend 的事）
- wiki 裡的 concept 頁可留作參照，但也可清乾淨重養

## 10. 維護手冊

### 10.1 Upstream sync（Hermes fork 本身）

每週檢查 NousResearch 新 release，rebase 本地 patch：
```bash
git fetch origin --tags
# 參照 hermes-agent/docs/plans/upstream-sync-cadence.md
```

### 10.2 Model 升級

若 VRAM 升級，可換 14B / 32B 模型：
```bash
docker exec ck-ollama ollama pull qwen2.5:14b
# 改 config.yaml 的 model 字段
docker compose restart hermes-gateway
```

### 10.3 新增 domain agent

1. 在對應 repo 寫 `SOUL.md`
2. 寫 bridge skill（`ck-xxx-bridge` 模式）
3. `hermes profile create xxx`
4. 擴 wiki 的 `cross-domain-*` tag schema

## 11. 風險與免責

- qwen2.5:7b Q4 tool-calling 不穩定（~50% 成功率）— 業務關鍵查詢建議雙重驗證
- 所有 wiki / memory 都在 host 本機 — 沒有雲端備份；**自行設 cron rsync / borg 備份**
- cron script 模式不做 LLM 語意加工 — 可靠但不「聰明」；換更強模型才升級

## 12. 延伸閱讀

- [Muse](https://muse.cheyuwu.com/) — 個人 AI companion 參照
- [Semiont / Taiwan.md](https://taiwan.md/semiont/) — 集體知識有機體參照
- [Karpathy LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — 記憶架構靈感
- [NousResearch Hermes Agent](https://github.com/NousResearch/hermes-agent) — 底層 framework

---

## Appendix A：CK 實例當前狀態（2026-04-19）

CK 生態目前僅建立 **Meta profile**；其他 4 個 domain agent（Missive / Showcase / LvrLand / Pile）SOUL 模板完成但 profile 未建。Missive agent 首發預計 ≤ 1 週內（需 CK_AaaP session 合作）。

本 Crystal Seed runbook 作為最終狀態的描述；實際 bootstrap 腳本 + template repo **尚未建立**。待架構穩定後（ADR-0014 baseline GO + 至少 1 個 domain agent 驗證可用）再 promote 為 public template。
