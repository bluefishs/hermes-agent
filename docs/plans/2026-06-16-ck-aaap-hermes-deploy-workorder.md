# CK_AaaP / hermes-stack 部署工單 — 深化交流三件（R1 繁簡 + tick sidecar + 權限持久化）

> 日期：2026-06-16 · CK_Hermes session 產出規格 · **apply 落 CK_AaaP / hermes-stack session**
> 來源：[`2026-06-15-meta-chat-restore.md`](2026-06-15-meta-chat-restore.md)、[`meta-memory-engine/README.md`](meta-memory-engine/README.md)
> 政策：[[feedback_integration_over_scope]]、[[feedback_pre_demo_functional_verification]]（每件附 functional DoD）、Session 分流（CONVENTIONS §7）

> 前置確認（2026-06-16 live）：51 容器 healthy、hermes 核心 v2026.5.22 無漂移；chat 機制 /v1 meta 200；**UI 端到端通**（Open WebUI :3010 → `hermes-gateway:8642/v1` → meta，models+chat 均 200、認證走 secret）；R2 記憶引擎昨晚自主 fire（daily-closing ok）、Windows 任務每 5min 正常。
>
> 🔄 **2026-06-17 更新（本機重啟後複驗）**：本機 6/16 重啟揭露並修復 **DA-4 NVIDIA hook P0 故障**（wsl --shutdown）；health-smoke 哨兵 8/8 PASS、keep-warm + 開機驗證任務雙雙 live（commit `7e06d2f50`）。本工單新增 **DA-4/5/6**（NVIDIA hook 韌性 / keep-warm 永久化 / 健康哨兵容器化），把今日新增的本機過渡層一併納永久化。

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

## DA-4 · P0 · NVIDIA Container Toolkit hook 韌性（防 GPU 推論全斷）

> ⚡ **2026-06-16 PM 實際發生並已本機修復**：本機重啟後 NVIDIA Container Toolkit 的 OCI prestart hook 崩潰（`ld.so _dl_setup_hash` 斷言、驅動 610.47 + WSL2 toolkit）→ ck-ollama 無法以 GPU 啟動、runner 崩潰 ×18、**所有 LLM 推論逾時、/v1 全 499**，但 healthcheck（`ollama list`）仍綠掩蓋。`docker restart` 反把容器停成 Exited（確定性崩潰）。**正解＝`wsl --shutdown` 重啟 Docker 引擎 re-init toolkit**（已驗證）。詳見 [`2026-06-16-post-restart-ollama-nvidia-hook-incident.md`](2026-06-16-post-restart-ollama-nvidia-hook-incident.md)。

### 步驟（永久韌性）
1. **偵測**：stack 內健康哨兵（見 DA-6）週期檢「`docker logs ck-ollama` 近 5min 有無 `Inconsistency detected by ld.so`」+「真推論 200」→ 非 healthcheck。
2. **環境固化**：runbook 記錄相依版本下限（Docker Desktop / NVIDIA Container Toolkit ≥ 對應驅動 610.47 的相容版），重啟後若再現先 `wsl --shutdown`，仍崩則升級 toolkit。
3. **告警**：哨兵偵測到崩潰 → log/通知（不在容器內自動 `wsl --shutdown`，屬 host 層）。

### DoD（functional）
- 模擬：`docker logs` 含 ld.so 崩潰時，哨兵在 1 輪內標 CRITICAL 並輸出「須 wsl --shutdown」。
- runbook 有「重啟後 GPU 推論斷」SOP（指向 §C-G + wsl 修復）。

---

## DA-5 · P2 · keep-warm 永久化（降冷啟動延遲）

> ⚡ **2026-06-16 PM 已本機 live**（內建 `tick-driver.ps1`，commit `7e06d2f50`）：ollama `OLLAMA_KEEP_ALIVE=30m`，閒置卸載主模型 → 下次 /v1 冷啟動可達 240s 逾時。本機過渡＝既有 5min tick 順帶「qwen 不在 GPU 就 re-warm」（自我限制、實測 1s 跳過/11s re-warm）。

### 步驟（永久化）
- ollama compose 設 `OLLAMA_KEEP_ALIVE=-1`（永不卸載，主模型常駐 GPU）或由 DA-2/DA-6 sidecar 週期 re-warm。
- 二擇一：`-1` 最簡（代價：~5GB GPU 常駐）；sidecar re-warm 較省（卸載後才載）。

### DoD
- 閒置 >35min 後首次 /v1 對話延遲 ≈ 暖機（~45s）而非冷啟動（>120s）。

---

## DA-6 · P1 · 健康哨兵 sidecar（functional smoke 容器化）

> ⚡ **2026-06-16 PM 本機過渡已 live**：`meta-memory-engine/health-smoke.ps1`（8 檢查 §C+§C-G、記 log、可 `-AutoRemediate`）+ Windows 任務 `CK-Hermes-Health-Smoke`（開機後 3min）。但屬本機、不可攜、未版控於 stack。

### 步驟
- 把 health-smoke 8 檢查（GPU hook/ollama 推論/meta 權限/R1/R2 cron/UI/v1）移植成 stack 內 sidecar 或 CI smoke（同網路、hermes uid）：週期跑 + 結果推 Prometheus/Loki（已有 PLG 觀測棧）→ Grafana 面板 + Alertmanager 告警。
- 與 DA-2 tick sidecar 可合一（同一 ops sidecar 跑 cron tick + keep-warm + health smoke）。

### DoD
- sidecar 跑後 Grafana 見 8 檢查狀態時序；故意斷一項（如 chown root meta）→ Alertmanager 告警。

---

## 優先序

```
P0  DA-3 權限持久化       ← 防 chat 入口再死（權限翻 root）
P0  DA-4 NVIDIA hook 韌性 ← 防 GPU 推論全斷（6/16 實際發生）
P1  DA-1 R1 繁簡上線      ← 深化交流體感最大、CP 最高
P1  DA-2 tick sidecar     ← R2 跨機可攜、移除本機過渡任務
P1  DA-6 健康哨兵 sidecar ← functional smoke 容器化 + 接 PLG 告警（可與 DA-2 合一）
P2  DA-5 keep-warm 永久化 ← 降冷啟動延遲（本機已 live，永久化即設定）
```

> 本機過渡層現況（commit `7e06d2f50`，重啟存活但 `--force-recreate`/image-pull 丟失）：R1 繁簡 patch / R2 cron+tick / meta 權限 chown / **keep-warm（tick 內建）/ health-smoke 哨兵（開機任務）**。DA-1~6 即把這整層遷成隨 stack 版控。
> 另：WO-2（CK_Missive 開 `/api/ai/memory/digest`，S3 唯一外部阻斷）與 WO-3（WS-D 業務分流）維持原工單，與本工單互補（事實歸後端、對話歸 meta）。
