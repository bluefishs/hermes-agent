# CK_AaaP / hermes-stack 部署工單 — 深化交流三件（R1 繁簡 + tick sidecar + 權限持久化）

> 日期：2026-06-16 · CK_Hermes session 產出規格 · **apply 落 CK_AaaP / hermes-stack session**
> 來源：[`2026-06-15-meta-chat-restore.md`](2026-06-15-meta-chat-restore.md)、[`meta-memory-engine/README.md`](meta-memory-engine/README.md)
> 政策：[[feedback_integration_over_scope]]、[[feedback_pre_demo_functional_verification]]（每件附 functional DoD）、Session 分流（CONVENTIONS §7）

> 前置確認（2026-06-16 live）：51 容器 healthy、hermes 核心 v2026.5.22 無漂移；chat 機制 /v1 meta 200；**UI 端到端通**（Open WebUI :3010 → `hermes-gateway:8642/v1` → meta，models+chat 均 200、認證走 secret）；R2 記憶引擎昨晚自主 fire（daily-closing ok）、Windows 任務每 5min 正常。

---

## DA-1 · P1 · R1 繁簡後處理上線（解簡體洩漏）

> ⚡ **2026-06-16 已 runtime 啟用（過渡）**：直接在運行中 gateway 注入 R1（`uv pip install opencc==1.3.1` 進 venv + 注入 `gateway/zh_convert.py`〔runtime 版預設 s2twp〕+ api_server.py 套 3 處編輯 + `docker restart`）→ `is_enabled:True`、`/v1` 回應**全繁中零簡體**實證（「聊天记录/检索/通过」→「對話記錄/檢索/透過」）。備份 `api_server.py.bak.20260616-pre-r1`。**持久化邊界**：runtime patch 存於容器 writable layer，**存活 `docker restart`／機器重啟（unless-stopped）**，但 **`compose up --force-recreate`／image pull 會丟失** → 本 DA-1（image rebuild）使其永久化+版控。

### 現況（程式碼）
程式碼已就緒於 CK_Hermes（commit `22586ef0a`）：`gateway/zh_convert.py` + `api_server.py` 接入 + `pyproject.toml` `zh` extra + tests 11/11。**預設關閉、部署解耦**（未裝 opencc 或未設 env 時 no-op）。

### 步驟
1. image build 納入 `.[zh]`（裝 `opencc>=1.1,<2`）——hermes-stack Dockerfile 的 `pip install` 加 `zh` extra，或 requirements 追加 `opencc`。
2. gateway env 設 `HERMES_ZH_CONVERT=s2twp`（hermes-stack `.env` + compose）。
3. rebuild image（含 CK fork 最新 main：R1 三檔）+ `docker compose up -d hermes-gateway`。
4. **回滾**：移除 env（即 no-op）或回前一 image tag。

### DoD（functional）
- `docker exec ck-hermes-gateway python3 -c "from gateway.zh_convert import is_enabled; print(is_enabled())"` → `True`。
- `/v1 model=meta` 問一句 → 回應**全繁中、無簡體**（可故意誘導：問「用簡體也沒關係」仍須回繁中）。
- baseline dispatch（query.py）不受影響。

---

## DA-2 · P1 · R2 tick sidecar（取代本機 Windows 過渡任務）

### 現況
R2 記憶引擎已復原並**本機 Windows 工作排程器 `CK-Hermes-Cron-Tick`（每 5min）驅動、已 end-to-end 驗證自主 fire**。但 Windows 任務僅本機、不可攜、未版控於 stack。gateway 內建排程器在 Docker 不 tick（已實測）。

### 步驟
1. hermes-stack compose 加一個極小 sidecar（例 `hermes-cron-tick`），每 60s 跑：
   `docker exec`-equivalent 或同網路內 `hermes cron tick`（HERMES_HOME=/opt/data、以 hermes uid）。
   - 最簡：busybox/alpine + `while true; do <call gateway hermes cron tick>; sleep 60; done`；或共用 gateway image 跑 `hermes cron tick` loop。
   - file-lock 保 at-most-once → 與任何其他 ticker 並存安全。
2. 確認 sidecar 跑後，**移除本機 Windows 任務**：`Unregister-ScheduledTask -TaskName CK-Hermes-Cron-Tick -Confirm:$false`（雙驅動雖安全但無必要）。

### DoD
- 停掉 Windows 任務後，故意 `cron run daily-closing-v5` → 60s 內 sidecar 自動 tick 使其 `last_status: ok`。
- 跨 `docker compose down/up` 後 sidecar 自動回、cron 續跑。

---

## DA-3 · P0 · meta profile 權限持久化（防 chat 入口再 500）

### 現況
6/15 發現 meta profile 目錄被翻 `root:root 700` → gateway 鎖死 → `/v1` 500。已 `chown hermes` 修復（live）。但 entrypoint「top-level 已 hermes 就跳過遞迴」最佳化，使重啟後若 host 再翻 root 不會自癒。

### 步驟
- hermes-stack entrypoint（或 compose 啟動 hook）啟動時對 **所有 `/opt/data/profiles/*`** 強制 `chown hermes:hermes`（不依賴 top-level 判斷）。
- 或 upstream entrypoint patch：`needs_chown` 邏輯改為「檢查 profiles/* 子目錄擁有者」。

### DoD
- 模擬 `chown root:root /opt/data/profiles/meta` → 重啟 gateway → 啟動後自動回 hermes 擁有、`/v1 model=meta` HTTP 200。

---

## 優先序

```
P0  DA-3 權限持久化   ← 防 chat 入口再死（最高，影響可用性）
P1  DA-1 R1 繁簡上線  ← 深化交流體感最大、CP 最高
P1  DA-2 tick sidecar ← R2 跨機可攜、移除本機過渡任務
```

> 另：WO-2（CK_Missive 開 `/api/ai/memory/digest`，S3 唯一外部阻斷）與 WO-3（WS-D 業務分流）維持原工單，與本工單互補（事實歸後端、對話歸 meta）。
