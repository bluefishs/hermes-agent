#!/bin/bash
# migrate-to-ck-aaap.sh — 一鍵執行 integration-migration-plan.md Phase A
#
# 用法：
#   bash scripts/migrate-to-ck-aaap.sh dry-run     # 預覽會做什麼，不動檔
#   bash scripts/migrate-to-ck-aaap.sh execute     # 實際執行（含 git commit）
#   bash scripts/migrate-to-ck-aaap.sh verify      # 跑完後驗 11 檔目標位置
#   bash scripts/migrate-to-ck-aaap.sh rollback    # 撤銷（若上一 commit 為本 script 產出）
#
# 設計：
#   - hermes-agent session 寫此 script；**使用者執行**才實際動 CK_AaaP / CK_Missive
#   - 符合 CONVENTIONS §7 session 邊界紀律：跨 repo 的真正動作由人觸發
#   - 11 個目標檔案（11 移轉 + CK_Missive 的 missive.soul.md）
#   - 失敗 fail fast；先 dry-run 再 execute
#
# 不做：
#   - 不刪 hermes-agent 副本（Phase B/C 由 hermes-agent session 後續處理）
#   - 不 push remote（commit 後使用者自行 git push）
#   - 不改 CK_AaaP 既有 ADR (ADR-0026/0027/0028 由使用者於 CK_AaaP session 採納時建)

set -euo pipefail

CKPROJECT_ROOT="${CKPROJECT_ROOT:-D:/CKProject}"
HERMES="${CKPROJECT_ROOT}/hermes-agent"
AAAP="${CKPROJECT_ROOT}/CK_AaaP"
MISSIVE="${CKPROJECT_ROOT}/CK_Missive"

MODE="${1:-help}"

# 2026-04-25 retro-2026-04-25.md §6.1 校準：
# - 廢止 master-integration-plan-v2 移轉（PLATFORM_VISION.md 已是真相源，避免雙真相源）
# - skill source 改放 platform/services/docs/hermes-skills/（ADR-0021/0022/0023 既有規範路徑）
# - ck-loki-tail PoC 併入 ck-observability-bridge（ADR-0022 範圍更廣）
declare -a MOVES_HERMES_TO_AAAP=(
  "docs/plans/adr-0020-phase1-extension-proposal.md|docs/plans/adr-0020-phase1-extension-proposal.md"
  "docs/plans/retro-2026-04-25.md|docs/plans/retro-hermes-agent-2026-04-25.md"
  "docs/plans/skill-ck-adr-query-design.md|platform/services/docs/hermes-skills/ck-adr-query/references/design.md"
  "docs/plans/skill-ck-loki-tail-design.md|platform/services/docs/hermes-skills/ck-observability-bridge/references/loki-poc-design.md"
  "scripts/adr-query-poc.py|platform/services/docs/hermes-skills/ck-adr-query/poc/adr-query-poc.py"
  "scripts/loki-tail-poc.py|platform/services/docs/hermes-skills/ck-observability-bridge/poc/loki-tail-poc.py"
  "docs/plans/cron-prompts.md|runbooks/hermes-stack/cron-prompts.md"
  "docs/plans/crystal-seed-bootstrap.md|runbooks/crystal-seed/README.md"
  "docs/plans/soul-templates/meta.soul.md|runbooks/hermes-stack/SOUL.meta.md.template"
  "docs/plans/soul-templates/showcase.soul.md|runbooks/soul-templates/showcase.soul.md"
  "docs/plans/soul-templates/lvrland.soul.md|runbooks/soul-templates/lvrland.soul.md"
  "docs/plans/soul-templates/pile.soul.md|runbooks/soul-templates/pile.soul.md"
  "docs/plans/soul-templates/README.md|runbooks/soul-templates/README.md"
)

HERMES_TO_MISSIVE_SOUL="docs/plans/soul-templates/missive.soul.md|SOUL.md"

usage() {
  cat <<EOF
$0 <mode>

Modes:
  dry-run    Show what would be copied (no file ops)
  execute    Copy files + git commit (caller must git push afterwards)
  verify     Check that 13 target files exist in CK_AaaP + CK_Missive
  rollback   git revert HEAD (only if HEAD was made by this script)
  help       Show this message

Files moved:
  hermes-agent ──→ CK_AaaP            (12 files)
  hermes-agent ──→ CK_Missive         (1 file: SOUL.md from missive.soul.md)

Originals retained on hermes-agent for 2-week dual-write window.
Phase B (deprecation banner) + Phase C (removal) handled by hermes-agent session later.
EOF
}

ensure_dirs() {
  mkdir -p "${AAAP}/docs/plans"
  mkdir -p "${AAAP}/platform/services/docs/hermes-skills/ck-adr-query/poc"
  mkdir -p "${AAAP}/platform/services/docs/hermes-skills/ck-adr-query/references"
  mkdir -p "${AAAP}/platform/services/docs/hermes-skills/ck-observability-bridge/poc"
  mkdir -p "${AAAP}/platform/services/docs/hermes-skills/ck-observability-bridge/references"
  mkdir -p "${AAAP}/runbooks/crystal-seed"
  mkdir -p "${AAAP}/runbooks/soul-templates"
  mkdir -p "${AAAP}/runbooks/hermes-stack"
}

