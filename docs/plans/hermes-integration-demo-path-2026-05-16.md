# Hermes Integration Demo Path — 30-min From Zero to L3

> 目標：讓 Hermes 投入的工程資產（4 bridge / 11 native tools / 145 tests / gateway middleware / hermes-stack）第一次在 user-facing 上呈現「整合效應」。
> 範圍：Phase 1 走 ck-missive-bridge 端到端（其他 3 bridge 列 Phase 2）。
> 接手 session：**`D:\CKProject\CK_AaaP`**（hermes-stack 主場）+ 部分 `D:\CKProject\CK_Missive`。
> 上游：[[architecture-retro-action-items-2026-05-15]] + [[workflow-c3-phase1-bridges-complete-2026-05-16]]

---

## 為什麼需要這份 cookbook

hermes-agent fork 已累積：
- 4 bridge × 11 native tools 在 registry 自動註冊
- 145 unit + e2e tests baseline
- gateway metrics / rate_limit / secrets middleware
- hermes-stack 三容器 docker-compose
- scripts/verify-bridges.py ops helper

**但 user 看不到任何效應**，因為四個「最後一哩」配置全在跨 session：
1. `~/.hermes/profiles/meta/SOUL.md` 未套 template
2. `hermes-stack/.env` 未注入 4 個 `*_BASE_URL`
3. 各 bridge `SKILL.md` frontmatter 未加 `toolsets:`
4. LLM 推理層（Anthropic credit 或 Ollama fallback）未確認

本 cookbook 把這些步驟串成 30 分鐘可執行流程，**走完一次就能在瀏覽器看到「LLM 觸發 missive_health tool → 真打 CK_Missive backend → 結果文字回答」**。

---

## Phase 1: ck-missive-bridge End-to-End Demo（30 分鐘）

### 前置檢查（2 分鐘）

```bash
# 1. CK_Missive backend 已 running（host 上 :8001 或 PM2）
curl -sS http://localhost:8001/health
# 預期：{"status":"ok","version":"5.5.8",...}

# 2. hermes-agent fork 已 push 到 fork/main（本 session 已完成）
cd D:/CKProject/CK_Hermes
git log --oneline -1
# 預期：54a97ad9c Merge origin/main (upstream sync 2026-05-16, ...)

# 3. CK_AaaP hermes-stack 配置在位
ls D:/CKProject/CK_AaaP/runbooks/hermes-stack/.env
# 預期：File exists
```

失敗應對：
- Missive 沒起 → `pm2 list` 確認 ck-backend，或 `BACKEND_PORT=8001 pm2 start ck-backend`
- hermes-agent 不在 push HEAD → `git pull fork main`

---

### Step 1: 注入 4 base url 到 hermes-stack/.env（5 分鐘）

> session：`D:\CKProject\CK_AaaP`

打開 `runbooks/hermes-stack/.env`，在 `# ADR-0028` 區塊**之前**加入：

```bash
# ─── ADR-0020 Phase 1 native tool bridges ─────────────────────
# host.docker.internal 在 Windows / macOS Docker Desktop 可用；
# Linux 需改用 host 內網 IP 或 host-gateway extra_hosts。
MISSIVE_BASE_URL=http://host.docker.internal:8001
# 之後 3 個 bridge 上線時補（Phase 2）：
# OBSERVABILITY_PROMETHEUS_URL=http://host.docker.internal:19090
# OBSERVABILITY_LOKI_URL=http://host.docker.internal:13100
# OBSERVABILITY_GRAFANA_URL=http://host.docker.internal:13000
# OBSERVABILITY_ALERTMANAGER_URL=http://host.docker.internal:19093
# SHOWCASE_BASE_URL=http://host.docker.internal:5200
# PILE_BASE_URL=http://host.docker.internal:8004
```

verify：

```bash
grep "MISSIVE_BASE_URL" D:/CKProject/CK_AaaP/runbooks/hermes-stack/.env
# 預期：MISSIVE_BASE_URL=http://host.docker.internal:8001
```

---

### Step 2: 套 meta SOUL template（5 分鐘）

> session：`D:\CKProject\CK_AaaP`（或本機 shell 直接寫 `~/.hermes/profiles/meta/`）

```bash
# 1. 確認 hermes meta profile 目錄存在
ls ~/.hermes/profiles/meta/
# 若不存在：mkdir -p ~/.hermes/profiles/meta/

# 2. 複製 meta SOUL template
cp D:/CKProject/CK_Hermes/docs/plans/soul-templates/meta.soul.md \
   ~/.hermes/profiles/meta/SOUL.md

# 3. 確認被讀到（hermes-stack 啟動時會 mount ~/.hermes）
head -10 ~/.hermes/profiles/meta/SOUL.md
```

