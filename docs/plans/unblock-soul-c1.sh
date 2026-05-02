#!/usr/bin/env bash
# SOUL C.1 治理 — 一鍵解鎖腳本
#
# 來源：docs/plans/c1-soul-status-2026-04-28.md「選項 1 精準版」
# 設計原則：「各專案 = Muse / hermes = taiwan.md (Semiont)」
#
# 動作：
#   Step 1（CK_AaaP session）：
#     - 把「坤哥」(Missive Muse) 從 hermes-stack 搬回 CK_Missive
#     - 套 meta.soul.md 為 hermes-stack runtime SOUL（Semiont 觀察者）
#     - 加 frontmatter（type/version/sync_targets/last_modified_at）
#     - 兩 repo 各自 commit
#   Step 2（hermes-agent session）：
#     - 激活 host meta wiki SOUL
#     - sync 到兩個容器
#     - 重啟確保 prompt cache 重建
#
# 使用方式：
#   # 從 CK_AaaP session 跑
#   bash D:/CKProject/hermes-agent/docs/plans/unblock-soul-c1.sh step1
#   # 切換到 hermes-agent session 跑
#   bash D:/CKProject/hermes-agent/docs/plans/unblock-soul-c1.sh step2
#   # 或一次跑（同 session 跑兩段，需確認 git config 兩 repo 都對）
#   bash D:/CKProject/hermes-agent/docs/plans/unblock-soul-c1.sh all

set -euo pipefail

CK_ROOT="D:/CKProject"
AAAP_DIR="$CK_ROOT/CK_AaaP"
HERMES_DIR="$CK_ROOT/hermes-agent"
MISSIVE_DIR="$CK_ROOT/CK_Missive"
HERMES_STACK="$AAAP_DIR/runbooks/hermes-stack"
META_TEMPLATE="$HERMES_DIR/docs/plans/soul-templates/meta.soul.md"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/meta}"

step1() {
  echo "─────────────────────────────────────────────────────────"
  echo "  SOUL C.1 Step 1 — CK_AaaP session（搬檔 + 套草稿）"
  echo "─────────────────────────────────────────────────────────"

  cd "$AAAP_DIR"

  # 1.1 把「坤哥」搬回 Missive 領地（Muse-like Missive Agent）
  if [[ -f "$HERMES_STACK/SOUL.md" ]]; then
    echo "[1.1] mv $HERMES_STACK/SOUL.md → $MISSIVE_DIR/SOUL.md"
    mv "$HERMES_STACK/SOUL.md" "$MISSIVE_DIR/SOUL.md"
  else
    echo "[1.1] hermes-stack/SOUL.md 已不存在（跳過搬檔，可能已執行過）"
  fi

  # 1.2 套用 meta.soul.md
  echo "[1.2] cp meta.soul.md → hermes-stack/SOUL.md"
  cp "$META_TEMPLATE" "$HERMES_STACK/SOUL.md"

  # 1.3 補 frontmatter
  echo "[1.3] 加 frontmatter 到 hermes-stack/SOUL.md"
  TODAY=$(date +%Y-%m-%d)
  TMP_FILE=$(mktemp)
  cat > "$TMP_FILE" <<FRONTMATTER
---
title: Hermes Meta — 共同大腦
type: soul
version: 1.0.0
last_modified_by: human
last_modified_at: $TODAY
source_of_truth: true
sync_targets:
  - ck-hermes-gateway:/opt/data/SOUL.md
  - ck-hermes-web:/opt/data/SOUL.md
tags: [agent, identity, persona, meta, hermes, semiont]
---

FRONTMATTER
  cat "$HERMES_STACK/SOUL.md" >> "$TMP_FILE"
  mv "$TMP_FILE" "$HERMES_STACK/SOUL.md"

  # 1.4 commit CK_AaaP
  echo "[1.4] commit CK_AaaP"
  cd "$AAAP_DIR"
  git add runbooks/hermes-stack/SOUL.md
  git commit -m "feat(soul): apply meta.soul.md to hermes-stack runtime (per C.1 option 1)

依設計原則「各專案 = Muse / hermes = taiwan.md (Semiont)」，hermes-stack runtime
應為 Semiont-like Meta（觀察者），原 SOUL.md（坤哥 — Missive 意識體）搬回 CK_Missive。

Refs: docs/plans/c1-soul-status-2026-04-28.md (hermes-agent session)"

  # 1.5 commit CK_Missive
  echo "[1.5] commit CK_Missive"
  cd "$MISSIVE_DIR"
  git add SOUL.md
  git commit -m "feat(soul): adopt 坤哥 Muse persona as Missive agent identity

從 CK_AaaP/runbooks/hermes-stack/SOUL.md 搬入；對齊「各專案 = Muse」設計原則。
Missive bridge skill 後續以此 SOUL 為人格定義。

Refs: hermes-agent docs/plans/c1-soul-status-2026-04-28.md"

  echo ""
  echo "  ✅ Step 1 完成"
  echo "  下一步：切到 hermes-agent session 跑 step2"
  echo ""
}

step2() {
  echo "─────────────────────────────────────────────────────────"
  echo "  SOUL C.1 Step 2 — hermes-agent session（激活 + sync）"
  echo "─────────────────────────────────────────────────────────"

  cd "$HERMES_DIR"

  # 2.1 激活 host meta wiki SOUL
  echo "[2.1] cp meta.soul.md → $HERMES_HOME/SOUL.md"
  mkdir -p "$HERMES_HOME"
  cp "$META_TEMPLATE" "$HERMES_HOME/SOUL.md"

  # 2.2 dry-run 確認
  echo "[2.2] dry-run sync_soul.py"
  python -m hermes_cli.sync_soul

  # 2.3 推進兩個容器
  echo ""
  echo "[2.3] apply sync_soul.py（推送至 ck-hermes-gateway + ck-hermes-web）"
  read -p "確認推送至 runtime 容器？(y/N) " confirm
  if [[ "$confirm" != "y" ]]; then
    echo "  跳過 apply，保持 dry-run 狀態"
    return 0
  fi
  python -m hermes_cli.sync_soul --apply

  # 2.4 重啟容器
  echo "[2.4] restart hermes-gateway + hermes-web (prompt cache 重建)"
  docker compose -f "$HERMES_STACK/docker-compose.yml" \
    restart hermes-gateway hermes-web

  # 2.5 驗收
  echo ""
  echo "[2.5] 驗收"
  echo "  - 預期 ck-hermes-gateway:/opt/data/SOUL.md 首行為「# Hermes Meta — 共同大腦與導師」"
  docker exec ck-hermes-gateway sh -c 'head -3 /opt/data/SOUL.md' || true

  echo ""
  echo "  ✅ Step 2 完成"
  echo ""
  echo "  後續工作（手動）："
  echo "    1. Open WebUI 對話，自介應為 Hermes Meta（觀察者口吻）"
  echo "    2. cd CK_Missive && node scripts/checks/shadow-baseline-report.cjs（baseline 重跑）"
  echo "    3. 更新 MEMORY.md SOUL Templates 段落"
  echo ""
}

main() {
  case "${1:-}" in
    step1) step1 ;;
    step2) step2 ;;
    all)   step1 && echo "" && step2 ;;
    *)
      echo "Usage: $0 {step1|step2|all}"
      echo ""
      echo "  step1   CK_AaaP session 搬檔 + frontmatter + commit"
      echo "  step2   hermes-agent session 激活 host SOUL + sync 容器"
      echo "  all     兩段同 session 跑（需 git config 對兩 repo 都正確）"
      exit 1
      ;;
  esac
}

main "$@"
