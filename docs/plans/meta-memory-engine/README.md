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

## 後續加值（非必要）

- writer 目前 script 模式無語意分析（pattern 欄位留白）。日後若 meta 主路徑換更強模型，可加一個「弱模型也安全」的小結步驟，但**勿回 agent 模式整段餵 LLM**（413 教訓）。
- meta 重新活躍寫 `log.md` 後，daily 的「今日動作摘要」會自然填充（目前 log 停在 5/18 → daily 多為靜默日屬正常）。