verify：SOUL.md 第一行應該是 `# CK 助理（meta）` 或類似身份宣告，繁中。

failure mode：若已有舊 `SOUL.md`，先 backup 再覆蓋（`cp SOUL.md SOUL.md.bak-2026-05-16`）。

---

### Step 3: ck-missive-bridge SKILL.md frontmatter 補 `toolsets`（5 分鐘）

> session：`D:\CKProject\CK_Missive`

打開 `docs/hermes-skills/ck-missive-bridge/SKILL.md`，frontmatter 區（檔頭 `---` 之間）加入 `toolsets:`：

```yaml
---
name: ck-missive-bridge
version: 2.0.0
description: CK_Missive 後端全功能橋接 — ...（保持原樣）
author: CK_Missive Team
license: MIT
toolsets: [missive]                    # ← 新增此行
metadata:
  hermes:
    tags: [CK, Missive, ...]
    homepage: https://missive.cksurvey.tw
prerequisites:
  env_vars: [MISSIVE_API_TOKEN, MISSIVE_BASE_URL]
---
```

接著裁掉 skill body 中「描述 LLM 如何構造 URL」的舊段落（v2.0 prompt-template 時代產物）；改為簡單一句：

> 本 skill 透過 `missive_health` 與 `missive_get_document` 兩個 native tool 操作 CK_Missive backend。LLM 觸發即可，不需自行構造 URL。

commit：

```bash
cd D:/CKProject/CK_Missive
git add docs/hermes-skills/ck-missive-bridge/SKILL.md
git commit -m "feat(skill): wire ck-missive-bridge to native toolset [missive]"
git push
```

---

### Step 4: hermes-stack 啟動（5 分鐘）

> session：`D:\CKProject\CK_AaaP`

```bash
cd D:/CKProject/CK_AaaP/runbooks/hermes-stack
docker compose up -d --build
# 等 30-60s 三容器 healthy
docker compose ps
```

verify：應該看到三個容器 `Up`：
- `hermes-web` :9119
- `hermes-gateway` :8642
- `open-webui` :3000

failure mode：
- build 失敗 → `docker compose logs --tail 50 <service>`
- container 不健康 → 多半是 .env 缺值或 mount 路徑錯
- port 被占 → `netstat -ano | findstr ":9119"` 找占用 process

---

### Step 5: bridge 可達性驗證（2 分鐘）

```bash
# Host 端跑（不需進 container）
cd D:/CKProject/CK_Hermes
$env:MISSIVE_BASE_URL = "http://localhost:8001"
python scripts/verify-bridges.py --bridge missive
```

預期輸出：

```
  [OK  ] missive  missive_health  200 http://localhost:8001/health
  Summary: 1 OK | 0 FAIL | 0 SKIP
```

container 內也要可達，docker exec 進去：

```bash
docker exec -it hermes-gateway sh -c 'python /opt/hermes/scripts/verify-bridges.py --bridge missive'
```

failure mode：container 內 `[FAIL]` 但 host 端 OK → 9 成是 `host.docker.internal` 在 Linux 沒對應；改 `extra_hosts: ["host.docker.internal:host-gateway"]` 加進 docker-compose.yml。

---

### Step 6: First user-facing demo（5 分鐘）

打開瀏覽器：`http://localhost:9119`

對話框輸入：

> 幫我看 Missive 還好嗎

預期：

1. LLM 認識 `missive_health` tool（因為 SKILL.md `toolsets: [missive]` 已啟用）
2. LLM 回應 tool_call → registry 觸發 `_handle_health` → aiohttp 真打 `http://host.docker.internal:8001/health`
3. 結果文字回 user：「CK_Missive 健康。版本 5.5.8，PostgreSQL 連線正常，...」（繁中，因 meta SOUL 規範）

**這就是整合效應的第一次 user-facing 呈現**。

進階 demo prompts（解鎖完整 11 tools 後可用，Phase 2）：
- 「文件 doc-xxx 內容是什麼？」 → `missive_get_document`
- 「現在 hermes-gateway error rate？」 → `prometheus_query`
- 「最近 1 小時 missive container 有 ERROR log 嗎？」 → `loki_query_range`
- 「列受管專案」 → `showcase_managed_projects`
- 「Celery 佇列狀態？」 → `pile_celery_status`

---

## Phase 2: 啟用其他 3 個 bridge（每個 1d，可任意順序）

各 bridge 對應的 SKILL.md 目前還是 stub（在 hermes-agent/docs/plans/）。

採納步驟（以 showcase 為例，其他類推）：

