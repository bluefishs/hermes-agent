# Meta 記憶引擎（R2）— 診斷、復原與版控

> 2026-06-15 · CK_Hermes session。關聯 [`../2026-06-15-meta-chat-restore.md`](../2026-06-15-meta-chat-restore.md) §4 R2。
> 使用者授權：「全面復原 + 納版控」。

## 這是什麼

meta 大腦（`profiles/meta`）的 SOUL 承諾「我記得昨天、上週、上個月」。其底層機制＝兩個 daily cron：
- **daily-closing**（23:00 TPE）：`daily-closing-writer.py` 從 `wiki/log.md` 抽當日條目 → 寫 `wiki/daily/YYYY-MM-DD.md`
- **daily-awakening**（07:30 TPE）：`daily-awakening-writer.py` 讀前日 daily → 寫 `wiki/briefings/morning-YYYY-MM-DD.md`

兩支 writer **純 Python、不依賴 LLM、idempotent**（自足完成 file I/O）。

## 凍結根因（2026-06-15 實測鎖定，四層）

| 層 | 發現 | 證據 | 修法 |
|---|---|---|---|
| **1. 舊 cron 是 agent 模式** | 每次把 script stdout 餵 LLM → prompt 爆量 | `agent.log`：`cron_c86963f36259 ... 413 payload too large` **每日**（4/29–5/2） | `--no-agent` 純腳本 |
| **2. 重啟後 gateway 內建排程器不 tick** | gateway in-process ticker 在此 Docker 部署未驅動 | 每分鐘探針 cron **95s 未 fire**；`cron status`＝「Gateway is not running」（`find_gateway_pids`/pid lock 偵測在容器失敗→排程器自停）；`.tick.lock` 凍 5/3 | 外部 `hermes cron tick` 驅動（見 tick-driver.sh） |
| **3. 腳本路徑作用域** | `--script` 解析到 **profile** scripts 目錄 `profiles/meta/scripts/`，writer 在 root `/opt/data/scripts/` | cron last_status：`error: Script not found: /opt/data/profiles/meta/scripts/daily-closing-writer.py` | 佈 writer 到 profile scripts 目錄（setup-cron.sh 已含） |
| **4. cron 檔擁有者** | root 建的 cron → jobs.json root-owned → gateway(hermes) 讀不到 | `cron tick`：`PermissionError: .../meta/cron/jobs.json` | `chown hermes` cron 檔 |

→ 結果：`briefings/` 停 `morning-2026-05-03`、`daily/` 停 `2026-05-02`，連貫敘事空了 6 週。

**✅ tick 機制已證可用**：四層修齊後，標準 `hermes cron tick`（standalone）對 daily-closing-v5 / daily-awakening-v2 **end-to-end 執行成功**（`cron run`+`tick` → writer 跑 → 寫出 daily/briefing → `last_status: ok`）。即「gateway 內建排程器不 tick」可由**外部週期呼叫 `hermes cron tick`** 完全繞過。

## 已做的修復（2026-06-15，live 全驗證）

1. **engine core**：手動跑兩支 writer（hermes 身分）→ 寫出 `daily/2026-06-15.md` + `briefings/morning-2026-06-15.md`。✅
2. **解層 1（413）**：`--no-agent` 純腳本模式註冊兩 cron（不經 qwen）。`daily-closing-v5`（`0 15 * * *`）、`daily-awakening-v2`（`30 23 * * *`），deliver local。
3. **解層 3（路徑）**：writer 佈到 `/opt/data/profiles/meta/scripts/`（profile-scoped）。
4. **解層 4（權限）**：cron 檔 + profile scripts 目錄 `chown hermes`。
5. **端到端驗證**：`hermes cron tick` 對兩 cron 各跑一次 → `last_status: ok`、wiki 檔正確產出。✅

## 排程驅動（解層 2）— ✅ 本機已啟用（2026-06-15）

gateway 內建排程器不 tick，但**外部 `hermes cron tick` 已證可執行到期 job**（file-lock 保 at-most-once、與其他 ticker 並存安全）。

**本機過渡方案已安裝並 end-to-end 驗證**：Windows 工作排程器任務 `CK-Hermes-Cron-Tick`，每 5 分鐘跑 [`tick-driver.ps1`](tick-driver.ps1) → `hermes cron tick`。驗證：強制 daily-closing 到期 → Start-ScheduledTask → `LastTaskResult=0` + daily wiki 檔由 task 驅動的 tick 正確產出。∴ R2 **全自動**：每日 23:00 TPE 寫 daily、07:30 TPE 寫 morning briefing。

**長期歸宿（建議遷移）**：CK_AaaP hermes-stack sidecar（每 1–5 分鐘 `hermes cron tick`，版控於 compose、隨 stack 起落、跨機器可攜）。遷移後可移除本機 Windows 任務（雙驅動因 file-lock 安全，但無必要）。

### Windows 任務管理（PowerShell）
```powershell
# 查狀態 / 上次結果
Get-ScheduledTask  -TaskName CK-Hermes-Cron-Tick
Get-ScheduledTaskInfo -TaskName CK-Hermes-Cron-Tick   # LastTaskResult 應 0
# 立即跑一次（手動）
Start-ScheduledTask -TaskName CK-Hermes-Cron-Tick
# 移除（遷 sidecar 後）
Unregister-ScheduledTask -TaskName CK-Hermes-Cron-Tick -Confirm:$false
# 重新安裝：見本檔末「重啟後一鍵復原」或 git log feat(meta) R2 commit 的註冊指令
```
> ⚠️ 任務跨重啟存活（`-StartWhenAvailable` + 3650 天重複），但依賴 Docker Desktop 已啟動（登入後自動起）。重啟後若 cron 凍結，先跑 `setup-cron.sh` 再確認任務 State=Ready。

