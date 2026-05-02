#!/usr/bin/env bash
# Hermes — 感受優勢自診斷 + 互動 demo
#
# 目的：回答「Hermes agents 優勢到底如何感受」
# 用法：
#   bash docs/plans/hermes-feel-the-power.sh diagnose   # 純診斷，不發 query
#   bash docs/plans/hermes-feel-the-power.sh demo       # 跑 3 個 demo query（需 API_SERVER_KEY）
#   bash docs/plans/hermes-feel-the-power.sh upgrade    # 顯示「進 L2」具體 SOP
#
# 設計：
#   - L1 單域：等同 Claude API 直呼，無顯著優勢
#   - L2 跨域聯邦：一句話跨 N bridge 並行，這才是 Hermes 賣點
#   - L3 時間累積：SOUL + wiki 萃取，需 1–2 月

set -uo pipefail

GATEWAY="${HERMES_GATEWAY:-http://localhost:8642}"
API_KEY="${API_SERVER_KEY:-}"

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────
# diagnose — gateway health + skill 清單 + missing report
# ─────────────────────────────────────────────────────────
diagnose() {
    echo -e "${BLUE}═══ Hermes 自診斷（$(date +%Y-%m-%d\ %H:%M)）═══${NC}"
    echo ""

    # 1. Gateway health
    echo "[1/4] Gateway 健康度："
    if curl -s --max-time 3 "$GATEWAY/health" | grep -q '"status": "ok"'; then
        echo -e "  ${GREEN}✓ ck-hermes-gateway:8642 運行中${NC}"
    else
        echo -e "  ${RED}✗ gateway 不可達（請先 docker compose up）${NC}"
        return 1
    fi

    # 2. Container status
    echo ""
    echo "[2/4] 容器狀態："
    docker ps --filter "name=ck-hermes" --format "  {{.Names}}: {{.Status}}" 2>/dev/null || \
        echo "  （docker 不可用，跳過）"

    # 3. Runtime 已裝 CK skill
    echo ""
    echo "[3/4] Runtime CK skills（從容器內讀）："
    if installed=$(MSYS_NO_PATHCONV=1 docker exec ck-hermes-gateway ls /opt/data/skills/ 2>/dev/null | grep '^ck-'); then
        echo "$installed" | sed 's/^/  ✓ /'
    else
        echo "  （無 ck-*-bridge skill 部署）"
    fi

    # 4. 應有但缺的 CK skill
    echo ""
    echo "[4/4] 缺漏的 CK bridge skill："
    EXPECTED=("ck-missive-bridge" "ck-observability-bridge" "ck-showcase-bridge" "ck-pilemgmt-bridge" "ck-lvrland-bridge" "ck-adr-query")
    INSTALLED=$(MSYS_NO_PATHCONV=1 docker exec ck-hermes-gateway ls /opt/data/skills/ 2>/dev/null | grep '^ck-' || true)
    MISSING=()
    for s in "${EXPECTED[@]}"; do
        if ! echo "$INSTALLED" | grep -q "^$s$"; then
            MISSING+=("$s")
        fi
    done
    if [[ ${#MISSING[@]} -eq 0 ]]; then
        echo -e "  ${GREEN}✓ 全部 ${#EXPECTED[@]} 個 CK skill 都已部署${NC}"
        echo -e "  ${GREEN}你已在 L2（跨域聯邦）— 試試 demo${NC}"
    else
        echo -e "  ${YELLOW}⚠ 缺 ${#MISSING[@]} 個 skill：${NC}"
        for s in "${MISSING[@]}"; do
            echo "    ✗ $s"
        done
        echo ""
        echo -e "  ${YELLOW}你在 L1（單域）— 跨域查詢無效${NC}"
        echo -e "  ${YELLOW}進 L2 需執行：bash $0 upgrade${NC}"
    fi

    # 5. SOUL 狀態
    echo ""
    echo "[bonus] SOUL 人格："
    SOUL_HEAD=$(MSYS_NO_PATHCONV=1 docker exec ck-hermes-gateway head -3 /opt/data/SOUL.md 2>/dev/null | tail -1)
    case "$SOUL_HEAD" in
        *"Hermes Meta"*|*"共同大腦"*)
            echo -e "  ${GREEN}✓ Semiont-like Meta 觀察者人格已激活${NC}"
            ;;
        *"CK 數位助理"*|*"工程顧問"*)
            echo -e "  ${YELLOW}⚠ 仍是過渡 CK 助理（C.1 報告推薦升級為 meta.soul.md）${NC}"
            ;;
        *"坤哥"*|*"Missive 意識體"*)
            echo -e "  ${RED}✗ 錯位：Missive Muse 人格在通用 runtime（C.1 Step 1 待執行）${NC}"
            ;;
        *)
            echo "  （無法判定，head: $SOUL_HEAD）"
            ;;
    esac
    echo ""
}