```bash
# CK_Showcase session
cd D:/CKProject/CK_Showcase
mkdir -p docs/hermes-skills/ck-showcase-bridge

# 寫 SKILL.md（複製 missive 範式）
cat > docs/hermes-skills/ck-showcase-bridge/SKILL.md <<'EOF'
---
name: ck-showcase-bridge
version: 1.0.0
description: CK_Showcase 治理 API 橋接 — 受管專案清單 / 治理健康度 / ADR 跨 repo 地圖
toolsets: [showcase]
prerequisites:
  env_vars: [SHOWCASE_BASE_URL]
---

# CK Showcase Bridge

本 skill 透過 `showcase_health` / `showcase_managed_projects` /
`showcase_governance_health` 三個 native tool 操作 CK_Showcase API。
LLM 觸發即可，不需自行構造 URL。
EOF

git add docs/hermes-skills/ck-showcase-bridge/SKILL.md
git commit -m "feat(skill): wire ck-showcase-bridge to native toolset [showcase]"
git push
```

同時在 `hermes-stack/.env` 解 comment 對應 base url。

各 bridge 對應端口 / hostname：

| bridge | env | 預設 port（host 內網） | 預設 path |
|---|---|---|---|
| missive | MISSIVE_BASE_URL | 8001 | /health, /api/v1/documents/{id} |
| showcase | SHOWCASE_BASE_URL | 5200 | /api/health, /api/overview/projects, ... |
| pilemgmt | PILE_BASE_URL | 8004 | /api/health, /api/celery/status |
| observability | 4 × OBSERVABILITY_*_URL | 19090 / 13100 / 13000 / 19093 | per-backend |

---

## Phase 3: 強化（按需）

| 任務 | 觸發條件 |
|---|---|
| Anthropic credit 充值 | hermes-web 對話品質不夠（gemma 本地推理可能對 tool_call schema 解讀粗糙） |
| Ollama gemma+nomic 微調 | 想完全零付費，可接受工具呼叫偶爾 hallucinate |
| MISSIVE_API_TOKEN 注入 | Missive 公網 `missive.cksurvey.tw` 啟用後（auth required） |
| Telegram bot 接通 | 希望從手機 chat 也能觸發 tool |
| Prometheus scrape hermes-gateway | QW-1 — 把 hermes 本身指標納入觀測棧 |
| Grafana dashboard 「Hermes tool usage」 | 觀測哪些 tool 被頻繁觸發、failure rate |

---

## Failure Mode Quick Reference

| 症狀 | 通常原因 | 處理 |
|---|---|---|
| `verify-bridges.py` host 端 OK / container 端 FAIL | `host.docker.internal` 在 Linux 不可用 | docker-compose 加 `extra_hosts: [host.docker.internal:host-gateway]` |
| LLM 不觸發 tool，自己編 URL | SKILL.md frontmatter 沒 `toolsets:` 或 hermes-web 啟動前 env 未注入 | 先確認 `docker exec hermes-gateway env \| grep MISSIVE_BASE_URL`；再重啟 stack |
| `[FAIL] 401` | `MISSIVE_API_TOKEN` 未設或過期 | 從 Missive token rotation SOP 取新 token，加進 .env |
| `[FAIL] timeout` | Missive backend 沒起 或 docker network 隔離 | `curl host.docker.internal:8001/health` 直接 probe |
| LLM 回應全簡體 | meta SOUL 沒套 | `head -10 ~/.hermes/profiles/meta/SOUL.md` 確認 |
| hermes-gateway container exit | .env 缺 `HERMES_HOST_DIR` 或 mount 路徑錯 | `docker compose logs hermes-gateway --tail 30` |

---

## 預期效益（Phase 1 完成後）

- ✅ 第一次 user-facing 「Hermes 真的幫我做了事」demo 可開
- ✅ ADR-0020 Phase 1 「Hermes 為人機介面」價值論證有實證
- ✅ hermes-agent 8 個月工程投入第一次落入 user value 鏈路
- ✅ 其他 3 個 bridge 與 demo prompt 可由此 baseline 橫向擴展
- ✅ 後續 ADR-0020 Phase 2 (Showcase 遷入 AaaP) / Phase 3 (DigitalTunnel 遷入) 有可演示前提

---

## 反思

本 cookbook 之所以可寫，是因為 hermes-agent session（2026-05-16）已把 code 推到位：

1. 4 bridge native tool 註冊範式統一
2. `scripts/verify-bridges.py` 純 stdlib 不依賴 hermes runtime
3. e2e test 證明 aiohttp socket 鏈路通
4. 145 tests baseline 給未來 sync regression 防線

接下來真正的瓶頸**完全是配置**，不是工程。30 分鐘走完就能跨越「整合效應呈現」這條線。

> 跨 session 操作員：照表操課即可。遇問題回查本檔 Failure Mode Quick Reference 或 [[workflow-c3-phase1-bridges-complete-2026-05-16]]。
