# Upstream Sync Plan — v2026.4.16 → v2026.4.23

> **狀態**：ready-to-execute（等使用者授權 rebase 動作）
> **產生**：2026-04-25 04:00 Taipei
> **規範**：`docs/plans/upstream-sync-cadence.md`
> **風險**：中（rebase 改 history；safety branch 已備）

## 1. 版本差異摘要

| 項 | 值 |
|---|---|
| 本地 HEAD | `a423464f` (docs: upstream sync cadence) |
| 本地 base | `1dd6b5d5` (= v2026.4.16, release v0.10.0) |
| Upstream latest | `v2026.4.23` = `bf196a3f` (release v0.11.0) |
| Local patches atop base | 3 commits |
| Upstream delta `v2026.4.16..v2026.4.23` | 1219 commits（含多 merge chain） |

## 2. Local patches 清單

```
1dd6b5d5 (v2026.4.16) release v0.10.0  ← base
8a96d2c5 fix: build web/ dashboard assets in Docker image
064e4dc5 chore: enforce LF line endings for container entrypoints
a423464f docs: upstream sync cadence, feature eval, and PR draft
(HEAD, fork/main)
```

所有 patch 已 push 至 `fork/main`。Safety branch: `backup/pre-rebase-2026-04-25`。

## 3. 對 CK 高價值的 upstream 補丁（必收）

| Commit | 為何重要 |
|---|---|
| `a884f6d5 fix(skills): follow symlinked category dirs consistently` | **Phase 2 SOUL/skill symlink 必要**（目前不穩） |
| `51c1d2de fix(profiles): stage profile imports to prevent directory clobbering` | Profile 隔離安全（Master Plan v2 D8） |
| `0086fd89 feat(cron): support enabled_toolsets per job` | daily-closing cron 可減 token 開銷 |
| `8b79acb8 feat(cron): expose enabled_toolsets in cronjob tool` | 同上，使用者介面暴露 |
| `22afa066 fix(cron): guard against non-dict result from run_conversation` | cron 穩定性（我們踩過 qwen2.5 non-dict 問題） |
| `9d147f7f fix(gateway): queue mode support in message handling` | Gateway 穩定 |
| `d0821b05 / 5651a733 / b7bdf32d / d72985b7 fix(gateway)` | session lock 修復（多條） |

## 4. 中價值補丁（順便受益）

- `78d1e252 fix(web_server): guard GATEWAY_HEALTH_TIMEOUT against invalid env values`
- `692ae6dd docs(readme)` — 文件刷新
- `d42b6a2e docs(agents): refresh AGENTS.md`

## 5. 低價值 / 不影響 CK

- `fix(gateway/discord): ...` × 2 — 我們未用 Discord
- `feat(dashboard): reskin / themes` × 3 — 我們走 Open WebUI
- `feat(xai): xAI image generation` — 違反零付費硬約束

## 6. 預期衝突點

| Path | 衝突來源 | 對策 |
|---|---|---|
| `pyproject.toml` | 本地未改 version；upstream 會從 `v0.10.0 → v0.11.0` | 接受 upstream |
| `Dockerfile` | 我們 `8a96d2c5` 插 web build；upstream 可能 refactor layer | 手動 resolve，保留 web build 區塊於 whatsapp-bridge 後、chown 前 |
| `.gitattributes` | 我們 `064e4dc5` 加 LF 硬化；upstream 若動同檔需合併 | 保留我們的規則 |
| `docs/plans/*` | 純本地；無衝突 | — |

## 7. Rebase 執行指令（需授權）

```bash
cd D:/CKProject/hermes-agent

# 0. 確認 clean tree
git status  # 應該 clean or only stash-able

# 1. Fetch（已完成）
git fetch origin --tags

# 2. Stash 任何未提交改動
git stash push -m "pre-rebase-2026-04-25" --include-untracked

# 3. Rebase 三個 local patch onto v2026.4.23
git rebase --onto v2026.4.23 1dd6b5d5 main

# 若有衝突：逐 commit resolve → git add → git rebase --continue

# 4. Pop stash（若有）
git stash pop

# 5. 驗 patches 仍必要（特別是 web build — upstream 可能已收）
git log --oneline v2026.4.23..HEAD
git diff v2026.4.23..HEAD -- Dockerfile .gitattributes

# 6. Renormalize line endings
git add --renormalize .
git commit -m "chore: renormalize line endings post-rebase" || true

# 7. Smoke test
docker compose build hermes-gateway
docker compose up -d hermes-gateway
curl -f http://localhost:8642/health
curl -f http://localhost:9119/

# 8. Push（只推 fork，不推 origin）
git push fork main --force-with-lease

# 9. Log
echo "2026-04-25 HH:MM SYNC v2026.4.16 → v2026.4.23（1219 commits）patches: 3 kept" \
  >> ~/.hermes/profiles/meta/wiki/log.md
```

## 8. 驗收條件

- [ ] `git log --oneline | head -5` 顯示三個 patch 在 v2026.4.23 之上
- [ ] Docker image build 成功
- [ ] `/health` = 200
- [ ] `/` 返回 HTML + JS asset 200
- [ ] `hermes skill list` 含 `llm-wiki`
- [ ] 本地 wiki（`~/.hermes/profiles/meta/wiki/`）未動
- [ ] 新 cron 可建立 `enabled_toolsets: [llm-wiki]` 測試（可選）

## 9. 回滾計畫

若 rebase 後嚴重壞：

```bash
git reset --hard backup/pre-rebase-2026-04-25
git push fork main --force-with-lease  # 回滾到前狀態
# 或保留 fork remote 不動，本地 reset 即可（fork 已有備份分支）
```

## 10. 不要做

- ❌ Squash upstream commits — bisect 失能
- ❌ 機械性保留舊 patch — 若 `fix(docker): web build` 已被 upstream 吸收，`drop` 該 patch
- ❌ Rebase 期間同時改 SOUL.md 或 wiki/ — 讓 rebase 乾淨
- ❌ Push 到 `origin/main`（我們是 fork，不是 upstream maintainer）

## 11. Cross-ref

- Cadence 規範：`docs/plans/upstream-sync-cadence.md`
- Feature eval：`docs/plans/upstream-feature-eval-2026-04-18.md`（/steer / execute_code project / Tool Gateway）
- Master Plan v2 Phase 1 依賴：`docs/plans/master-integration-plan-v2-2026-04-19.md`
- Heartbeat commit cycle 備註：rebase 成功後的 commit message 建議用 `chore(sync): v2026.4.16 → v2026.4.23` 簡單型（非 heartbeat 五段式，因為是機械性同步）
