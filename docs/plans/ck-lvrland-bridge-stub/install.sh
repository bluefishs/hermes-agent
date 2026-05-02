#!/usr/bin/env bash
# CK_lvrland Bridge v0.1 — install into Hermes skill directory
# Usage: bash install.sh [hermes_skill_dir]
set -euo pipefail

TARGET="${1:-$HOME/.hermes/skills/ck-lvrland-bridge}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$TARGET"
cp "$SRC_DIR/SKILL.md" "$TARGET/"
cp "$SRC_DIR/tools.py" "$TARGET/"
cp "$SRC_DIR/tool_spec.json" "$TARGET/"

cat <<EOF

  CK_lvrland Bridge v0.1 installed to: $TARGET

  必要環境變數（加到 ~/.hermes/.env）：
    LVRLAND_BASE_URL=http://host.docker.internal:8002
    LVRLAND_API_TOKEN=                       # 留空 = LvrLand dev mode
    LVRLAND_TIMEOUT_S=30
    LVRLAND_DEFAULT_DISTRICTS=中壢區,桃園區

  驗證（hermes-agent 內）：
    hermes tools list | grep lvrland_
    hermes chat "中壢區最近房價走勢"
    hermes chat "在地圖上顯示桃園區"          # 應觸發 map_highlight tool_call

  3 tool 對應 LvrLand 已上線 endpoint：
    lvrland_health        → GET  /api/health  (detail fallback to plain)
    lvrland_query_sync    → POST /api/v1/ai/query              (Groq+Ollama RAG)
    lvrland_price_trends  → POST /api/v1/analytics/price-volume-trends

  升級：重新執行本腳本即可覆蓋。

EOF
