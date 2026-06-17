# 電腦重啟前/後 Checklist（Delta）— 2026-06-16

> 接續 [`RESTART_CHECKLIST_2026-06-15.md`](RESTART_CHECKLIST_2026-06-15.md)。完整復原程序沿用 [`RESTART_CHECKLIST_2026-05-25.md`](RESTART_CHECKLIST_2026-05-25.md)。
> 安全準則不變：不 `compose down` / **不 `--force-recreate`** / 不 `prune` / 不碰 DB / 不刪 volume·image。
> ⚠️ 本 session（6/15–6/16）有**多項 runtime production 變更**（非僅文件），重啟存活性見 §B。

---

## A. 版本對齊（2026-06-16 實測，無漂移）

| 檢查 | 期望 | 實測 |
|---|---|---|
| gateway/web/.env | v2026.5.22 | ✅ 全 `ckproject/hermes-agent:v2026.5.22` |
| 51 容器 | healthy | ✅ 0 unhealthy |
| restart policy | 自動回、**不 recreate** | ✅ hermes 4 容器 = `unless-stopped`（機器重啟自動回、保留 writable layer）|

## B. 本 session 持久變更 × 重啟存活性（關鍵）

| 變更 | 載體 | `docker restart`/機器重啟 | `--force-recreate`/image pull | 復原 |
|---|---|---|---|---|
| **meta profile 權限**（chown hermes 全 profile）| 容器 fs | ⚠️ 重啟後 entrypoint 跑、host 可能再翻 root → **必驗**（§C-1）| 同左 | `chown 10000:10000 /opt/data/profiles/*` |
| **R1 繁簡**（opencc 裝 venv + 注入 zh_convert.py + api_server.py 3 處 patch）| 容器 **writable layer** | ✅ **存活**（unless-stopped 不 recreate）| ❌ **丟失** | `bash r1-zh-convert-runtime-apply.sh`（一鍵重灌）|
| **R2 cron**（daily-closing-v5/awakening-v2 + writer 在 profile scripts）| bind mount `~/.hermes` | ✅ 存活 | ✅ 存活（bind mount）| `bash meta-memory-engine/setup-cron.sh` |
| **R2 tick 驅動**（Windows 任務 CK-Hermes-Cron-Tick）| Windows 工作排程器 | ✅ `StartWhenAvailable` 自動續（依賴 Docker Desktop 登入後自起）| n/a | 見 meta-memory-engine/README §Windows 任務管理 |
| **SOUL**（D-α/D-β 實測負向）| — | 已**還原**至 `SOUL.md.bak.20260616-pre-recall`，**無淨變更** | — | 備份齊（pre-recall / pre-mcptool / 20260602…）|

> 結論：**機器重啟（unless-stopped）下，R1 + R2 + 權限全部存活**；須人工的有**兩項**：①「若 host 把 meta 翻 root」→ §C-1 一行修；②**「若 NVIDIA hook 崩潰（GPU 推論全斷）」→ §C-G `wsl --shutdown` 修**（6/16 PM 實際發生並已驗證修復）。**切勿 `--force-recreate`**（會丟 R1 runtime patch 與 opencc）；**切勿用 `docker restart ck-ollama` 修 GPU hook**（確定性崩潰，restart 只會停容器）。

## C. 重啟後驗證（功能級，缺一不可 — healthcheck≠functional）

```bash
# C-1 meta 權限 + chat 入口（最高優先；6/15 曾因 root:root 700 → /v1 500）
docker exec ck-hermes-gateway ls -lad /opt/data/profiles/meta            # owner 應 hermes；若 root →
docker exec ck-hermes-gateway sh -c 'chown 10000:10000 /opt/data/profiles/*'
docker exec ck-hermes-gateway sh -c 'KEY=$(printenv API_SERVER_KEY); curl -s -o /dev/null -w "%{http_code}\n" -m 240 http://localhost:8642/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "{\"model\":\"meta\",\"messages\":[{\"role\":\"user\",\"content\":\"嗨\"}]}"'   # 期望 200

# C-2 R1 繁簡仍 active
docker exec ck-hermes-gateway /opt/hermes/.venv/bin/python3 -c "from gateway.zh_convert import is_enabled; print(is_enabled())"   # 期望 True；若 False/ImportError → bash r1-zh-convert-runtime-apply.sh

# C-3 R2 cron + Windows 任務
docker exec -e HERMES_HOME=/opt/data -u 10000:10000 ck-hermes-gateway /opt/hermes/.venv/bin/hermes cron list   # 應見 daily-closing-v5 / daily-awakening-v2
# PowerShell: Get-ScheduledTaskInfo -TaskName CK-Hermes-Cron-Tick   (State=Ready / LastResult=0)

# C-4 UI 服務
# 瀏覽器開 http://localhost:3010 (Open WebUI)；或 curl -o /dev/null -w "%{http_code}" http://localhost:3010 → 200
```

