# 2026-07-08 整體架構×服務流程覆盤（重啟後 live 複驗＋S3 段C 缺陷根治）

> 位置慣例：跨 repo meta 覆盤產出放 `CK_Hermes/docs/plans/`（先例：2026-06-15/07-03 同名系列）。
> 前情：7/03→7/07 整合優化弧線已收束（v2026.7.4.1），姿勢＝穩定觀察期勿動 hermes core；
> 本次為觀察期第一次例行覆盤，**發現並根治一個 S3 段C 的隱性缺陷（sidecar 缺 env）**，未動 gateway。

## 1. 系統健康快照（15:10–16:00 實測）

| 項目 | 結果 |
|---|---|
| 容器 | **55 個、0 非健康**；本機今晨約 11:10 重啟，Docker 自動全拉回 |
| health-smoke | 7/08 10:50 登入自動跑 → **OVERALL=PASS 9/9**（含 C-1c dispatch）|
| 版本 | `.env`=容器=**v2026.7.4.1**，無漂移 |
| 三 flag | `HERMES_ZH_CONVERT=s2twp` / `HERMES_V1_DISPATCH_FIX=agent_query` / `HERMES_V1_BUSINESS_FASTPATH=count` 全 live（gateway runtime env 實查）|
| ollama | 4 模型在線（qwen2.5:7b-ctx64k 主力）|
| Missive | healthy、documents **1906**（7/07=1902，+4 自然成長）、entities 38114 |
| /v1 功能探針 | 問「公文總共有幾份」→ **200 / 7.3s / `X-Hermes-Fastpath: business-count` / 回真數字 1906（收1323+發583）＝ground truth，零捏造**。7.3s 比部署時 18-35s 更快（keep-warm 生效）|
| R2 記憶引擎 | daily-closing completed:24 last ok；briefings 連續至 morning-2026-07-08.md，零斷檔 |

結論：健康面全綠，v2026.7.4 弧線的根治成果（fastpath+攔截）在重啟後持續有效。

## 2. 🎯 本次唯一實質發現：S3 段C federation collector 在 cron 情境從未成功過

### 症狀
- morning-2026-07-07.md 與 morning-2026-07-08.md 的「跨平臺意識體」段皆為 **「missive：(digest 不可達，跳過)」**。
- cron output（`cron/output/dba66619fddf/`）7/06、7/07 兩晚皆 `federation 0/1`。
- `raw/federation/` 只有一頁 `missive-2026-07-07.md`，mtime = 7/07 06:34 本地 ＝ **使用者手動 docker exec 到 gateway 容器的實證**，非 cron 產物。同一天早上 07:30 的真 cron 跑就失敗了。

### 根因（確證，非推測）
cron tick 由 **`ck-hermes-ops` sidecar 驅動（DA-2）** → awakening writer 及其 `subprocess` 呼叫的
`query.py memory_digest` 都在 **ops 容器**內執行；而 compose 的 `hermes-ops` service
**沒有掛 gateway 那份 `env_file`（`${HERMES_HOST_DIR}/.env`）**，容器內無
`MISSIVE_API_TOKEN`/`MISSIVE_BASE_URL` → query.py 直接回
`{"error":"no_token","message":"env MISSIVE_API_TOKEN required for action 'memory_digest'"}`
→ payload 非 ok → collector fail-safe 跳過（無 exception，cron output 只存 stdout 故無錯誤線索）。

在 ops 容器內重現 no_token、在 gateway 容器同刻正常，一翻兩瞪眼。
段 B（daily-closing）不受影響是因它用 **urllib 直呼 HTTPS**、不依賴 token env。

### 修復（已部署並驗證）
- `CK_AaaP/runbooks/hermes-stack/docker-compose.yml`：`hermes-ops` 加掛與 gateway 相同的
  `env_file: ${HERMES_HOST_DIR:-.}/.env`（含註記）。
- `docker compose up -d hermes-ops` 只重建 sidecar（**gateway 未動**，符合穩定觀察期）。
- 驗證：ops 容器內 `query.py memory_digest` → **`ok:true`（坤哥、as_of 2026-07-08T16:00+08）**；
  sidecar 重啟後 DA-5 re-warm 正常。
- **最終驗證點＝今晚 cron 自然跑**：明晨（本地 ~07:30）確認
  `morning-2026-07-09.md` 跨平臺段含坤哥摘要 + `raw/federation/missive-2026-07-09.md` 存在（cron 情境首次真成功）。

### 教訓（「隔離正常≠嵌入正常」第三例，新變體：容器環境差異型）
1. 前兩例是「subprocess 嵌入 gateway 進程失效」；本例是 **「docker exec 到 A 容器驗證，實際執行在 B 容器」**。
   凡 cron 消費端驗收，必須在 **cron 實際執行的容器與身分**（ck-hermes-ops、uid 10000、其 env）下驗，
   手動 exec 到 gateway 不算實證。
2. cron output 檔只落 stdout，collector 的 stderr 失敗訊息全數丟失 → 排障只能靠重現。見 §4 建議 R-3。

## 3. 次要觀測（不阻斷）

- **digest 端點偶發 502**（Cloudflare→origin 暫態；修復驗證過程中兩容器同刻皆 502、數分鐘後自癒，origin 本地 /health 全程 200）。collector/fetch 皆無 retry，單次 502 就丟掉當晚 digest。
- **cron 時區澄清**：jobs 的 expr 是 **UTC**——daily-closing `0 15 * * *` UTC＝**23:00 本地**、awakening `30 23 * * *` UTC＝**翌日 07:30 本地**（晨間 briefing 在早上產出，語意正確）。CLAUDE.md 舊述「15:00 daily+23:30 federation」實為 UTC，勿誤讀成本地時刻。
- 7/05 23:52 health-smoke 曾一次 `C-1c dispatch=WARN`，7 分鐘後複跑 PASS（暫態，無 pattern）。

