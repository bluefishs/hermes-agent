# 2026-07-03 整體架構 × 服務流程覆盤（重啟後 live 複驗）

> 承 6/17「整合優化（免費基礎）」。距上次覆盤約 16 天。今早本機重啟（約 10:35），
> Docker 自動恢復，`CK-Hermes-Health-Smoke` 登入任務於 10:50 自動跑重啟後驗證 → **OVERALL=PASS**。
> 本次結論：**系統健康、韌性機制實證生效、無 config 漂移；唯一實質前進點仍是業務查詢架構分流（WS-D）**。

---

## 一、Live 複驗實況（2026-07-03 上午）

| 面向 | 實測 | 判定 |
|---|---|---|
| 容器 | **53 容器全 healthy**（`Up 15 minutes` ＝重啟後 Docker 自動拉回，無 exited/unhealthy）| ✅ |
| NVIDIA hook | `G-1 nvidia-hook=PASS` — **6/16 PM 的 prestart hook 崩潰 P0 事故本次未重演**（WSL2 toolkit re-init 後穩定）| ✅ |
| health-smoke 哨兵 | `[2026-07-03 10:50:26] OVERALL=PASS`，8+1 檢查全綠（含 `C-1b v1-chat=PASS`）＝**重啟後自動驗證設計完全生效** | ✅ |
| ck-hermes-ops sidecar | 重啟後 `round=5/10/15` 連續 `DA-6 smoke OK: gateway=200 ollama=200` + `DA-5 re-warmed qwen`（60s tick）| ✅ |
| 版本 | gateway/web/ops 三容器 = `ckproject/hermes-agent:v2026.5.22`，`active_profile=meta`，**無漂移** | ✅ |
| ollama | 4 模型在線（qwen2.5:7b-ctx64k / qwen2.5:7b / gemma4:e2b / nomic-embed-text 768D）| ✅ |
| Missive ground truth | `/health` → **documents 1895**（6/17 是 1854，自然成長 +41）、canonical_entities 34123 | ✅ |
| Windows 任務 | `CK-Hermes-Cron-Tick` + `CK-Hermes-Health-Smoke` 皆 `Ready`（重啟存活）| ✅ |

### 功能層探針（healthcheck ≠ functional，本專案血淚教訓）

**A. /v1 meta chat（真對話，帶 API_SERVER_KEY）**
- HTTP **200**、繁體中文、R1 s2twp live、延遲 **~30s**（較先前 ~175s **大幅改善**，keep-warm 讓 qwen 常駐熱態、免 240s 冷啟動）
- ⚠️ **但捏造業務數字**：問「公文幾份」→ 回「`1234` 份（後端本次未回傳明確統計數字）」；ground truth 為 1895。弱模型在後端未回數字時自行編造。

**B. query.py 直呼後端（可靠路徑）**
- `ok:true / success:true`、**1,895 筆**（收文 1,317 + 發文 578）、`tools_used:[get_statistics]`、18s、model gemma4
- **與 ground truth 完全一致、零捏造、繁中**

### 🎯 決定性對比（再次坐實架構論點）

| 路徑 | 「公文幾份」結果 | 正確性 | 延遲 |
|---|---|---|---|
| **query.py 直呼後端** | 1,895（分佈正確）| ✅ 零捏造 | 18s |
| **/v1 meta LLM 迴圈** | 「1234」| ❌ 捏造 | 30s |

→ **業務查詢走 meta LLM 迴圈不可靠（模型捏造），直呼後端 100% 正確**。WS-D「架構分流繞過迴圈」的論點第 N 次被實測證實。這是免費基礎下唯一有實質改善空間的槓桿。

---

## 二、自 6/17 以來的重要 delta（多數尚未反映於 CLAUDE.md）

1. **✅ ck-hermes-ops sidecar 已部署並納入 compose stack**（重大韌性成熟）
   - 定義於 `CK_AaaP/runbooks/hermes-stack/docker-compose.yml` 的 `hermes-ops` service（label `com.ck.version:v0.11.0`、entrypoint `/ops-sidecar.sh`）
   - 內建 **DA-5 keep-warm**（每 tick re-warm qwen）+ **DA-6 functional smoke**（每 5 tick 驗 gateway=200/ollama=200）
   - 意義：keep-warm 與 smoke 從 6/17 的**脆弱 Windows 任務/腳本**升級為 **compose 常駐 sidecar**，隨 stack 起停、版控化、跨重啟自動存活。
   - 對照 6/17 CLAUDE.md「DA-1 已 commit 但尚未 build/deploy、keep-warm 在 tick-driver.ps1」→ 現實已前進：**DA-5/DA-6 容器化落地**（DA-1 見下）。

