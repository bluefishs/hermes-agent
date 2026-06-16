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

> 結論：**機器重啟（unless-stopped）下，R1 + R2 + 權限全部存活**；唯一須人工的是「若 host 把 meta 翻 root」→ §C-1 一行修。**切勿 `--force-recreate`**（會丟 R1 runtime patch 與 opencc）。

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
