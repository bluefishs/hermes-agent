# R2 記憶引擎 — Windows tick 驅動（過渡方案，由 CK-Hermes-Cron-Tick 工作排程器每 5 分鐘呼叫）
#
# 為何：gateway 內建 cron 排程器在此 Docker 部署不 tick（2026-06-15 實測；pid lock 偵測在容器內失敗）。
#   `hermes cron tick` 跑「到期 job 一次」即退（未到期 no-op、極輕量；file-lock 保 at-most-once，與其他 ticker 並存安全）。
# 長期歸宿：CK_AaaP hermes-stack sidecar（版控於 compose、隨 stack 起落）。本檔為本機過渡。
#
# 安裝/移除見 README.md「啟用週期驅動」。手動測試：powershell -File tick-driver.ps1
$ErrorActionPreference = 'SilentlyContinue'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
& $docker exec -e HERMES_HOME=/opt/data -u 10000:10000 ck-hermes-gateway /opt/hermes/.venv/bin/hermes cron tick | Out-Null
exit 0