2. **✅ 重啟韌性經多次實證**：health-smoke.log 顯示 6/16、6/17（×3）、6/22、7/03 皆 OVERALL=PASS（6/17 09:20 有一次 v1-chat CRITICAL、10:11 已自癒 PASS）→ 自動恢復 + 哨兵 + keep-warm 三件套**跨多次重啟穩定**。

3. **✅ R2 記憶引擎全自主、零斷檔**（相比 6/15 凍結〔停 5/2〕是根本性復原）
   - `daily-closing-v5`（15:00）：`last_status:ok`、`completed:19`、`next_run 2026-07-03T15:00`
   - `daily-awakening`（23:30）+ curator 記憶策展（6/29 REPORT）
   - cron/output 實檔：兩 job 從 6/26 到 7/02 **每日連續產出、無 gap**
   - ⚠️ 但內容稀薄：最新 daily-closing 註記「**0 log entries this day**」＝機制活著但**無真實互動日誌可摘**（閒置系統的預期現象，非故障）。

4. **業務量成長**：documents 1847（6/15）→ 1854（6/17）→ **1895（7/03）**。

5. **⚠️ DA-1（R1 opencc 烤入 image）仍未部署**
   - 系統 python3 無 opencc module；R1 靠 runtime 注入 venv（`/opt/hermes/.venv` 有 opencc 1.3.1 + `/opt/hermes/gateway/zh_convert.py`）
   - `C-2 r1-zh=PASS` ＝ runtime patch 存活 restart（`unless-stopped` 保留容器層）
   - **∴「重啟仍勿 `--force-recreate`」指引依然成立**（force-recreate 會把容器重置回 image、丟失 R1）。

---

## 三、整體性建議與規劃

> 前提維持 6/17 使用者決策：**維持免費基礎**（不付費模型 / 不升 GPU / 深度記憶模型強度牆 D-δ 不投入）。
> 力氣放「免費整合層完善」。以下依 CP 值排序。

### P0（最高 CP，免費、治真痛點）— 業務查詢架構分流 WS-D 甲
- **痛點**：本次再證 /v1 meta 迴圈對業務查詢會捏造數字（1234 vs 1895）。這是使用者面對的**唯一實質可見缺陷**（延遲已靠 keep-warm 改善、繁簡已 live、對話已通）。
- **方案**（已有設計契約 `docs/plans/ws-d-business-query-fastpath-design.md`）：在 **AaaP Chat caller 側**加窄業務分類器，把「計數/統計/查詢」類問題**直呼 Missive 後端**（query.py 路徑 100%/18s），不進 meta LLM 迴圈；非業務對話仍走 meta。
- **落點**：CK_AaaP session（caller 側 + 定址 ADR-CK-003 §4，**不需 fork hermes**）。
- **零成本**、根治捏造、順帶砍延遲。**建議列為下一個實作 sprint 的唯一 P0**。

### P1 — DA-1：R1 opencc 烤入 image，解除 --force-recreate 禁令 ✅ **已於同日執行完成**
- 現況（執行前）：R1 靠 runtime patch，`--force-recreate`/image pull 會丟失 → 運維上是**長期地雷**（任何 stack 重建都可能靜默丟繁簡）。
- 動作：build `CK_AaaP/runbooks/hermes-stack` 的 hermes image（commit `944442458` 把 opencc 烤入 Dockerfile）→ 部署後 R1 永久化 → **移除「勿 --force-recreate」限制**。
- **執行結果（見下方「附二：版本更新執行紀錄」）**：v2026.5.22 → v2026.7.3，opencc 1.4.0 烤入、R1 永久化、8+1 全綠、禁令解除。

### P2 — 韌性層冗餘釐清（簡化，非新增）
- 現有三重保活：①compose `hermes-ops` sidecar（連續 keep-warm+smoke）②Windows `CK-Hermes-Cron-Tick`（5min tick 順帶 re-warm）③Windows `CK-Hermes-Health-Smoke`（登入/排程跑完整 §C+§C-G 審計）。
- ①②在 keep-warm 上**功能重疊**。sidecar 落地後，②的 re-warm 職責可退役（保留 cron tick 驅動 R2 即可），減少維運面。③（完整審計 + 寫 log）與 ①（連續輕量 smoke）互補，**兩者都保留**。
- 落點：本機設定微調，低風險。

### P3 — R2 記憶內容價值化（觀察，勿過度投入）
- daily-closing「0 log entries」揭示：記憶引擎**跑得動但沒東西可記**（無人與 meta 深度互動）。
- 這與 6/16 定論一致：**跨 session 記憶綜合弱的瓶頸在模型強度（D-δ）與互動量，非管路**。免費基礎下**勿再投 prompt 層 recall 強化**（6/16 D-α/D-β 實測負向已還原）。
- 若未來要讓記憶有料，槓桿是「餵入業務事件流」（如把 R2 cron 接 Missive 每日 digest）——但這**依賴 CK_Missive 開 `POST /api/ai/memory/digest`**（S3 段 A，長期 405 阻斷，WO-2）。屬跨 repo 協調，非本機可解。