## 4. 整體建議與規劃

### 辦理結果（R-2~R-5、R-7 於 2026-07-08 同日辦畢；R-6 為外部工單）

- ✅ **R-1** hermes-ops 補 env_file 並重建 sidecar（段C 根治）。
- ✅ **R-2 段C cron 真跑驗收（提前達成）**：以 `hermes cron run dba66619fddf` 觸發、由 **ops sidecar** tick 於 09:03:08 UTC 執行（60s 內、非 Windows 任務 5min 邊界＝確為先前必失敗的容器）→ **`federation 1/1`**、`morning-2026-07-08.md` 跨平臺段含坤哥摘要（1906 份/38114 實體）、`raw/federation/missive-2026-07-08.md` 由 cron 寫入。**S3 三段「cron 全自主」成立**；明晨 07:30 自然跑為追加確證。
- ✅ **R-3 失敗儀器化（採 b 案，不動 fork）**：`collect_federation` 兩失敗分支（非 ok payload〔曾靜默吞 no_token 兩晚的那支〕與 exception）都把原因寫進 briefing 平臺行（`(digest 不可達：<原因>，跳過)`）與 **stdout**（cron output 只保 stdout）；`daily-closing` 的 `fetch_missive_digest` 同步去 fail-silent（no token/非 HTTPS/請求失敗皆印原因）。
- ✅ **R-4 digest retry**：collector subprocess 與 closing fetch 各加 1 次重試（間隔 30s），治偶發 CF 502 丟整晚 digest。兩 copy 同步（repo＋volume chown 10000、容器內 py_compile 過）。
- ✅ **R-5 health-smoke 增 C-3c federation**：驗最新晨間 briefing 含 `raw/federation/` 連結（ASCII 標記避 CJK 跨 PowerShell 失真）；WARN 級不阻斷、指引看 R-3 儀器化輸出。實跑 **10/10 全 PASS**（含 C-1b/C-1c 完整版）。RESTART_CHECKLIST 同步 9→10 檢查＋C-3c 處置行。
- ⏭️ **R-6 聯邦擴充**（維持外部工單）：lvrland/pile 依 ADR-CK-003 §6 比照坤哥開 digest 端點後，`FEDERATION_PLATFORMS` 各加一行即接入（屬各域 session）。
- ✅ **R-7 時區文件校正**：meta-memory-engine README 補「cron expr 為 UTC」對照與**雙 ticker env 等價**教訓（新增 cron script env 依賴時 gateway/ops 兩容器都要有）。

### 完善波 2（2026-07-08 晚間，同日續辦）
- ✅ **DA-7 sidecar env 守衛**（`ops-sidecar.sh`）：啟動即檢查 `MISSIVE_API_TOKEN`/`MISSIVE_BASE_URL`，缺失 loud log（stdout→Loki 可收）——讓「compose 改動靜默丟 env」同型缺失在部署當下可見。正向（env 在、無 WARN）與負向（env -u 模擬缺失、守衛觸發）雙向驗證過；sidecar 已重啟套用。
- ✅ **C-3d 兩 copy 漂移哨兵**（health-smoke 第 11 檢查）：比對 repo 版控副本 vs volume 執行副本（cron 真跑 volume 那份）md5（去 `\r` 正規化防 autocrlf 假陽性），任一 writer 漂移即 WARN 並指引「docker cp repo→volume，勿反向」。實跑 PASS。治本專案反覆家族「改錯檔/兩 copy 未同源」。
- ✅ **今晚 daily-closing 自然跑實戰確證**：15:00:36 UTC（36 秒偏移＝ops ticker 執行）→ `digest ok`、daily 頁含坤哥摘要（40114 實體）——修復後環境＋新版 writer 的第一次無人工自然成功。
- ✅ **fastpath 觀測例行讀數**（容器生命週期內）：`fastpath served=2`、`backfilled=0`、`fall-through=0`＝無文字化洩漏、無捏造回填需求，攔截網閒置健康。
- 剩餘追蹤僅時間門檻項：明晨 07:30 awakening 自然跑（B-S3-OBS 連 3 夜確證起點）。
- **雙 ticker 競速解釋了 7/07 的不對稱**：daily-closing（整點 :00）被 Windows 任務（exec 到 gateway、有 token）搶到故有 digest；awakening 兩晚被 60s 的 ops ticker 搶到故失敗。env 等價化後競速不再影響結果。
- `daily-closing` 的 fetch 其實也依賴 `MISSIVE_API_TOKEN`（無 token 直接 None）——修復前它能成功純屬 ticker 競速運氣，本次一併去 fail-silent。

### 姿勢維持
- 穩定觀察期原則不變：gateway/hermes core 本次零變更；下一最高 CP 前進點仍＝聯邦內容深化（R2 有互動才有摘要）與 R-6 擴充，非再動 hermes。

## 5. 本次變更清單

| Repo | 變更 | 狀態 |
|---|---|---|
| CK_AaaP | `runbooks/hermes-stack/docker-compose.yml` hermes-ops 加 env_file | 已部署（sidecar 已重建）|
| CK_Hermes | 本覆盤文件 | 新增 |
| 運行系統 | ck-hermes-ops 重建（gateway/web/webui/ollama 未動）| 完成 |
