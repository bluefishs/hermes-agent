#!/usr/bin/env bash
# ck-* skill helper installer — 部署 query.py 到 hermes-gateway runtime
#
# Usage:
#   bash install.sh <skill-name>
#
# Example:
#   bash install.sh ck-missive-bridge
#
# 預期：在 ck-hermes-gateway container 內 /opt/data/skills/<skill-name>/scripts/
#       建立 query.py，讓 model emit terminal call 跑此 helper 取得 backend 資料。
#
# 此腳本由 hermes-agent session 維護；業務 repo 採納時可複製到自己的 install.sh。
set -euo pipefail

SKILL_NAME="${1:-}"
if [[ -z "$SKILL_NAME" ]]; then
    echo "usage: bash $0 <skill-name>"
    echo "  example: bash $0 ck-missive-bridge"
    exit 1
fi

CONTAINER="${HERMES_CONTAINER:-ck-hermes-gateway}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HELPER_SRC="$SCRIPT_DIR/query.py"
TARGET_DIR="/opt/data/skills/$SKILL_NAME/scripts"
TARGET_FILE="$TARGET_DIR/query.py"

if [[ ! -f "$HELPER_SRC" ]]; then
    echo "ERROR: $HELPER_SRC not found"
    exit 1
fi

if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER}$"; then
    echo "ERROR: container $CONTAINER not running"
    exit 1
fi

echo "[1/4] mkdir -p $TARGET_DIR (in $CONTAINER)"
docker exec "$CONTAINER" sh -c "mkdir -p $TARGET_DIR"

echo "[2/4] docker cp $HELPER_SRC -> $CONTAINER:$TARGET_FILE"
docker cp "$HELPER_SRC" "$CONTAINER:$TARGET_FILE"

echo "[3/4] verify deploy"
SIZE=$(docker exec "$CONTAINER" sh -c "wc -c < $TARGET_FILE" | tr -d '\r ')
echo "   deployed: $SIZE bytes"

echo "[4/4] smoke test (health action)"
docker exec "$CONTAINER" sh -c "python3 $TARGET_FILE health" || {
    echo "WARNING: smoke test failed; check env vars in compose"
    exit 1
}

echo ""
echo "✅ helper deployed for skill: $SKILL_NAME"
echo ""
echo "下一步："
echo "  1. 業務 repo 把 SKILL.md 加上「呼叫範例」段（教 model 用本 helper）"
echo "     範本見：D:/CKProject/hermes-agent/docs/plans/skill-helper-template/README.md"
echo ""
echo "  2. 從 hermes runtime 真實測試："
echo "     curl -m 180 -X POST http://localhost:8642/v1/responses \\"
echo "       -H 'Authorization: Bearer ck-hermes-local-dev-key' \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"model\":\"hermes-agent\",\"input\":\"請查詢 backend 健康狀態\",\"store\":false}'"
echo ""
echo "  3. 注意：本 deploy 在 container restart 後會消失"
echo "     若要持久化：CK_AaaP session 把 query.py 加入 hermes-stack docker-compose 的 volume mount"
echo "     或將業務 repo 的 SKILL.md + scripts/ 一併 git tracked，docker compose cp 自動同步"