### 維持不動
- config 與現實一致（qwen 主模型 / ck-ollama base_url / meta profile），本次**不動任何 config**。
- SOUL 人格良好，勿改（6/16 D-α/D-β 已證 prompt 層強化負向）。

---

## 四、重啟準備狀態（維持綠燈）
- 8+1 PASS 基線、git working tree clean、兩 Windows 任務 Ready、sidecar 隨 compose 存活。
- **重啟後 SOP 不變**：看 `docs/plans/meta-memory-engine/health-smoke.log` 末行（PASS 即可；`G-1 nvidia-hook` 紅 → `wsl --shutdown` 重啟 Docker 引擎，**勿 `docker restart ck-ollama`**）。
- **仍勿 `--force-recreate`**（R1 runtime patch，待 DA-1 部署後解除）。

---

## 附二：版本更新執行紀錄（v2026.5.22 → v2026.7.3，同日 DA-1 部署）

使用者於覆盤後指示「線上更新 hermes 版本」→ 走 **Build DA-1 新版並部署**（唯一「前進版本又不丟 R1」的路徑）。

**版本抉擇**：本機另有現成 `v2026.5.25`（比 5.22 多 1 skill commit）但**建於 DA-1 前、不含 opencc**，切過去會丟 R1 → 否決。改從 **current HEAD `6ba1c370f`** build（含 R1 gateway 源碼 `22586ef0a` + DA-1 Dockerfile `944442458`）。

**執行步驟**（依 `CK_AaaP/runbooks/hermes-stack/upgrade-hermes-agent.md` ADR-0028）：
1. 備份 `.env` → `.env.bak.20260703-pre-v2026.7.3`
2. `.env`：`HERMES_AGENT_VERSION=v2026.7.3`、`HERMES_AGENT_GIT_SHA=6ba1c370f`（`HERMES_ZH_CONVERT` 無需設，compose 已預設 `s2twp`）
3. `docker compose build hermes-web`（先 build 不動運行容器）→ `opencc==1.4.0` 烤入、`hermes-agent==0.13.0`、image `v2026.7.3` 產出
4. `docker compose up -d`（recreate web/gateway/ops；open-webui 未變）→ gateway Healthy
5. `.env.example` 同步、`git tag v2026.7.3`（本地）

**驗收全綠**：
- 3 容器 `v2026.7.3` healthy
- **DA-1 核心**：全新 recreate 容器**未跑任何 runtime patch**，venv `import opencc` 1.4.0 即在 → 證明來自 image；`zh_convert.is_enabled=True`、`active_mode=s2twp`、實轉「软件质量→軟體質量」正確
- /v1 meta chat 200 繁中（CK meta 人格）、ops sidecar DA-6 smoke gateway=200/ollama=200
- **health-smoke 8+1 全 PASS**（`C-2 r1-zh=is_enabled True`）
- 舊 image `v2026.5.22` 保留

**成果**：R1 繁簡後處理**永久化**（不再依賴 runtime patch）→ **「勿 `--force-recreate`」長期禁令解除**，運維自由度恢復。
**Rollback**（若未來需要，< 2min）：`.env` 改回 `v2026.5.22`+SHA `7bc58275` → `docker compose up -d`（不 build，舊 image 仍在）。

---

## 附三：新版 Hermes agent（0.13.0）功能盤點 + 導入優化評估

覆盤後檢視 hermes-agent 0.13.0 有哪些功能/服務值得導入以提升平台效益（Explore agent 深掘，聚焦免費基礎 + 平台痛點）。

**版本現況**：fork 落後上游 NousResearch **5864 commits**（分岔久遠），本地領先 69（CK 客製）。全量 re-sync 是大工程、非現在該做（走 `upstream-sync-cadence.md` 節奏）。上游新東西多為 openviking memory API / computer-use / vision 修復，非急迫。

**Top 3 最高平台效益導入候選**：

| # | 候選 | 潛力 | 狀態 |
|---|---|---|---|
| 1 | `platform_toolsets:{api_server:[...]}` 裁剪 /v1 工具集 | 高 | ✅ **本次已執行**（見下）|
| 2 | `session_search_tool`（FTS5 跨 session 召回）| 高 | 工具**已載入** /v1，差在 meta 主動呼叫（行為/prompt 層，非 config）|
| 3 | api_server 後處理攔截業務查詢（WS-D 落點）| 中高 | ✅ **已實作上線**（v2026.7.3.1，見附四）|

