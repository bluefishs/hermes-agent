#!/bin/bash
# refresh-adr-index.sh — 手動更新 ADR index（Variant B 資料源）
#
# 用法：bash scripts/refresh-adr-index.sh
#
# 把跨 6 repo 的 ADR 萃取為 JSON index 寫到 wiki/raw/，供 ck-adr-query skill
# 容器內 mount path 讀取。
#
# 設計原因：
# - hermes-gateway 容器看不到 host D:/CKProject 6 repo
# - cron 30min 自動更新對 ADR query 完全足夠（ADR 不會 30 分內變動 5 次）
# - 為避免 Windows Task Scheduler 配置複雜，先提供手動 trigger；使用者
#   可在 ADR 重大變動後手動跑

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_AGENT="$(cd "$SCRIPT_DIR/.." && pwd)"
INDEX_OUT="${HOME}/.hermes/profiles/meta/wiki/raw/adr-index.json"

mkdir -p "$(dirname "$INDEX_OUT")"

PYTHONIOENCODING=utf-8 python "$HERMES_AGENT/scripts/adr-query-poc.py" index --pretty > "$INDEX_OUT"

bytes=$(stat -c%s "$INDEX_OUT" 2>/dev/null || stat -f%z "$INDEX_OUT" 2>/dev/null || echo "?")
total=$(grep -c '"fqid":' "$INDEX_OUT" || echo "?")
collisions=$(python -c "
import json
with open(r'$INDEX_OUT', encoding='utf-8') as f:
    d = json.load(f)
print(d.get('total_collisions', '?'))
" 2>/dev/null || echo "?")

echo "✅ ADR index refreshed:"
echo "   path:        $INDEX_OUT"
echo "   bytes:       $bytes"
echo "   total ADRs:  $total"
echo "   collisions:  $collisions"
echo
echo "Skill ck-adr-query reads this file from /opt/data/profiles/meta/wiki/raw/adr-index.json"
echo "(bind-mounted to host \$HOME/.hermes/)."
