# Hermes 平臺 — 重啟後 functional smoke（標準化驗證程序）
#
# 為何：本機重啟是 CK 平臺反覆風險源（6/15 bind mount 權限翻 root；6/16 NVIDIA Container
#   Toolkit hook 崩潰致推論全斷）。兩者共通＝「healthcheck 仍綠但 functional 已死」，唯有端到端
#   功能探針能抓。本腳本把 RESTART_CHECKLIST_2026-06-16 §C + §C-G 編碼成可執行、可排程、會記 log
#   的程序，取代「靠人記得手動跑 checklist」。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File health-smoke.ps1            # 完整（含 /v1 ~50s）
#   powershell ... -File health-smoke.ps1 -Quick                                    # 快速（跳過慢 /v1 對話）
#   powershell ... -File health-smoke.ps1 -AutoRemediate                            # 偵測 NVIDIA hook 崩潰時自動跑 wsl 修復（破壞性：全容器循環）
#   powershell ... -File health-smoke.ps1 -Register                                 # 註冊開機自動執行（CK-Hermes-Health-Smoke 任務）
#
# 結果：逐項 PASS/WARN/FAIL 寫主控台 + health-smoke.log（同目錄、append、含時間戳）。
#   退出碼 0=全綠 / 1=有 WARN（非阻斷）/ 2=有 CRITICAL FAIL。
# 長期歸宿：CK_AaaP hermes-stack 內建健康哨兵（DA 系列）。本檔為本機標準化過渡。

param(
  [switch]$Quick,
  [switch]$AutoRemediate,
  [switch]$Register
)

$ErrorActionPreference = 'SilentlyContinue'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $here 'health-smoke.log'
$ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

