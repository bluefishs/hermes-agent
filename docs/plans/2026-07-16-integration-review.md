# 2026-07-16 整體架構 × 服務流程覆盤（重啟後 live 複驗 + B-S3-OBS 三夜確證結案）

> 承 `2026-07-08-integration-review.md`（§4 完善波2）、`2026-07-07-integration-closeout.md`、`RESTART_CHECKLIST_2026-07-07.md`。
> 本輪＝重啟後 live 複驗 + B-S3-OBS 觀察期收束判定。

## 0. TL;DR

- **本機今晨約 06:26 重啟**，56 容器全 `Up ~2h`、**0 非健康、0 exited**（Docker 自動拉回）；`CK-Hermes-Health-Smoke` 登入 08:26 自動跑 → SOP 再次零人工全自癒。
- **health-smoke 12 檢查 11 PASS / 1 WARN**：唯一 `C-3c federation=WARN`，**根因＝7/15 23:30 awakening 撞 Missive digest 端點 CF 502**（已知 R-4 暫態，retry×1 未擋住），其餘 11 檢查全 PASS。
- **✅ B-S3-OBS 三夜確證決定性結案**：federation raw 頁 **7/09 首夜（awakening）+ 7/10–7/14 連 5 夜 = 連 6 夜自然跑成功**，遠超「連 3 夜」門檻；唯 7/15 單夜暫態 miss（fail-safe、loud log 已寫明）。
- **R2 記憶引擎全自主零斷檔**：兩 cron `last_status=ok`、`completed 32/33`、daily/morning briefing **7/10–7/16 每日連續**；daily-closing digest 健康（7/15 daily 頁含坤哥摘要）。
- **內容持續增厚（非稀薄）**：坤哥 07/08–07/15 成長摘要＝公文 **1933** 份（7/08 是 1904）、知識實體 **48551**（期間新增 **12758**）。「靜默日/內容稀薄」僅指**本地 meta wiki 無互動動作**（閒置預期），跨平臺 digest 餵養實際帶入真實成長數據。
- **本次不動任何 runtime config**（穩定觀察期紀律維持）；唯一 watch item＝CF 502 若復發再升級 R-4 retry。

## 1. 重啟後 live 複驗（證據）

| 項目 | 讀數 | 判定 |
|---|---|---|
| 容器 | 56 全 `Up ~2h`、0 unhealthy、0 exited | ✅（+1 vs 7/08 的 55＝新增 `ck-label-studio`） |
| health-smoke（08:26 自動跑） | `OVERALL=WARN`｜11 PASS + `C-3c federation=WARN` | 🟡 唯一 WARN 為外部 502（見 §2） |
| 三 flag（gateway 容器內） | `ZH=s2twp` / `DISPATCH=agent_query` / `FASTPATH=count` | ✅ 全 live |
| active_profile | `meta` | ✅ |
| DA-7 ops env 守衛 | ops 容器 `MISSIVE_API_TOKEN` set=yes | ✅ 烤入 Config.Env、存活重啟 |
| Windows 任務 | `CK-Hermes-Cron-Tick` Ready（每 5min，last 10:14 result=0）、`CK-Hermes-Health-Smoke` Ready（login，last 08:26 result=1〔WARN→exit 1 屬預期〕） | ✅ |
| R2 cron 台帳 | `daily-closing-v5` completed=32 last=ok（next 07-16 15:00）／`daily-awakening-v2` completed=33 last=ok（next 07-16 23:30） | ✅ 兩 job 自主連續 |

→ **`RESTART_CHECKLIST_2026-07-07` SOP 第 N 次實戰零人工全自癒**（含 nvidia-hook=PASS，6/16 P0 未重演）。

## 2. 唯一 WARN 剖析：C-3c federation（7/15 夜 CF 502）

**現象**：`morning-2026-07-16.md` 平臺行＝`missive：(digest 不可達：http_error：HTTP 502，跳過)`；federation raw 目錄最新為 `missive-2026-07-15.md`（7/14 23:30 寫），**無 `missive-2026-07-16.md`**。C-3c 判準＝最新 briefing 是否含 `raw/federation/` 連結，故 WARN。

**根因鏈**：
1. awakening（`30 23 * * *` UTC）7/15 23:30 觸發、script `last_status=ok`（fail-safe：即使 digest 子呼叫失敗，briefing 仍落地並寫明原因＝R-3 儀器化生效）。
2. digest 子呼叫撞 **CF edge HTTP 502**；R-4 retry×1 後仍 502 → 跳過聯邦段。
3. C-3c 只看「最新 briefing 有無聯邦連結」→ WARN（**正確反映**單夜 miss）。

**非回歸佐證**：
- **daily-closing（段B）同期健康**：7/15 15:00 daily 頁含**完整坤哥成長摘要**（公文 1933 / 實體 48551）→ digest 端點本質正常、走 urllib 直呼路徑成功。
- **7/09–7/14 連 6 夜聯邦 raw 頁齊全** → 502 為**單夜暫態**，非端點壞。
- `RESTART_CHECKLIST_2026-07-07` §故障排除已預先涵蓋此路徑（C-3c WARN → 看 briefing 平臺行 no_token/502 → 查 ops token / Missive 端點）＝**已知、可診斷、fail-safe**，非意外。