cmd_dry_run() {
  echo "=== Phase A dry-run preview ==="
  echo "Source root: ${HERMES}"
  echo "Target root: ${AAAP} (and ${MISSIVE} for SOUL)"
  echo
  for spec in "${MOVES_HERMES_TO_AAAP[@]}"; do
    src="${spec%|*}"
    dst="${spec#*|}"
    full_src="${HERMES}/${src}"
    full_dst="${AAAP}/${dst}"
    if [ -e "${full_src}" ]; then
      printf "  [OK]   %s  →  %s\n" "${src}" "${dst}"
    else
      printf "  [MISS] %s  (source missing)\n" "${src}"
    fi
  done
  src="${HERMES_TO_MISSIVE_SOUL%|*}"
  dst="${HERMES_TO_MISSIVE_SOUL#*|}"
  if [ -e "${HERMES}/${src}" ]; then
    printf "  [OK]   %s  →  CK_Missive/%s\n" "${src}" "${dst}"
  else
    printf "  [MISS] %s  (source missing)\n" "${src}"
  fi
  echo
  echo "Run \`$0 execute\` to apply."
}

cmd_execute() {
  echo "=== Phase A execute ==="
  ensure_dirs

  for spec in "${MOVES_HERMES_TO_AAAP[@]}"; do
    src="${spec%|*}"
    dst="${spec#*|}"
    full_src="${HERMES}/${src}"
    full_dst="${AAAP}/${dst}"
    if [ ! -e "${full_src}" ]; then
      echo "WARN: source missing — ${src}; skip"
      continue
    fi
    mkdir -p "$(dirname "${full_dst}")"
    cp -p "${full_src}" "${full_dst}"
    echo "copied: ${src} → CK_AaaP/${dst}"
  done

  # Missive SOUL — only copy if target absent (avoid overwriting existing persona)
  src="${HERMES_TO_MISSIVE_SOUL%|*}"
  dst="${HERMES_TO_MISSIVE_SOUL#*|}"
  if [ -e "${MISSIVE}/${dst}" ]; then
    echo "skip (exists): CK_Missive/${dst}; user must merge manually if desired"
  else
    cp -p "${HERMES}/${src}" "${MISSIVE}/${dst}"
    echo "copied: ${src} → CK_Missive/${dst}"
  fi

  echo
  echo "=== Commit in CK_AaaP ==="
  cd "${AAAP}"
  git add docs/ runbooks/
  git commit -m "feat(integration): import hermes-agent governance/skill artifacts (Phase A)

- docs/plans/: master plan v2, ADR-0020 Phase 1 extension proposal
- docs/hermes-skills/ck-adr-query/: design + PoC (source of truth per ADR-0018)
- docs/hermes-skills/ck-loki-tail/: design + PoC
- runbooks/hermes-stack/cron-prompts.md, SOUL.meta.md.template
- runbooks/crystal-seed/README.md (fork-able stack template)
- runbooks/soul-templates/: showcase/lvrland/pile drafts

hermes-agent originals preserved for 2-week dual-write window.
Source: hermes-agent commit \$(cd ${HERMES} && git rev-parse --short HEAD)" || \
    echo "(nothing to commit in CK_AaaP)"

  if [ -e "${MISSIVE}/SOUL.md" ] && \
     [ -z "$(cd ${MISSIVE} && git status --short SOUL.md 2>/dev/null)" ]; then
    : # already tracked, no change
  elif [ -e "${MISSIVE}/SOUL.md" ]; then
    echo
    echo "=== Commit in CK_Missive ==="
    cd "${MISSIVE}"
    git add SOUL.md
    git commit -m "feat(soul): adopt Missive agent SOUL canonical (from hermes-agent template)" || \
      echo "(nothing to commit in CK_Missive)"
  fi

  echo
  echo "=== Done ==="
  echo "Next: caller must git push in each repo:"
  echo "  cd ${AAAP} && git push"
  echo "  cd ${MISSIVE} && git push   # if SOUL added"
  echo
  echo "Then return to hermes-agent session for Phase B (deprecation banner)."
}

cmd_verify() {
  echo "=== Verifying targets ==="
  local fail=0
  for spec in "${MOVES_HERMES_TO_AAAP[@]}"; do
    dst="${spec#*|}"
    if [ -e "${AAAP}/${dst}" ]; then
      printf "  [OK]   CK_AaaP/%s\n" "${dst}"
    else
      printf "  [FAIL] CK_AaaP/%s\n" "${dst}"
      fail=$((fail + 1))
    fi
  done
  if [ -e "${MISSIVE}/SOUL.md" ]; then
    printf "  [OK]   CK_Missive/SOUL.md\n"
  else
    printf "  [FAIL] CK_Missive/SOUL.md\n"
    fail=$((fail + 1))
  fi
  echo
  if [ "${fail}" -eq 0 ]; then
    echo "All 13 target files present."
    return 0
  else
    echo "${fail} target(s) missing."
    return 1
  fi
}

cmd_rollback() {
  echo "=== Rollback (revert most recent commit in each repo) ==="
  echo "WARNING: only run if HEAD in each repo was created by this script."
  read -p "Proceed? [y/N] " ans
  if [ "${ans}" != "y" ]; then
    echo "abort."
    return 1
  fi
  cd "${AAAP}"
  git revert --no-edit HEAD || true
  if [ -e "${MISSIVE}/SOUL.md" ]; then
    cd "${MISSIVE}"
    git revert --no-edit HEAD || true
  fi
  echo "Done. Verify with \`$0 verify\` (should report missing)."
}

case "${MODE}" in
  dry-run|dry)  cmd_dry_run ;;
  execute|exec) cmd_execute ;;
  verify)       cmd_verify ;;
  rollback)     cmd_rollback ;;
  help|*)       usage ;;
esac
