# R2 記憶引擎 — Windows tick 驅動（過渡方案，由 CK-Hermes-Cron-Tick 工作排程器每 5 分鐘呼叫）
#
# 為何：gateway 內建 cron 排程器在此 Docker 部署不 tick（2026-06-15 實測；pid lock 偵測在容器內失敗）。
#   `hermes cron tick` 跑「到期 job 一次」即退（未到期 no-op、極輕量；file-lock 保 at-most-once，與其他 ticker 並存安全）。
# 長期歸宿：CK_AaaP hermes-stack sidecar（版控於 compose、隨 stack 起落）。本檔為本機過渡。
#
# 安裝/移除見 README.md「啟用週期驅動」。手動測試：powershell -File tick-driver.ps1
$ErrorActionPreference = 'SilentlyContinue'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'

# (1) R2 cron tick（原職責）
& $docker exec -e HERMES_HOME=/opt/data -u 10000:10000 ck-hermes-gateway /opt/hermes/.venv/bin/hermes cron tick | Out-Null

# (2) Keep-warm（免費降冷啟動延遲，2026-06-16 PM 加）
#   ollama OLLAMA_KEEP_ALIVE=30m，主模型閒置 >30min 卸載 → 下次 /v1 冷啟動可達 240s 逾時（6/16 實見）。
#   本 tick 每 5min 跑：若 qwen 不在 GPU 就 re-warm（已載入則 ollama ps 秒判直接跳過）→ chat 永遠走 ~45s 暖機。
#   自我限制（只在卸載後才 load）、免額外排程任務、免提權。NVIDIA hook 崩潰時 ollama run 會失敗，被 SilentlyContinue 吞、不影響 cron tick。
$loaded = & $docker exec ck-ollama ollama ps 2>$null | Select-String 'qwen2.5:7b-ctx64k'
if (-not $loaded) {
  & $docker exec ck-ollama ollama run qwen2.5:7b-ctx64k 'hi' *> $null
}
exit 0