# ─── 自我註冊為開機任務 ──────────────────────────────────────────
if ($Register) {
  $self = $MyInvocation.MyCommand.Path
  $arg = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $self + '"'
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
  # 開機後延遲 3 分鐘（等 Docker Desktop + WSL2 + 51 容器起來）
  $trigger = New-ScheduledTaskTrigger -AtLogOn
  $trigger.Delay = 'PT3M'
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
  try {
    Register-ScheduledTask -TaskName 'CK-Hermes-Health-Smoke' -Action $action -Trigger $trigger `
      -Settings $settings -Description 'Hermes 平臺重啟後 functional smoke（§C+§C-G）' -Force -ErrorAction Stop | Out-Null
    Write-Output "[$ts] 已註冊開機任務 CK-Hermes-Health-Smoke（登入後延遲 3 分鐘執行）"
    exit 0
  } catch {
    Write-Output "[$ts] 註冊失敗：$($_.Exception.Message)"
    exit 1
  }
}

# ─── 結果收集 ────────────────────────────────────────────────────
$results = @()
function Add-Result($name, $status, $detail) {
  $script:results += [pscustomobject]@{ Name = $name; Status = $status; Detail = $detail }
}

# 等 Docker 引擎就緒（開機情境）
$dockerReady = $false
for ($i = 0; $i -lt 18; $i++) {
  & $docker info *> $null
  if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
  Start-Sleep -Seconds 5
}
if (-not $dockerReady) {
  Add-Result 'docker-engine' 'CRITICAL' 'docker info 90s 內未就緒'
} else {

  # G-1 NVIDIA hook 未崩潰（最關鍵 — 6/16 P0 來源）
  $crashes = (& $docker logs ck-ollama --since 5m 2>&1 | Select-String 'Inconsistency detected by ld.so').Count
  if ($crashes -eq 0) { Add-Result 'G-1 nvidia-hook' 'PASS' '近 5min 0 次 ld.so 崩潰' }
  else { Add-Result 'G-1 nvidia-hook' 'CRITICAL' "$crashes 次 ld.so 崩潰 → GPU 推論斷，須 wsl --shutdown" }

  # G-2 ollama 真推論（functional，非 healthcheck）— 用 ollama run 避免 JSON 引號跨 PowerShell/docker exec 失真
  $infer = & $docker exec ck-ollama ollama run qwen2.5:7b-ctx64k '用繁體中文說你好' 2>$null
  $ec = $LASTEXITCODE
  if ($ec -eq 0 -and ("$infer").Trim().Length -gt 0) { Add-Result 'G-2 ollama-infer' 'PASS' 'qwen 推論成功（runner 正常）' }
  else { Add-Result 'G-2 ollama-infer' 'CRITICAL' "推論失敗 exit=$ec → 疑 NVIDIA hook 崩潰，須 wsl --shutdown" }

  # C-1a meta profile 權限（6/15 P0 來源）
  $owner = & $docker exec ck-hermes-gateway sh -c 'stat -c "%U" /opt/data/profiles/meta' 2>$null
  if ($owner -eq 'hermes') { Add-Result 'C-1a meta-perm' 'PASS' 'meta 由 hermes 擁有' }
  else { Add-Result 'C-1a meta-perm' 'CRITICAL' "meta 擁有者=$owner（非 hermes）→ /v1 將 500，須 chown 10000" }

  # C-2 R1 繁簡
  $r1 = & $docker exec ck-hermes-gateway /opt/hermes/.venv/bin/python3 -c "from gateway.zh_convert import is_enabled; print(is_enabled())" 2>$null
  if ($r1 -match 'True') { Add-Result 'C-2 r1-zh' 'PASS' 'is_enabled True' }
  else { Add-Result 'C-2 r1-zh' 'WARN' "is_enabled=$r1（繁簡後處理未生效，--force-recreate 後須 r1-zh-convert-runtime-apply.sh）" }

  # C-3 R2 cron 存在
  $cron = & $docker exec -e HERMES_HOME=/opt/data -u 10000:10000 ck-hermes-gateway /opt/hermes/.venv/bin/hermes cron list 2>$null
  $cronStr = ($cron | Out-String)
  if (($cronStr -match 'daily-closing-v5') -and ($cronStr -match 'daily-awakening-v2')) { Add-Result 'C-3 r2-cron' 'PASS' 'daily-closing-v5 + daily-awakening-v2 在冊' }
  else { Add-Result 'C-3 r2-cron' 'WARN' 'R2 cron 缺項，須 setup-cron.sh' }

  # C-3b Windows tick 任務在跑
  $tick = Get-ScheduledTask -TaskName 'CK-Hermes-Cron-Tick' -ErrorAction SilentlyContinue
  if ($tick -and $tick.State -ne 'Disabled') { Add-Result 'C-3b tick-task' 'PASS' "CK-Hermes-Cron-Tick $($tick.State)" }
  else { Add-Result 'C-3b tick-task' 'WARN' 'CK-Hermes-Cron-Tick 不存在/停用 → R2 不自主 fire' }

  # C-3c S3 聯邦 digest 落地（R-5，2026-07-08）— 驗最新晨間 briefing 含聯邦 digest。
  # 判定用 ASCII 標記「raw/federation/」（成功行才有的連結），避免 CJK 跨 PowerShell/docker exec 失真。
  # 背景：段C collector 曾因 ops sidecar 缺 MISSIVE env 靜默失敗兩晚（briefing 只見「不可達」），
  # 哨兵化防同型 fail-silent 再潛伏。WARN 級（非阻斷；失敗原因看 briefing 平臺行＝R-3 儀器化輸出）。
  $fed = & $docker exec ck-hermes-gateway sh -c 'f=$(ls -t /opt/data/profiles/meta/wiki/briefings/morning-*.md 2>/dev/null | head -1); if [ -z "$f" ]; then echo NOFILE; elif grep -q "raw/federation/" "$f"; then echo FEDOK; else echo FEDFAIL; fi' 2>$null
  $fedStr = "$fed".Trim()
  if ($fedStr -eq 'FEDOK') { Add-Result 'C-3c federation' 'PASS' '最新晨間 briefing 含聯邦 digest（raw/federation 連結在）' }
  elseif ($fedStr -eq 'FEDFAIL') { Add-Result 'C-3c federation' 'WARN' '最新 briefing 無聯邦 digest → 看 briefing 平臺行失敗原因；查 ops 容器 MISSIVE env / Missive digest 端點' }
  else { Add-Result 'C-3c federation' 'WARN' "聯邦檢查異常（$fedStr）→ briefings 目錄無檔或探針失敗" }

  # C-3d 兩 copy 漂移（2026-07-08）— repo 版控副本 vs volume 執行副本（cron 真跑的是 volume 那份）。
  # 本專案反覆失敗家族「改錯檔/兩 copy 未同源」的哨兵化：任一 writer 內容不一致即 WARN。
  # 比對前去 \r（CRLF/LF 正規化），避免 git autocrlf 造成假陽性。
  $md5 = [System.Security.Cryptography.MD5]::Create()
  $driftList = @()
  foreach ($s in @('daily-closing-writer.py', 'daily-awakening-writer.py')) {
    $localPath = Join-Path $here $s
    if (-not (Test-Path $localPath)) { $driftList += "$s(repo 缺檔)"; continue }
    $txt = (Get-Content -Raw -Encoding UTF8 $localPath) -replace "`r", ""
    $lh = ([BitConverter]::ToString($md5.ComputeHash([Text.Encoding]::UTF8.GetBytes($txt))) -replace '-', '').ToLower()
    $vh = ("$(& $docker exec ck-hermes-gateway sh -c "tr -d '\r' < /opt/data/profiles/meta/scripts/$s | md5sum" 2>$null)" -split '\s+')[0]
    if (-not $vh) { $driftList += "$s(volume 缺檔/探針失敗)" }
    elseif ($lh -ne $vh) { $driftList += $s }
  }
  if ($driftList.Count -eq 0) { Add-Result 'C-3d copy-sync' 'PASS' 'repo↔volume 兩 copy 一致（closing+awakening）' }
  else { Add-Result 'C-3d copy-sync' 'WARN' ("兩 copy 漂移：{0} → docker cp repo 版入 volume + chown 10000（勿反向蓋掉版控）" -f ($driftList -join ', ')) }

  # C-4 Open WebUI
  $ui = & $docker exec ck-hermes-gateway sh -c 'curl -s -m 15 -o /dev/null -w "%{http_code}" http://ck-open-webui:8080' 2>$null
  if ($ui -eq '200' -or $ui -eq '302') { Add-Result 'C-4 open-webui' 'PASS' "UI $ui" }
  else { Add-Result 'C-4 open-webui' 'WARN' "Open WebUI 回 $ui" }

  # C-1b /v1 meta chat 端到端（慢 ~50s，-Quick 跳過）— python stdin urllib，避免 JSON 引號/CJK 編碼跨 PowerShell 失真
  if (-not $Quick) {
    $py = @'
import os,json,urllib.request as u,urllib.error as e
k=os.environ['API_SERVER_KEY']
d=json.dumps({'model':'meta','messages':[{'role':'user','content':'ping'}]}).encode()
req=u.Request('http://localhost:8642/v1/chat/completions',data=d,headers={'Authorization':'Bearer '+k,'Content-Type':'application/json'})
try:
    print(u.urlopen(req,timeout=240).status)
except e.HTTPError as ex:
    print(ex.code)
except Exception as ex:
    print('ERR')
'@
    $v1 = "$(($py | & $docker exec -i ck-hermes-gateway /opt/hermes/.venv/bin/python3 - 2>$null) | Select-Object -Last 1)".Trim()
    if ($v1 -eq '200') { Add-Result 'C-1b v1-chat' 'PASS' 'meta /v1 200' }
    else { Add-Result 'C-1b v1-chat' 'CRITICAL' "meta /v1 回 $v1（端到端對話入口故障）" }
  } else {
    Add-Result 'C-1b v1-chat' 'SKIP' '-Quick 跳過'
  }

  # C-1c /v1 業務查詢 dispatch 攔截（慢 ~70s，-Quick 跳過）— 驗候選#3：回應不應是文字化 tool_call
  # 弱模型有時把 query.py agent_query 寫成文字不執行；攔截生效則回填真答案（含數字）。
  if (-not $Quick) {
    $pyd = @'
import os,json,re,urllib.request as u
k=os.environ['API_SERVER_KEY']
d=json.dumps({'model':'meta','messages':[{'role':'user','content':'系統裡公文總共幾份？'}]}).encode()
req=u.Request('http://localhost:8642/v1/chat/completions',data=d,headers={'Authorization':'Bearer '+k,'Content-Type':'application/json'})
try:
    c=json.loads(u.urlopen(req,timeout=240).read())['choices'][0]['message']['content']
    print('TEXTIFIED' if ('query.py' in c and 'agent_query' in c) else ('OK' if re.search(r'\d',c) else 'NONUM'))
except Exception:
    print('ERR')
'@
    # 本檢查專驗「攔截安全網健康」＝回應不應洩漏文字化 tool_call。TEXTIFIED 才是攔截壞掉；
    # NONUM（模型未回數字）屬回應變異非攔截問題，不讓 health-smoke 因模型變異 flap 成 WARN。
    $disp = "$(($pyd | & $docker exec -i ck-hermes-gateway /opt/hermes/.venv/bin/python3 - 2>$null) | Select-Object -Last 1)".Trim()
    if ($disp -eq 'OK') { Add-Result 'C-1c dispatch' 'PASS' '業務查詢回真答案（含數字、無文字化 tool_call）' }
    elseif ($disp -eq 'NONUM') { Add-Result 'C-1c dispatch' 'PASS' '無文字化 tool_call（攔截健康）；本次模型未回數字＝回應變異' }
    elseif ($disp -eq 'TEXTIFIED') { Add-Result 'C-1c dispatch' 'WARN' '回文字化 tool_call → 攔截未生效，查 HERMES_V1_DISPATCH_FIX / dispatch_intercept' }
    else { Add-Result 'C-1c dispatch' 'WARN' "dispatch 探針回 $disp（非阻斷；探針/後端暫態）" }
  } else {
    Add-Result 'C-1c dispatch' 'SKIP' '-Quick 跳過'
  }
}