# ─────────────────────────────────────────────────────────
# demo — 跑 3 個 query 對比
# ─────────────────────────────────────────────────────────
demo() {
    if [[ -z "$API_KEY" ]]; then
        echo -e "${RED}需設 API_SERVER_KEY env：${NC}"
        echo "  export API_SERVER_KEY=\$(cat ~/.hermes/secrets/api_server_key.txt 2>/dev/null \\"
        echo "                          || cat D:/CKProject/CK_AaaP/runbooks/hermes-stack/secrets/api_server_key.txt)"
        echo "  bash $0 demo"
        return 1
    fi

    echo -e "${BLUE}═══ Hermes Demo — 感受優勢實測 ═══${NC}"
    echo ""

    # Query 1：L1 單域
    echo -e "${BLUE}[Demo 1/3] L1 單域查詢（與直接呼 Claude API 等同）${NC}"
    echo "  Q: \"今天 Missive 系統健康嗎\""
    _query "今天 Missive 系統健康嗎"
    echo ""

    # Query 2：L2 跨域
    echo -e "${BLUE}[Demo 2/3] L2 跨域聯邦（Hermes 真正賣點）${NC}"
    echo "  Q: \"Missive、PileMgmt、LvrLand 三系統當前健康度，並列\""
    _query "Missive、PileMgmt、LvrLand 三系統當前健康度，並列"
    echo "  ※ 沒 Hermes：你必須開 3 個 UI / curl 3 個 endpoint"
    echo "  ※ 有 Hermes：一句話並行呼叫 3 個 bridge skill"
    echo ""

    # Query 3：治理 + 跨域
    echo -e "${BLUE}[Demo 3/3] 複合查詢（治理 + 業務）${NC}"
    echo "  Q: \"列當前所有 in-flight 90 天以上的 ADR；同時看 Missive 上週新增的公文數\""
    _query "列當前所有 in-flight 90 天以上的 ADR；同時看 Missive 上週新增的公文數"
    echo "  ※ 此 query 需 ck-adr-query + ck-missive-bridge 兩個 skill 同時可用"
    echo ""

    echo -e "${GREEN}═══ Demo 結束 ═══${NC}"
    echo "如果 Demo 2/3 回應「我無法跨域查詢」或只回了 Missive，"
    echo "代表你還在 L1 — 跑 'bash $0 upgrade' 看升級 SOP。"
}

_query() {
    local q="$1"
    local resp
    resp=$(curl -s --max-time 30 -X POST "$GATEWAY/v1/chat/completions" \
        -H "Authorization: Bearer $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"hermes-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"$q\"}],\"temperature\":0.3}" \
        2>&1)
    echo "$resp" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    if 'error' in d:
        print('  ✗ Error:', d['error'].get('message', d['error']))
    else:
        c = d.get('choices', [{}])[0].get('message', {}).get('content', '')
        for line in c.split('\n')[:10]:
            print('  >', line)
        if len(c.split('\n')) > 10:
            print('  > ... (truncated)')
except Exception as e:
    print('  ✗ Parse error:', e)
    print('  raw:', sys.stdin.read()[:200] if False else '<consumed>')
" 2>&1
}

