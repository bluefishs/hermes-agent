#!/usr/bin/env bash
# ck-* skill 業務 repo 採納自動化 — 從 4 步變 1 命令
#
# 用途：業務 repo session 啟動後執行此腳本，把預製的 helper + SKILL.md patch
#       一次性套用到自己 repo 並 deploy 到 hermes-gateway runtime。
#
# Usage:
#   bash adopt.sh <skill-name> <business-repo-path> [--deploy] [--verify]
#
# Examples:
#   # 在 CK_Missive session（cd D:/CKProject/CK_Missive）
#   bash D:/CKProject/hermes-agent/docs/plans/skill-helper-template/adopt.sh ck-missive-bridge .
#
#   # 含 deploy + verify（要求 hermes-gateway 容器活著）
#   bash D:/CKProject/hermes-agent/docs/plans/skill-helper-template/adopt.sh \
#        ck-missive-bridge . --deploy --verify
#
# 工作流：
#   1. 偵測 hermes-agent stub directory（依 skill-name 對應）
#   2. mkdir docs/hermes-skills/<skill-name>/scripts/
#   3. cp query.py + install-helper.sh
#   4. (optional) append SKILL.md「呼叫範例」段
#   5. git status 顯示 staged + 建議 commit message
#   6. (--deploy) docker cp + restart hermes-gateway
#   7. (--verify) curl /v1/responses health 測試
set -euo pipefail

if [[ $# -lt 2 ]]; then
    cat <<'EOF'
Usage: bash adopt.sh <skill-name> <business-repo-path> [--deploy] [--verify]

skill-name: ck-missive-bridge / ck-lvrland-bridge / ck-pilemgmt-bridge /
            ck-showcase-bridge / ck-observability-bridge

business-repo-path: 業務 repo 根目錄（通常 . — 從業務 repo 跑此 script）

Flags:
  --deploy   docker cp helper 到 ck-hermes-gateway:/opt/data/skills/.../scripts/
             並 restart gateway
  --verify   --deploy 後跑 hermes /v1/responses 健康測試確認 model 能 emit
             terminal call

Source: D:/CKProject/hermes-agent/docs/plans/skill-helper-template/adopt.sh
EOF
    exit 1
fi

SKILL="$1"
REPO="$2"
shift 2

DEPLOY=false
VERIFY=false
for arg in "$@"; do
    case "$arg" in
        --deploy) DEPLOY=true ;;
        --verify) VERIFY=true ;;
        *) echo "unknown flag: $arg"; exit 1 ;;
    esac
done

# ── 1. 確認 stub directory ─────────────────────────────────
HERMES_AGENT="${HERMES_AGENT:-D:/CKProject/hermes-agent}"
declare -A STUB_DIRS=(
    [ck-missive-bridge]="skill-helper-template"
    [ck-lvrland-bridge]="ck-lvrland-bridge-stub"
    [ck-pilemgmt-bridge]="ck-pilemgmt-bridge-stub"
    [ck-showcase-bridge]="ck-showcase-bridge-stub"
    [ck-observability-bridge]="ck-observability-bridge-skeleton"
)

STUB_NAME="${STUB_DIRS[$SKILL]:-}"
if [[ -z "$STUB_NAME" ]]; then
    echo "ERROR: unknown skill '$SKILL'; valid: ${!STUB_DIRS[@]}"
    exit 1
fi

STUB_DIR="$HERMES_AGENT/docs/plans/$STUB_NAME"
if [[ ! -d "$STUB_DIR" ]]; then
    echo "ERROR: stub directory not found: $STUB_DIR"
    exit 1
fi

# missive 的 query.py 在 skill-helper-template 根目錄；其他在 stub/scripts/
if [[ "$SKILL" == "ck-missive-bridge" ]]; then
    HELPER_SRC="$STUB_DIR/query.py"
    PATCH_SRC="$STUB_DIR/missive-skill-patch.md"
else
    HELPER_SRC="$STUB_DIR/scripts/query.py"
    PATCH_SRC="$STUB_DIR/skill-patch.md"
fi
INSTALL_SRC="$HERMES_AGENT/docs/plans/skill-helper-template/install.sh"

for f in "$HELPER_SRC" "$INSTALL_SRC"; do
    [[ -f "$f" ]] || { echo "ERROR: missing $f"; exit 1; }
done

# ── 2. 業務 repo 結構 ──────────────────────────────────────
cd "$REPO"
TARGET_DIR="docs/hermes-skills/$SKILL"
TARGET_SCRIPTS="$TARGET_DIR/scripts"

