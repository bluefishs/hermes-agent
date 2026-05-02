#!/usr/bin/env bash
# Phase 1.5 Step 2 — Hermes profile 啟用一鍵 script
#
# 把「hermes profile use <name> + docker compose restart hermes-gateway +
# 健康檢查 + 真實 baseline 對照測試」打包為 1 命令。
#
# 設計：
# - 預設 dry-run：先顯示要做什麼，不實際執行
# - --apply：真的執行（會中斷現有 hermes-gateway 用戶 ~30s）
# - --rollback：切回 default profile + restart
#
# Usage:
#   bash phase15-activate.sh <profile> [--apply] [--rollback]
#
# Examples:
#   bash phase15-activate.sh missive             # dry-run，看會做什麼
#   bash phase15-activate.sh missive --apply     # 真的啟用 missive profile
#   bash phase15-activate.sh missive --rollback  # 切回 default
#
# 前置：
# - ~/.hermes/profiles/<profile>/ 已存在（per phase2-profile-isolation-design）
# - ck-hermes-gateway container 在跑
# - hermes-stack docker-compose.yml 路徑已知
set -euo pipefail

PROFILE="${1:-}"
MODE="${2:-dry-run}"

if [[ -z "$PROFILE" ]]; then
    cat <<'EOF'
Usage: bash phase15-activate.sh <profile> [--apply | --rollback]

Available profiles (預製於 ~/.hermes/profiles/):
  meta             — Semiont 觀察者（default，當前 active）
  missive          — Missive Muse 公文/案件助手 ⭐ 推薦 pilot
  lvrland          — LvrLand 房價/估價助手（待 CF Tunnel #12）
  pile             — PileMgmt 樁位/Celery 助手（待 CF Tunnel #13）
  showcase         — Showcase 治理 API 助手（待 CF Tunnel #13）
  observability    — Loki/Prom/Grafana/Alertmanager（待 CF Tunnel #13）

Modes:
  (default) dry-run — 顯示會做什麼，不實際執行
  --apply           — 真的執行 (會中斷 hermes-gateway ~30s)
  --rollback        — 切回 meta（default）profile + restart

Source: D:/CKProject/hermes-agent/docs/plans/skill-helper-template/phase15-activate.sh
EOF
    exit 1
fi

PROFILE_DIR="$HOME/.hermes/profiles/$PROFILE"
HERMES_STACK_DIR="${HERMES_STACK_DIR:-D:/CKProject/CK_AaaP/runbooks/hermes-stack}"
COMPOSE_FILE="$HERMES_STACK_DIR/docker-compose.yml"
CONTAINER="${HERMES_CONTAINER:-ck-hermes-gateway}"

# ── Validate ─────────────────────────────────────────────
echo "═══ Phase 1.5 Step 2 — activate hermes profile: $PROFILE ═══"
echo ""

case "$MODE" in
    --apply|--rollback|dry-run) ;;
    *) echo "ERROR: unknown mode '$MODE'; use --apply, --rollback, or omit for dry-run"; exit 1 ;;
esac

if [[ "$MODE" == "--rollback" ]]; then
    PROFILE="meta"
    PROFILE_DIR="$HOME/.hermes/profiles/$PROFILE"
    echo "→ rollback mode: profile = meta"
    echo ""
fi

if [[ ! -d "$PROFILE_DIR" ]]; then
    echo "ERROR: profile dir $PROFILE_DIR not found"
    echo "  Run: ls $HOME/.hermes/profiles/"
    echo "  若 missing → 跑 hermes-agent docs/plans/phase2-profile-isolation-design.md SOP"
    exit 1
fi

echo "[check] profile dir exists: $PROFILE_DIR"
[[ -f "$PROFILE_DIR/SOUL.md" ]] && echo "  ✅ SOUL.md ($(wc -c < "$PROFILE_DIR/SOUL.md") bytes)"
[[ -f "$PROFILE_DIR/config.yaml" ]] && echo "  ✅ config.yaml"
[[ -d "$PROFILE_DIR/skills" ]] && echo "  ✅ skills/ ($(ls "$PROFILE_DIR/skills" | wc -l) entries)"