# ─────────────────────────────────────────────────────────
# upgrade — 印「進 L2」具體 SOP
# ─────────────────────────────────────────────────────────
upgrade() {
    cat <<'EOF'

═══ 進 L2（跨域聯邦）SOP — 預估 15 分鐘 ═══

本 session（hermes-agent）已備齊所有素材；剩下 CK_AaaP session 的整合：

┌────────────────────────────────────────────────────────────┐
│ Step A — CK_AaaP session 採納 4 bridge skill 到 runtime    │
└────────────────────────────────────────────────────────────┘

cd D:/CKProject/CK_AaaP

# A.1 採納 4 個 bridge skill source（observability/showcase/pilemgmt 已有；補 lvrland）
mkdir -p platform/services/docs/hermes-skills/ck-lvrland-bridge
cp ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/{SKILL.md,tool_spec.json,README.md,install.sh,tools.py} \
   platform/services/docs/hermes-skills/ck-lvrland-bridge/

# A.2 部署到 runtime（hermes_data volume 內 /opt/data/skills/）
HERMES_DATA="$(docker volume inspect ck_hermes_data -f '{{.Mountpoint}}')"
for skill in ck-observability-bridge ck-showcase-bridge ck-pilemgmt-bridge ck-lvrland-bridge ck-adr-query; do
    docker cp platform/services/docs/hermes-skills/$skill ck-hermes-gateway:/opt/data/skills/
done

# A.3 解註 config.yaml 的 skills.enabled 4 行
docker exec ck-hermes-gateway sh -c "
sed -i 's/# - ck-showcase-bridge/  - ck-showcase-bridge/' /opt/data/config.yaml
sed -i 's/# - ck-observability-bridge/  - ck-observability-bridge/' /opt/data/config.yaml
sed -i 's/# - ck-pilemgmt-bridge/  - ck-pilemgmt-bridge/' /opt/data/config.yaml
"
# 同時加 ck-lvrland-bridge + ck-adr-query 到 enabled

# A.4 重啟（破舊 prompt cache，下次對話才 fresh）
docker compose -f runbooks/hermes-stack/docker-compose.yml restart hermes-gateway

┌────────────────────────────────────────────────────────────┐
│ Step B — SOUL 升級（C.1 選項 1 精準版）                    │
└────────────────────────────────────────────────────────────┘

bash ../hermes-agent/docs/plans/unblock-soul-c1.sh step1

# 切回 hermes-agent session：
bash docs/plans/unblock-soul-c1.sh step2

┌────────────────────────────────────────────────────────────┐
│ Step C — 驗收（你親自感受 L2）                              │
└────────────────────────────────────────────────────────────┘

# 1. 重跑診斷確認 5/5 skill 全裝
bash docs/plans/hermes-feel-the-power.sh diagnose

# 2. 開 Open WebUI（http://localhost:3000）問一句：
#    "Missive 健康嗎、PileMgmt celery 在跑什麼、LvrLand 中壢區房價走勢、列 in-flight ADR"
#    Hermes 應並行呼叫 4 個 bridge，整合回應

# 3. 或 CLI：
bash docs/plans/hermes-feel-the-power.sh demo

═══════════════════════════════════════════════════════════════

EOF
}

# ─────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────
case "${1:-}" in
    diagnose) diagnose ;;
    demo)     demo ;;
    upgrade)  upgrade ;;
    *)
        echo "Usage: $0 {diagnose|demo|upgrade}"
        echo ""
        echo "  diagnose  自診斷（gateway / 容器 / skill / SOUL 狀態）"
        echo "  demo      跑 3 個對比 query（需 API_SERVER_KEY）"
        echo "  upgrade   顯示「L1 → L2」整合 SOP"
        echo ""
        echo "建議流程："
        echo "  1. bash $0 diagnose       看自己在 L1 還是 L2"
        echo "  2. bash $0 upgrade        如果 L1，照 SOP 升級"
        echo "  3. bash $0 demo           升級後實測感受"
        exit 1 ;;
esac
