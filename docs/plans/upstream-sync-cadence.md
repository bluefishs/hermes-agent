# Upstream sync cadence — hermes-agent fork

> Status：adopted 2026-04-18（替換 P1 原定月度）
> Owner：@bluefishs
> 起因：從 `16f9d020`（base）到 `v2026.4.16`（upstream）累積 **665 commits behind**，跨 5 個 release — CJK 修正、Opus 4.7 migration、gateway bug fix 等影響 daily driver 的關鍵補丁未吸收。月度節奏太稀疏。

## 節奏：per-release-tag

每次 upstream 發新 tag（形如 `v2026.W.D`，約週一版）— **7 天內** 同步到本地 fork。

執行頻率：**每週一上午** 跑一次檢查；若偵測到新 tag 且本地未追上，當日執行 sync。

## 檢查指令（~30 秒）

```bash
cd D:/CKProject/hermes-agent

# 1. 抓新 tag
git fetch origin --tags

# 2. 比對本地 main 離最新 release 有多少 commits
LATEST_TAG=$(git tag --list 'v2026.*' --sort=-creatordate | head -1)
LOCAL_BASE=$(git rev-list --tags='v2026.*' --simplify-by-decoration HEAD | head -1)
echo "upstream latest: $LATEST_TAG"
git log --oneline "$LOCAL_BASE..$LATEST_TAG" | wc -l  # commits 落差

# 3. 若 > 0，執行 sync 流程（下節）
```

## Sync 流程（per-release）

1. **Safety branch** — `git branch backup/pre-rebase-$(date +%Y-%m-%d) main`
2. **Stash 任何未提交改動**（LF 硬化、本地筆記）
3. **Rebase** 本地 patch 到新 tag：

   ```bash
   git fetch origin --tags
   git rebase --onto <new-tag-commit> <old-base-commit> main
   ```

4. **驗證 patch 仍必要** — `git diff HEAD~1 HEAD -- <patch-files>`；若 upstream 已合我們的 PR，移除對應 workaround commit
5. **Pop stash** + `git add --renormalize .`（讓 `.gitattributes` 生效）
6. **Smoke test**：
   - Docker build success
   - `docker run ... dashboard` → `/health` = 200
   - `/` 返回 HTML + `/assets/index-<hash>.js` = 200
   - 選項：容器內跑 `pytest tests/ -q`（upstream 要求但非強制）
7. **Push** — 僅 push 到 `fork/main`（**不**推回 `origin`）
8. **Record** — 於 `memory/project_upstream_sync_YYYY-MM-DD.md` 留 snapshot

## 衝突處理

- **單 patch 衝突**：手動 resolve，commit message 保留 `Co-authored-by`
- **多 patch 衝突**：考慮 drop 已過時的 patch（重作 feature check）；不要機械性保留舊 workaround
- **Dockerfile 相關**：注意 upstream 可能改 layer 順序，我們的 web build 插入位置要重確認在 whatsapp-bridge 之後、`chown` 之前

## 不要做

- 不要 squash upstream commits — bisect 失能
- 不要一次跳過多個 release — 累積衝突面積變大
- 不要把多個本地 patch 合成一個 commit — 送 upstream PR 時需單一主題

## Escalation

若連續 2 週找不到時間執行：

1. 改為雙週節奏但**強制** sprint 排入
2. 或考慮用 GitHub Action + CronCreate 自動跑 rebase + PR（需驗證 upstream CI 可通過）

## 追蹤指標

- 兩次 sync 之間的最大 commit gap（目標 ≤ 50）
- upstream PR 回覆延遲（目標 ≤ 7 天注意，≤ 30 天合併或 close）
- smoke test 失敗率（目標 ≤ 10%）