# ── Plan ─────────────────────────────────────────────────
echo ""
echo "[plan] 將執行以下操作："
cat <<EOF
  1. echo "$PROFILE" > ~/.hermes/active_profile  (host marker)
  2. docker compose -f $COMPOSE_FILE \\
       exec hermes-gateway sh -c 'cp -r /opt/data/profiles/$PROFILE/. /opt/data/.staging/'
     (將 profile 內容覆蓋到 runtime SOUL/config/skills)
  3. docker compose -f $COMPOSE_FILE restart hermes-gateway
     (約 30s downtime)
  4. 等待 health endpoint 200
  5. 跑 demo query 驗證 prompt token / tool-call 觸發率
EOF

# ── Dry-run early exit ──────────────────────────────────
if [[ "$MODE" == "dry-run" ]]; then
    echo ""
    echo "✅ dry-run completed; pass --apply to execute"
    exit 0
fi

# ── Apply ────────────────────────────────────────────────
echo ""
echo "[apply] 執行中..."
read -p "  ⚠️  這會中斷 hermes-gateway ~30s。確認執行？(y/N) " confirm
if [[ "$confirm" != "y" ]]; then
    echo "  cancelled by user"
    exit 0
fi

# Step 1: host marker
echo "[1/5] mark active_profile"
echo "$PROFILE" > "$HOME/.hermes/active_profile"
echo "  ✅ ~/.hermes/active_profile = $PROFILE"

# Step 2: copy profile content into runtime (runtime SOUL.md / config.yaml / skills override)
# 注意：hermes runtime 預設讀 /opt/data/* 不是 /opt/data/profiles/$PROFILE/*
#       所以需把 profile 內容 mirror 到 runtime root
echo "[2/5] mirror profile content to runtime root"
docker exec "$CONTAINER" sh -c "
    cp /opt/data/profiles/$PROFILE/SOUL.md /opt/data/SOUL.md.activate-backup-\$(date +%Y%m%d-%H%M%S) 2>/dev/null || true
    cp /opt/data/profiles/$PROFILE/SOUL.md /opt/data/SOUL.md
    cp /opt/data/profiles/$PROFILE/config.yaml /opt/data/config.yaml.activate-backup-\$(date +%Y%m%d-%H%M%S) 2>/dev/null || true
    cp /opt/data/profiles/$PROFILE/config.yaml /opt/data/config.yaml
    echo '  copied SOUL + config'
"

# Step 3: restart
echo "[3/5] restart hermes-gateway"
if [[ -f "$COMPOSE_FILE" ]]; then
    docker compose -f "$COMPOSE_FILE" restart hermes-gateway
else
    docker restart "$CONTAINER"
fi

# Step 4: wait for health
echo "[4/5] wait for health endpoint"
for i in $(seq 1 30); do
    if curl -s -m 3 http://localhost:8642/health 2>/dev/null | grep -q '"status": "ok"'; then
        echo "  ✅ healthy after ${i}s"
        break
    fi
    sleep 1
    [[ $i -eq 30 ]] && { echo "  ❌ timeout waiting for health"; exit 1; }
done

# Step 5: verify demo query
echo "[5/5] verify with demo query"
TMPF=$(mktemp)
cat > "$TMPF" <<EOF
{"model":"hermes-agent","input":"hi","store":false,"max_output_tokens":50}
EOF
RESULT=$(curl -s -m 60 -X POST http://localhost:8642/v1/responses \
    -H "Authorization: Bearer ${API_SERVER_KEY:-ck-hermes-local-dev-key}" \
    -H "Content-Type: application/json" \
    --data-binary @"$TMPF")
rm -f "$TMPF"
PROMPT_TOKENS=$(echo "$RESULT" | python -c "import sys,json; print(json.load(sys.stdin).get('usage',{}).get('input_tokens', 'N/A'))" 2>/dev/null || echo "parse_err")
echo "  prompt_tokens = $PROMPT_TOKENS"
echo ""
echo "  meta profile baseline: 13016 tokens"
echo "  $PROFILE profile expected: ~5000–6000 tokens (only 1 SKILL.md loaded)"
echo "  若顯著降低 → profile isolation 工作 ✅"

echo ""
echo "✅ Phase 1.5 Step 2 done; profile = $PROFILE"
echo ""
echo "後續驗收（用戶手動）："
echo "  1. 開 hermes-web :9119 互動，觀察人格是否改變"
echo "  2. 跑 5 次業務 query，看 tool-call 觸發率（vs meta baseline ~70%）"
echo "  3. 觀察簡體中文混入比例（vs meta baseline ~30%）"
echo "  4. 若不滿意 → 跑 bash phase15-activate.sh meta --apply 回滾"