**關鍵框架事實（0.13.0 實查）**：
- `/v1` 每請求重建 AIAgent（`api_server.py:906`）= 延遲根因（架構性）。
- 框架有完整 hook 事件系統（`gateway/hooks.py`，`command:*` 支援 deny/handled/rewrite），**但 `api_server.py` 對 hook emit=0**→ **/v1 天生繞過 hook**（歷史結論在 0.13.0 仍成立）。∴ 痛點①的攔截只能走 CK 已用的 zh_convert 後處理注入點（`api_server.py:1290/1435`），與 ADR-CK-005 ③ 收斂一致。
- 30 個 provider plugin + reasoning/thinking-mode 內建（DeepSeek/xai/ollama-cloud…）、fallback chain 就緒→**換 provider 純 config**，但免費基礎下實際可行僅本地/`ollama-cloud` 換更強 tool-use 模型（reasoning 多付費）。
- `clarify_tool` 可讓弱模型「缺數字時反問而非捏造」，但 /v1 OpenAI-compat 反問語意不自然。
- `/v1/responses`（stateful）、`delegate`（子 agent 限縮 toolset）為架構性選項。

### 已執行優化（本次）

**優化 A — /v1 工具集裁剪**（候選 #1，`profiles/meta/config.yaml` 加 `platform_toolsets.api_server`）
- 移除純文字業務問答用不到的 `browser`（10 子工具）+`vision`+`image_gen`（6/4 覆盤點名的 /v1 未用三工具）；13→10 toolset。
- 效益：dispatch 少 12 個干擾工具→qwen 更易選對、prompt 縮小、**零能力損失**（保留 terminal/skills/memory/session_search 等 meta 核心）、可逆。
- 持久性：改在 `/opt/data` volume（**跨 restart+recreate 存活**，優於 R1 曾經的 image-layer patch）；備份 `config.yaml.bak.20260703-pre-toolset-trim`。**版控待補**（目前為 runtime volume 態、非 git；建議納 CK_AaaP hermes-stack 持久化如 DA 工單）。
- 實測：/v1 200、業務查詢 dispatch **意圖正確**（選對 query.py，未捏造假數字），但出現**文字化 tool_call**（見下）。

**優化 B — ADR REGISTRY 重生**（修 pre-push gate 一項 RED）：`python CK_AaaP/scripts/generate-adr-registry.py`。

### 🎯 下一 P0 定案：候選 #3 = 業務查詢後處理攔截（治本捏造/文字化 tool_call）

本次 /v1 業務查詢實測回覆：
```
terminal("/opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "...")
```
qwen **選對工具但寫成文字沒執行**（殘留②文字化 tool_call）。這與裁剪前「捏造 1234」同屬 dispatch 不可靠（模型保真度牆），**唯一治本 = 在 `api_server.py` 後處理層偵測文字化 tool_call → 真執行 query.py → 回填正確結果**（model-agnostic、不受 TPM、不靠模型保真度，與 WS-D 甲 / ADR-CK-005 ③ 一致）。

## 附四：候選 #3 已實作上線（v2026.7.3.1，治文字化 tool_call）✅

依 GO 完成 TDD 實作並上線。`gateway/dispatch_intercept.py`（信號式偵測 + HTTP-direct run_query + 串流 guard）接入 api_server `:1290`（非串流）+ 串流 emit/finish；feature flag `HERMES_V1_DISPATCH_FIX=agent_query`（compose 預設 on、空值即時回滾）。**實證攔截生效**：3/3 live 業務查詢回真答案「1898 筆（收文1318+發文580）」零文字化 call，gateway log 見 `backfilled business query`（攔截確證）。47 TDD 測試 + health-smoke 8+1 綠。**兩個實戰教訓**（詳見 `ws-d-v1-postprocess-dispatch-design.md` §9）：①偵測須信號式（弱模型文字化格式多樣，`terminal(`前綴只中一種）②run_query 須 in-process HTTPS（subprocess 在 gateway sandbox 回 None，fresh exec 卻正常＝隔離單元正常≠嵌入正常）。**界限**：只治失敗模式 B（文字化 call），純捏造數字（模式 A）不在範圍。

---

## 附一：本次探針指令備忘（跨 Git Bash 陷阱）
- docker exec 走容器內 venv python：`export MSYS_NO_PATHCONV=1` 避免 `/opt/...` 被 Git Bash 轉成 `C:/Program Files/Git/opt/...`
- /v1 探針需 `Authorization: Bearer $API_SERVER_KEY`、model=`meta`（缺 key 回 401）
- query.py 需 `MISSIVE_API_TOKEN`（host 無、gateway 容器內有）→ 於容器內 `/opt/data/skills/ck-missive-bridge/scripts` 跑
- Missive ground truth：`ck_missive_backend:8001/health` → `documents`