## C-G. GPU/推論探針（2026-06-16 PM 新增 — 重啟後 ollama NVIDIA hook 崩潰事故催生）

> ⚠️ **新增背景**：6/16 本機重啟後 NVIDIA Container Toolkit prestart hook 崩潰（`ld.so _dl_setup_hash` 斷言，驅動 610.47 + WSL2 toolkit），ck-ollama 無法以 GPU 啟動、**所有推論逾時、/v1 全 499**，但容器 healthcheck（`ollama list` 不載模型）仍綠 → 假象。C-1「/v1 200」雖能抓到但表現為慢逾時易誤判。**故新增直接 GPU/推論探針**。詳見 [`2026-06-16-post-restart-ollama-nvidia-hook-incident.md`](2026-06-16-post-restart-ollama-nvidia-hook-incident.md)。

```bash
# G-1 ollama runner 未崩潰（最關鍵）
docker logs ck-ollama --since 5m 2>&1 | grep -c "Inconsistency detected by ld.so"   # 期望 0；>0 = hook 崩潰
# G-2 ollama 真推論（functional，非 healthcheck）
docker exec ck-hermes-gateway sh -c 'curl -s -m 60 http://ck-ollama:11434/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen2.5:7b-ctx64k\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":10}" -o /dev/null -w "%{http_code}\n"'   # 期望 200
```

**若 G-1 > 0 或 G-2 ≠ 200（GPU hook 崩潰）→ 復原程序（已驗證有效）：**
```powershell
# PowerShell：重啟 WSL2 + Docker 引擎（re-init NVIDIA Container Toolkit）
wsl --shutdown            # docker-desktop distro 停止；Docker Desktop app 會自動重啟引擎
# 等 docker info 恢復（約數秒~1min），unless-stopped 容器自動回；ck-ollama 若是 Exited 需手動 docker start ck-ollama
# 重跑 G-1/G-2 + C-1 確認 200。R1/權限/R2 皆存活（已驗證）。
# 若 wsl 重啟仍崩潰 → 更新 Docker Desktop / NVIDIA Container Toolkit，或回退 GPU 驅動。
```
> ⚠️ 切勿用 `docker restart ck-ollama` 當修復——hook 崩潰是確定性的，restart 只會把容器停成 Exited（已實測）。正解是 wsl 引擎層重啟。

## D. 本 session 成果（重啟後應維持）

- ✅ chat 入口修復（500→200，meta 權限 chown）
- ✅ R1 繁簡 **live**（零簡體；runtime patch，永久化待 CK_AaaP DA-1）
- ✅ R2 記憶引擎自主運轉（昨晚 daily-closing fire ok；每日 23:00/07:30 TPE）
- ✅ chat 機制 + UI 端到端確認（Open WebUI → gateway → meta 200）
- 📋 盤點複查定論：meta 深度記憶瓶頸坐實在模型強度（D-δ），prompt 層 recall 強化已證無效

## E. 待 deploy（重啟不影響，落他 session）

- CK_AaaP：DA-1 R1 image rebuild 永久化 / DA-2 tick sidecar（取代 Windows 任務）/ DA-3 權限持久化 entrypoint（免 §C-1 人工）
- CK_Missive：WO-2 開 `/api/ai/memory/digest`（S3 405）

## F. 重啟前最後確認（一眼 GO）

```
✅ v2026.5.22 = 運行映像（unless-stopped、不 recreate、無漂移）
✅ git working tree clean（91fdc89ad；本 session commits 全落地）
✅ R1 is_enabled True / R2 cron×2 + Windows 任務 Ready / meta hermes 擁有
✅ 備份齊：SOUL.md.bak.* / api_server.py.bak.20260616-pre-r1 / config.yaml.bak.*
⚠️ 重啟後務必跑 §C-1~C-4 functional 驗證（尤其 /v1 200）；勿 --force-recreate
```