**判定**：屬 `2026-07-08-integration-review` 列的殘留「digest 偶發 CF 502」（R-4）。7 夜中 6 夜成功（86%），失敗夜為 fail-safe + loud log。**暫不動 config**。

## 3. B-S3-OBS 觀察期結案

| 夜（產出 briefing） | federation 結果 | 證據 |
|---|---|---|
| 7/09 晨（awakening 首夜） | ✅ 1/1 | `missive-2026-07-09.md`（CLAUDE.md 記錄） |
| 7/10 晨 | ✅ | `missive-2026-07-10.md`（7/09 23:30 寫） |
| 7/11 晨 | ✅ | `missive-2026-07-11.md` |
| 7/12 晨 | ✅ | `missive-2026-07-12.md` |
| 7/13 晨 | ✅ | `missive-2026-07-13.md` |
| 7/14 晨 | ✅ | `missive-2026-07-14.md`／`missive-2026-07-15.md`（7/14 23:30） |
| 7/16 晨 | ❌ 502 暫態 | `morning-2026-07-16` 平臺行標明、fail-safe |

→ **連 6 夜自然跑成功（遠超連 3 夜門檻）＝B-S3-OBS 決定性 CONFIRMED**。S3 跨平臺統整管道（15:00 daily + 23:30 federation 雙時段餵養）已證長期穩定自主。

## 4. 整體性建議與規劃

### 4.1 姿勢維持（本輪不動 runtime）
穩定觀察期紀律未破：系統健康、配置與現實一致、唯一 WARN 為外部暫態 + fail-safe。**本次不動任何 hermes runtime config**（延續 7/07 起「進入穩定觀察期勿動 hermes」）。

### 4.2 Watch item（條件式行動，勿預先做）
- **CF 502 復發門檻**：目前 1/7 夜。若**未來 7 日內再 miss ≥2 夜**（累積模式化），才升級 R-4：retry×1 → **retry×2 + 指數退避（如 2s/8s）**，或改走「直連後端 `ck_missive_backend:8001`（繞 CF edge）作 fallback」。單夜暫態不觸發行動（避免對噪音過度工程，對齊 GM-7c 閾值紀律）。
- **health-smoke WARN 語意**：C-3c 對「最新 briefing 無聯邦」判 WARN 是正確的，但**單夜暫態會讓重啟後首跑顯 WARN**。建議（可選、低優先）：C-3c 改看「近 3 日 briefing 是否**至少 1 日**含聯邦連結」→ 單夜暫態不擾動 OVERALL，連 3 夜才 WARN。此屬哨兵靈敏度調校，非 runtime，風險低；但因當前一眼可診斷、SOP 已涵蓋，**列選配非必辦**。

### 4.3 下一最高 CP 前進點（不變）
承 7/07–7/09 結論，hermes 本體無阻斷。前進點在**其他 repo / 內容層**：
- **R2 內容語意加工**：briefing 目前為 script 純模板（「語意加工待未來強化 LLM 環境或手動補」）。跨平臺 digest 已帶入真實成長數據（坤哥摘要），但本地 meta wiki 因無互動而稀薄。長期價值提升點＝當有真人 chat 互動時，briefing 才會有可摘素材；或引入更強 LLM 環境做語意綜合（成本議題，非本輪）。
- **CK_Missive digest 端點穩定性**（外部）：CF 502 屬 Missive 側 / CF edge，若要根治可於 CK_Missive session 查 digest 端點在 CF 前的穩定性（timeout/資源）。屬跨 repo hand-off，非 hermes。

### 4.4 重啟準備（維持就緒）
- Pre-restart 基線：本輪 live 態＝health-smoke 11 PASS + 1 外部 WARN（可診斷）、工作樹 clean、兩 Windows 任務 Ready、DA-7 token 存活、全容器 unless-stopped。
- 重啟 SOP 續讀 `RESTART_CHECKLIST_2026-07-07.md`（12 檢查〔含 C-3c/C-3d〕，末行判讀；C-3c WARN 已有診斷指引）。

## 5. 台帳讀數（本輪快照，2026-07-16 ~10:15）

- 容器：56 Up ~2h / 0 非健康 / 0 exited
- health-smoke 末行：`[2026-07-16 08:26:30] OVERALL=WARN | ... C-3c federation=WARN ...`（其餘 11 PASS）
- 三 flag：s2twp / agent_query / count（gateway 容器內實證）
- cron：daily-closing completed=32 ok／awakening completed=33 ok
- 坤哥摘要（7/15 daily）：公文 1933 / 實體 48551 / 期間新增 12758
- federation raw 連續：7/09–7/14（6 夜）；7/15 夜 502 miss
- CK_Hermes 工作樹：clean（main ahead fork 6）