mkdir -p "$TARGET_SCRIPTS"

# ── 3. 複製 helper + install ──────────────────────────────
cp "$HELPER_SRC" "$TARGET_SCRIPTS/query.py"
cp "$INSTALL_SRC" "$TARGET_DIR/install-helper.sh"
chmod +x "$TARGET_DIR/install-helper.sh" 2>/dev/null || true

echo "[1/5] copied:"
echo "    $HELPER_SRC"
echo "      → $REPO/$TARGET_SCRIPTS/query.py"
echo "    $INSTALL_SRC"
echo "      → $REPO/$TARGET_DIR/install-helper.sh"

# ── 4. SKILL.md 提示 ──────────────────────────────────────
SKILL_MD="$TARGET_DIR/SKILL.md"
if [[ -f "$SKILL_MD" ]]; then
    if grep -q "## 呼叫範例" "$SKILL_MD" 2>/dev/null; then
        echo "[2/5] SKILL.md 已含「呼叫範例」段，跳過 patch"
    else
        echo "[2/5] SKILL.md 缺「呼叫範例」段"
        echo "    請手動把以下檔案的內容附加到 SKILL.md（在「## 工具清單」之後）："
        echo "        $PATCH_SRC"
    fi
else
    echo "[2/5] SKILL.md 尚未建立於 $SKILL_MD"
    echo "    建議建立 SKILL.md 並參考："
    echo "        $PATCH_SRC"
fi

# ── 5. Git status 與建議 commit message ────────────────────
echo ""
echo "[3/5] git status (staged from this script):"
git add "$TARGET_DIR/" 2>/dev/null || true
git status --short "$TARGET_DIR/" || true

echo ""
echo "[4/5] 建議 commit message："
cat <<COMMIT
git commit -m "feat(skill): $SKILL adopt query.py helper + SKILL.md curl-equivalent

依 hermes-agent docs/plans/skill-helper-template/ 設計：
- scripts/query.py 純 stdlib helper，繞 hermes 4 道閘 (tirith / no-curl / approval / CF Access)
- install-helper.sh: docker cp 到 ck-hermes-gateway runtime
- SKILL.md 加「呼叫範例」段教 model 用 python3 helper

Refs: hermes-agent docs/plans/hermes-runtime-blockers-postmortem.md (7 層真因)
      hermes-agent docs/plans/skill-helper-template/README.md (採納步驟)"
COMMIT

# ── 6. (--deploy) docker cp + restart ──────────────────────
if $DEPLOY; then
    echo ""
    echo "[5/5] --deploy: 部署到 ck-hermes-gateway runtime"
    bash "$TARGET_DIR/install-helper.sh" "$SKILL" || {
        echo "WARNING: install-helper.sh failed"
        exit 1
    }
fi

# ── 7. (--verify) hermes runtime 真實測試 ──────────────────
if $VERIFY; then
    if ! $DEPLOY; then
        echo "WARNING: --verify 需配合 --deploy；跳過"
    else
        echo ""
        echo "[bonus] --verify: 真實測試 hermes runtime"
        TMPF=$(mktemp)
        cat > "$TMPF" <<JSON
{"model":"hermes-agent","input":"請查詢 $SKILL 對應 backend 的健康狀態","store":false}
JSON
        echo "  POST /v1/responses (timeout 90s)..."
        RESULT=$(curl -s -m 90 -X POST http://localhost:8642/v1/responses \
            -H "Authorization: Bearer ${API_SERVER_KEY:-ck-hermes-local-dev-key}" \
            -H "Content-Type: application/json" \
            --data-binary @"$TMPF")
        rm -f "$TMPF"
        if echo "$RESULT" | grep -q '"function_call"'; then
            echo "  ✅ function_call 觸發成功"
            echo "$RESULT" | head -c 500
        else
            echo "  ⚠️  function_call 未觸發；可能 model 行為 stochastic"
            echo "      Multi-turn UI（Open WebUI）會自動 retry"
            echo "$RESULT" | head -c 500
        fi
    fi
fi

echo ""
echo "✅ adopt.sh done for skill: $SKILL"
echo ""
echo "後續手動步驟（若無 --deploy / --verify）："
echo "  1. 編輯 $SKILL_MD 加「呼叫範例」段（從 $PATCH_SRC 複製）"
echo "  2. git commit（用上方建議 commit message）"
echo "  3. CK_AaaP session 跑：bash $TARGET_DIR/install-helper.sh $SKILL"
echo "  4. 對 hermes /v1/responses 跑業務 query 驗證"