# ─── 輸出 + log ──────────────────────────────────────────────────
$nFail = @($results | Where-Object { $_.Status -eq 'CRITICAL' }).Count
$nWarn = @($results | Where-Object { $_.Status -eq 'WARN' }).Count
$overall = if ($nFail -gt 0) { 'CRITICAL' } elseif ($nWarn -gt 0) { 'WARN' } else { 'PASS' }

Write-Output "===== Hermes Health Smoke @ $ts ====="
foreach ($r in $results) {
  $mark = switch ($r.Status) { 'PASS' { 'OK  ' } 'WARN' { 'WARN' } 'CRITICAL' { 'FAIL' } default { '--  ' } }
  Write-Output ("  [{0}] {1,-18} {2}" -f $mark, $r.Name, $r.Detail)
}
Write-Output "===== 總判定：$overall（FAIL=$nFail WARN=$nWarn）====="

# log（單行摘要，便於 grep/趨勢）
$summary = ($results | ForEach-Object { "$($_.Name)=$($_.Status)" }) -join ' '
Add-Content -Path $logFile -Value "[$ts] OVERALL=$overall | $summary" -Encoding utf8

# ─── NVIDIA hook 崩潰自動修復（opt-in）─────────────────────────────
$hookCrash = ($results | Where-Object { $_.Name -eq 'G-1 nvidia-hook' -and $_.Status -eq 'CRITICAL' }).Count -gt 0
if ($hookCrash) {
  if ($AutoRemediate) {
    Write-Output "[$ts] 偵測 NVIDIA hook 崩潰 → 執行 wsl --shutdown（Docker 引擎將重啟、全容器循環）..."
    Add-Content -Path $logFile -Value "[$ts] AUTO-REMEDIATE: wsl --shutdown" -Encoding utf8
    wsl --shutdown
    Write-Output "[$ts] wsl --shutdown 已下達。等 Docker 引擎恢復後請重跑本腳本驗證（Docker Desktop app 會自動重啟引擎）。"
  } else {
    Write-Output ">>> 修復：PowerShell 執行 'wsl --shutdown'（Docker Desktop 會自動重啟引擎、re-init NVIDIA toolkit）；勿用 docker restart ck-ollama。或重跑本腳本加 -AutoRemediate。"
  }
}

$exitCode = 0
if ($overall -eq 'CRITICAL') { $exitCode = 2 } elseif ($overall -eq 'WARN') { $exitCode = 1 }
exit $exitCode
