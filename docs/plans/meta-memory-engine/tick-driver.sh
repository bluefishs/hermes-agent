#!/usr/bin/env bash
# R2 記憶引擎 — 外部 tick 驅動
#
# 為何需要：2026-06-15 實測 gateway 內建 cron 排程器在此 Docker 部署「不 tick」
#   （建每分鐘探針 cron，95s 未 fire；`hermes cron status` 回「Gateway is not running」——
#    pid lock 偵測在容器內失敗 → 排程器自我停用）。`hermes cron tick` 可手動跑「到期 job 一次」，
#   故由外部排程每分鐘呼叫一次即可可靠驅動，與 gateway 內建排程器解耦、deployment-agnostic。
#
# 跑法：每 1 分鐘呼叫一次（到期才執行，未到期 no-op、極輕量）。
#   - 以 hermes(10000:10000) 身分跑，避免 jobs.json 變 root-owned。
#   - HERMES_HOME=/opt/data（active_profile=meta）。
#
# 安裝（擇一，落 CK_AaaP / hermes-stack 或宿主）：
#   A) Windows 工作排程器（本機）：每 1 分鐘執行
#        powershell -Command "docker exec -e HERMES_HOME=/opt/data -u 10000:10000 ck-hermes-gateway /opt/hermes/.venv/bin/hermes cron tick"
#   B) hermes-stack 加 sidecar（推薦，隨 stack 起落）：
#        一個極小 container 每 60s 跑 `docker exec ... hermes cron tick`，或在 gateway compose 加 healthcheck-style loop。
#   C) 宿主 WSL/Git Bash 背景 loop（臨時驗證用）：
#        while true; do bash tick-driver.sh; sleep 60; done
set -euo pipefail
GW="${HERMES_GATEWAY_CONTAINER:-ck-hermes-gateway}"
MSYS_NO_PATHCONV=1 docker exec -e HERMES_HOME=/opt/data -u 10000:10000 "$GW" \
  /opt/hermes/.venv/bin/hermes cron tick 2>&1 || true