## 重啟後一鍵復原

```bash
# 1. 確保 profile / cron 權限（見 ../RESTART_CHECKLIST_2026-06-15.md §A）
docker exec ck-hermes-gateway sh -c 'chown -R 10000:10000 /opt/data/profiles/meta/cron'
# 2. 把 writer 腳本佈到 /opt/data/scripts/（= 宿主 C:\Users\User1\.hermes\scripts\）— 若遺失才需
#    （本目錄 daily-*-writer.py 為版控鏡像；live 源為 /opt/data/scripts/）
# 3. 重新註冊 cron（冪等）
bash setup-cron.sh
# 4. 啟用 tick 驅動（見 tick-driver.sh，擇一安裝）
```

## 檔案

| 檔 | 用途 |
|---|---|
| `daily-closing-writer.py` / `daily-awakening-writer.py` | 版控鏡像（live 源 `/opt/data/scripts/`）。純 Python、idempotent |
| `setup-cron.sh` | 冪等註冊兩 cron（--no-agent / deliver local / hermes 擁有） |
| `tick-driver.sh` | 外部 tick 驅動（解排程器不 tick），每分鐘呼叫 |
| `health-smoke.ps1` | **重啟後 functional smoke 哨兵**（標準化 §C+§C-G 驗證，見下節） |
| `health-smoke.log` | smoke 每次執行的單行摘要（append，便於趨勢/grep） |

## 重啟後 functional smoke 哨兵（health-smoke.ps1）— 2026-06-16 PM

> 緣由：本機重啟是 CK 平臺反覆風險源——6/15 bind mount 權限翻 root（/v1 500）、6/16 NVIDIA Container Toolkit hook 崩潰（推論全斷、/v1 全 499）。兩者共通＝**healthcheck 仍綠但 functional 已死**，唯端到端功能探針能抓。本腳本把 [`../RESTART_CHECKLIST_2026-06-16.md`](../RESTART_CHECKLIST_2026-06-16.md) §C+§C-G 編碼成可執行哨兵，取代「靠人記得手動跑 checklist」。詳見 [`../2026-06-16-post-restart-ollama-nvidia-hook-incident.md`](../2026-06-16-post-restart-ollama-nvidia-hook-incident.md)。

**驗 7 項**：G-1 NVIDIA hook 未崩潰 / G-2 ollama 真推論（`ollama run`，非 healthcheck）/ C-1a meta 權限 / C-2 R1 繁簡 / C-3 R2 cron / C-3b tick 任務 / C-4 Open WebUI（+ 完整模式 C-1b /v1 meta chat 200）。輸出逐項 PASS/WARN/FAIL + 寫 `health-smoke.log`；退出碼 0/1/2。

```powershell
# 手動跑（完整含 /v1 ~50s）
powershell -NoProfile -ExecutionPolicy Bypass -File health-smoke.ps1
# 快速（跳過慢 /v1，~15s；G-2 的 ollama run 會順帶 keep-warm 主模型）
powershell ... -File health-smoke.ps1 -Quick
# 偵測 NVIDIA hook 崩潰時自動跑 wsl 修復（破壞性：全容器循環）
powershell ... -File health-smoke.ps1 -AutoRemediate
```

**註冊開機自動驗（需提權 PowerShell — Register-ScheduledTask/schtasks 在非提權 session 被 Access denied）**：
```powershell
# 方式 A：用腳本自註冊（登入後延遲 3 分鐘跑完整 smoke）
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\CKProject\CK_Hermes\docs\plans\meta-memory-engine\health-smoke.ps1" -Register
# 方式 B：schtasks 等價（亦可改 /sc MINUTE /mo 25 跑 -Quick 當「健康趨勢 + keep-warm」雙用）
schtasks /create /tn "CK-Hermes-Health-Smoke" /tr "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"D:\CKProject\CK_Hermes\docs\plans\meta-memory-engine\health-smoke.ps1\"" /sc ONLOGON /delay 0003:00 /f
# 查/移除
Get-ScheduledTask -TaskName CK-Hermes-Health-Smoke ; Unregister-ScheduledTask -TaskName CK-Hermes-Health-Smoke -Confirm:$false
```

> 💡 **免費 keep-warm 優化（降冷啟動延遲）— 2026-06-16 PM 已內建於 [`tick-driver.ps1`](tick-driver.ps1)**：ollama `OLLAMA_KEEP_ALIVE=30m`，閒置 >30min 卸載主模型 → 下次 /v1 冷啟動可達 240s 逾時（6/16 實見）。既有每 5 分鐘的 `CK-Hermes-Cron-Tick` 現在順帶檢查：qwen 不在 GPU 就 `ollama run` re-warm（已載入則 `ollama ps` 秒判跳過＝自我限制、不長holdGPU 也不需新任務/提權）→ chat 幾乎永遠走「暖機 ~45s」而非「冷啟動逾時」。**實測**：卸載後跑 tick → 11s 內 qwen 回到 GPU（`29 minutes from now`）。零成本、純整合層、不動 compose。若要「零冷啟動」可把 tick 的 re-warm 改為無條件 ping（代價：模型 24/7 常駐）。長期歸宿仍是 CK_AaaP hermes-stack 內建（DA 系列）。

## 後續加值（非必要）

- writer 目前 script 模式無語意分析（pattern 欄位留白）。日後若 meta 主路徑換更強模型，可加一個「弱模型也安全」的小結步驟，但**勿回 agent 模式整段餵 LLM**（413 教訓）。
- meta 重新活躍寫 `log.md` 後，daily 的「今日動作摘要」會自然填充（目前 log 停在 5/18 → daily 多為靜默日屬正常）。
