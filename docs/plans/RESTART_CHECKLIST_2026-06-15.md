# 電腦重啟前/後 Checklist（Delta）— 2026-06-15

> 觸發：6/15 整體覆盤 + 聚焦 chat 深化交流。接續 [`RESTART_CHECKLIST_2026-06-09.md`](RESTART_CHECKLIST_2026-06-09.md)。
> 完整復原程序仍沿用 [`RESTART_CHECKLIST_2026-05-25.md`](RESTART_CHECKLIST_2026-05-25.md)。
> 安全準則不變：不 `compose down` / 不 `force-recreate` / 不 `prune` / 不碰 DB / 不刪 volume·image。

---

## 🔴 A. 重啟後**第一優先**驗證 — meta profile 權限（新增，環境性可能再犯）

**背景**：6/15 發現 `/v1` meta 對話入口回 HTTP 500（`Permission denied .../profiles/meta/.env`），根因＝**meta profile 目錄被翻成 `root:root 700`、gateway(hermes uid 10000) 鎖在門外**（研判 host 端 Windows bind mount 權限重置，**環境性、重啟可能再犯**）。詳見 [`2026-06-15-meta-chat-restore.md`](2026-06-15-meta-chat-restore.md)。

**重啟後必驗（兩步，缺一不可）**：
```bash
# 1. 結構：meta 目錄須為 hermes 擁有（被硬化成 700 沒關係，只要 owner=hermes）
docker exec ck-hermes-gateway ls -lad /opt/data/profiles/meta
#   期望 owner = hermes；若為 root → 立即修：
docker exec ck-hermes-gateway sh -c 'chown 10000:10000 /opt/data/profiles/*'

# 2. Functional（單看 healthcheck/dispatch 探針不夠 — 它們繞過 gateway！）：
docker exec ck-hermes-gateway sh -c 'KEY=$(printenv API_SERVER_KEY); curl -s -m 240 -o /dev/null -w "%{http_code}\n" http://localhost:8642/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d "{\"model\":\"meta\",\"messages\":[{\"role\":\"user\",\"content\":\"嗨\"}]}"'
#   期望 200；若 500 → 回步驟 1 chown
```
⚠️ **教訓**：baseline `query.py` 探針走 root `docker exec` 直跑、**繞過 gateway profile 載入**，即使 chat 入口壞掉它仍 GO → **單探針 GO ≠ chat 可用**。重啟後務必跑上面的 `/v1` functional 驗證。

## B. 今日（6/15）持久變更

1. **🔧 production 變更（live，唯一）**：`chown 10000:10000 /opt/data/profiles/*`（解 meta 鎖死 + 防全 profile 同類 bug）。**無 config/SOUL/容器變更**；meta config=qwen baseline 未動。
2. **文件（repo working tree）**：新增 `docs/plans/{2026-06-15-integration-review,2026-06-15-meta-chat-restore}.md` + 本 checklist；更新 `2026-06-12-cross-repo-integration-workorder.md`（WO-1 降 P1）。
3. **上層 `D:\CKProject\CLAUDE.md`**：6/15 banner（覆盤 + chat 修復 + 計數回歸消退）。
4. **Memory**：新增 `project_meta_chat_restore_deepening` + 更新 `project_hermes_baseline_go_nogo_20260530` + MEMORY.md 索引。

## C. 今日結論（重啟後應維持）

- ✅ **/v1 meta chat 已修復**（500→200，durable=chown hermes）。**重啟後依 §A 復驗**。
- ✅ **baseline GO**：計數題 3/3 回 1847（=ground truth，無捏造）；6/12 計數回歸消退。
- ✅ **版本無漂移**：gateway/web/.env 全 v2026.5.22；51 容器全 healthy。
- 🟡 **深化交流殘留**：R1 簡體洩漏（建議 gateway 加 OpenCC 後處理）／R2 記憶引擎凍結（daily cron 停 5/2、排程器未重載，需獨立修+納版控）／R3 延遲 39-87s 架構性。

## D. 持久化建議（落 CK_AaaP / hermes-stack）

- entrypoint 啟動時對 **所有 `profiles/*`** 強制 `chown hermes:hermes`（現「top-level 已 hermes 就跳過遞迴」最佳化會漏修子目錄）→ 使重啟自動自癒、免人工 §A 修。
- **R2 tick 驅動 sidecar**：hermes-stack 加一個每 1-5 分鐘跑 `hermes cron tick` 的 sidecar（gateway 內建排程器在 Docker 不 tick）→ meta 記憶引擎全自動。

## D2. R2 記憶引擎重啟後復原（cron 凍結時）

```bash
cd CK_Hermes/docs/plans/meta-memory-engine && bash setup-cron.sh   # 佈 writer 到 profile + 冪等註冊兩 cron + chown
# 驗證（強制跑一次）：
docker exec -e HERMES_HOME=/opt/data -u 10000:10000 ck-hermes-gateway /opt/hermes/.venv/bin/hermes cron list   # 應見 daily-closing-v5 / daily-awakening-v2 active
# 啟用週期驅動：見 meta-memory-engine/tick-driver.sh（sidecar 或 Windows 工作排程器）
```
詳見 [`meta-memory-engine/README.md`](meta-memory-engine/README.md)（四層根因 + 復原）。

## E. 已知狀態（非阻斷，同 6/9）

- dispatch ~70%（/v1 in-loop，WS-D 分流為解）；Telegram token 失效（暫緩）；Missive 後端偶暫態降級（CK_Missive runtime）；S3 digest POST 405（WO-2 待開）。
