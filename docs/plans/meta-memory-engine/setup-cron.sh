#!/usr/bin/env bash
# R2 記憶引擎 — 一鍵復原 meta daily cron（--no-agent 純腳本模式）
#
# 背景：meta 大腦的「每日萃取→briefings→喚醒」是 SOUL 承諾的時間連貫來源，
#       但 2026-06-15 發現它自 5/2 凍結。根因兩層：
#         (1) 舊 cron 為 agent 模式 → 每次把 script stdout 送 LLM → 413 payload too large（每日失敗）
#         (2) 重啟後 gateway 內建 cron 排程器未 tick（pid lock 偵測在 Docker 失敗 → 排程器自我停用）
#       本腳本解 (1)：用 --no-agent 純腳本模式註冊（writer 自足、不經 qwen）。
#       (2) 由 tick-driver.sh + 外部排程驅動（見 README）。
#
# 用法（在宿主機，需 ck-hermes-gateway 運行中）：
#   bash setup-cron.sh
# 冪等：重複跑會先移除同名舊 job 再建。
set -euo pipefail

GW="${HERMES_GATEWAY_CONTAINER:-ck-hermes-gateway}"
HERMES="/opt/hermes/.venv/bin/hermes"
HOME_ENV="HERMES_HOME=/opt/data"      # active_profile=meta，cron 為 profile-scoped
UID_GID="10000:10000"                  # 必須以 hermes 身分建，否則 jobs.json root-owned → gateway 讀不到

# MSYS_NO_PATHCONV=1 防 Git Bash 把 /opt/... 改寫成 Windows 路徑
dex() { MSYS_NO_PATHCONV=1 docker exec -e "$HOME_ENV" -u "$UID_GID" "$GW" "$@"; }
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 關鍵：cron --script 解析到 **profile-scoped** scripts 目錄 /opt/data/profiles/meta/scripts/
# （非 root /opt/data/scripts/）。writer 不在那 → cron 報 "Script not found"。
# 故先把版控鏡像佈到 profile scripts 目錄並 chown hermes。
echo "== 佈署 writer 到 profile scripts 目錄 =="
MSYS_NO_PATHCONV=1 docker exec "$GW" mkdir -p /opt/data/profiles/meta/scripts
MSYS_NO_PATHCONV=1 docker cp "$SELF_DIR/daily-closing-writer.py"   "$GW:/opt/data/profiles/meta/scripts/daily-closing-writer.py"
MSYS_NO_PATHCONV=1 docker cp "$SELF_DIR/daily-awakening-writer.py" "$GW:/opt/data/profiles/meta/scripts/daily-awakening-writer.py"
MSYS_NO_PATHCONV=1 docker exec "$GW" chown -R "$UID_GID" /opt/data/profiles/meta/scripts

echo "== 移除同名舊 job（冪等）=="
for name in daily-closing-v5 daily-awakening-v2; do
  ids=$(dex "$HERMES" cron list 2>/dev/null | awk -v n="$name" '
    /^\s+[0-9a-f]{12} \[/{id=$1} $0 ~ ("Name:.*"n){print id}')
  for id in $ids; do echo "  remove $name ($id)"; dex "$HERMES" cron remove "$id" >/dev/null 2>&1 || true; done
done

echo "== 註冊 daily-closing-v5（23:00 TPE = 15:00 UTC）=="
dex "$HERMES" cron create "0 15 * * *" --name daily-closing-v5 \
  --script daily-closing-writer.py --no-agent --deliver local

echo "== 註冊 daily-awakening-v2（07:30 TPE = 23:30 UTC）=="
dex "$HERMES" cron create "30 23 * * *" --name daily-awakening-v2 \
  --script daily-awakening-writer.py --no-agent --deliver local

echo "== 確認 cron 檔 hermes 擁有（防 root-owned 鎖死）=="
MSYS_NO_PATHCONV=1 docker exec "$GW" chown -R "$UID_GID" /opt/data/profiles/meta/cron

echo "== 現況 =="
dex "$HERMES" cron list 2>/dev/null | grep -iE "daily-|Mode|active" || true
echo "DONE — 排程驅動見 tick-driver.sh / README.md"
