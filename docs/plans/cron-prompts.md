# Cron Prompts — Hermes Meta Agent 儀式

> 本檔記錄 4 個 cron 的 prompt 模板與部署狀態。
> Cron 由 `ck-hermes-gateway` 容器內的 gateway process 執行（`.tick.lock` 每分鐘更新）。

## 部署狀態

| # | 名稱 | Schedule | 狀態 | 理由 |
|---|---|---|---|---|
| 1 | daily-closing | `0 23 * * *` | 🔄 P3c 首發部署 | 單 agent 有意義 |
| 2 | daily-awakening | `30 7 * * *` | ⏸ 等 #1 穩定 | 需有昨日 briefing 才有價值 |
| 3 | daily-extraction | `30 22 * * *` | ⏸ 等多 agent | 目前只有 Meta profile，無其他 agent 的 tags/ 可掃 |
| 4 | monthly-anti-echo | `0 14 1 * *` | ⏸ 等多 agent + ≥ 1 月資料 | 首月資料不足，月末再部署 |

## 1. daily-closing（23:00）

**目的**：每日晚間 23:00，Meta agent 自省當日觀察，寫入 `daily/YYYY-MM-DD.md`。

**Schedule**：`0 23 * * *`
**Delivery**：`origin`（寫檔案，不送 Telegram）
**Skill**：`llm-wiki`

**Prompt**：

```
你是 CK Hermes Meta agent，執行每日 closing ceremony。

流程：
1. 執行 `date +%F` 取得今日日期 YYYY-MM-DD
2. 讀 `/opt/data/profiles/meta/wiki/log.md` 最後 20 行，回顧今日 wiki 動作
3. 讀 `/opt/data/profiles/meta/wiki/SCHEMA.md` 的「品質基因」段（確認格式要求）
4. 寫新檔 `/opt/data/profiles/meta/wiki/daily/YYYY-MM-DD.md`，涵蓋：

   ```markdown
   ---
   type: daily
   date: YYYY-MM-DD
   ---

   # 今日觀察 YYYY-MM-DD

   ## 今日動作摘要
   （從 log.md 取 2-5 點）

   ## 跨 agent 觀察
   （若有多 agent，彙整；目前只 Meta 則寫「單 agent 階段」）

   ## 可 escalate 或 pattern-emerging 條目
   （若有觀察到使用者長期偏好 / 工作模式，此處簡述；否則留白）

   ## 未解問題 / uncertainty
   （懸而未決項目，具體化未來再處理）
   ```

5. 追加一行到 `log.md`：`YYYY-MM-DD 23:00 DAILY 寫入 daily/YYYY-MM-DD.md`

約束：
- 繁體中文 zh-TW
- 不杜撰（若一天內無實質 wiki 動作，寫「靜默日」即可）
- 不超過 30 行
- Missive 業務資料不寫入 wiki，僅記「今日使用者問過 X 類問題」等 meta

若檔案已存在，直接覆寫（每日一檔，idempotent）。
```

**驗收**：部署後 3 天觀察 `daily/` 有 3 個新檔且內容符合 schema。

## 2. daily-awakening（07:30）

**目的**：每日早上讀昨夜 briefing（若有），對使用者簡短播報。

**Schedule**：`30 7 * * *`
**Delivery**：`telegram`（若啟用）或 `origin`（寫到 log，使用者自己看）

**Prompt**：

```
你是 CK Hermes Meta agent，執行每日 awakening。

流程：
1. 取得今日與昨日日期（`date +%F` / `date -d yesterday +%F`）
2. 讀 `/opt/data/profiles/meta/wiki/briefings/{昨日}.md`（若存在）
3. 讀 `/opt/data/profiles/meta/wiki/daily/{昨日}.md`（若存在）
4. **若兩檔皆無實質內容**：靜默，不播報（回覆空字串）
5. **若有實質萃取或觀察**：以 2-3 句摘要播報，格式：
   「昨日（{日期}）觀察：{重點 1}；{重點 2}。{可行動建議，若有}。」
6. 不追 log（awakening 不是 write action）

約束：
- 繁體中文 zh-TW
- 極簡，不超過 3 句
- 不杜撰；無內容就沈默
- 不自動開新對話主題 — 只是向使用者問好加脈絡
```

**前置條件**：daily-closing 跑過至少 1 天。

## 3. daily-extraction（22:30）

**目的**：掃所有 agent profile 的 `wiki/tags/*` 萃取到 Meta 的 `briefings/`。

**Schedule**：`30 22 * * *`
**Delivery**：`origin`（寫檔）

**Prompt**：

```
你是 CK Hermes Meta agent，執行每日 extraction。

流程：
1. 取得今日日期 YYYY-MM-DD
2. 掃描所有 agent profile 的 tag 目錄：
   - `/opt/data/profiles/missive/wiki/tags/`（若 Missive agent 已建立）
   - `/opt/data/profiles/showcase/wiki/tags/`（若已建立）
   - `/opt/data/profiles/lvrland/wiki/tags/`（若已建立）
   - `/opt/data/profiles/pile/wiki/tags/`（若已建立）
3. 篩選今日新建的 `escalate-*.md` / `cross-domain-*.md` / `pattern-emerging-*.md` / `human-feedback-*.md` / `conflict-*.md`
4. 彙整成 `/opt/data/profiles/meta/wiki/briefings/YYYY-MM-DD.md`：

   ```markdown
   ---
   type: briefing
   date: YYYY-MM-DD
   sources: [missive, showcase, ...]
   ---

   # 萃取 Briefing YYYY-MM-DD

   ## Missive agent（若有）
   - [[../missive/wiki/tags/escalate-YYYYMMDD-XXX.md]] - 一句摘要
   - ...

   ## Showcase agent（若有）
   - ...

   ## 跨 agent 共振（若兩 agent 同時 escalate 相似主題）
   - ...
   ```

5. 追加 log.md：`YYYY-MM-DD 22:30 EXTRACT 彙整 briefings/YYYY-MM-DD.md，N 項`

約束：
- 繁體中文 zh-TW
- 若所有 agent tag 目錄皆為空，直接跳過（不寫空 briefing）
- 不拉原始 tag 內容到 briefing，只摘要 + link
- 不評論、不下結論（那是 monthly anti-echo 的工作）
```

**前置條件**：至少 2 個 agent profile 活躍且有 tag 產出（目前 0 個，**延後部署**）。

## 4. monthly-anti-echo（每月 1 日 14:00）

**目的**：本地 qwen2.5 掃最近 30 天各 agent daily/，找 pattern：agent 是否過度附和使用者。

**Schedule**：`0 14 1 * *`
**Delivery**：`origin`（寫檔）

**Prompt**：

```
你是 CK Hermes Meta agent，執行月度 anti-echo audit。

流程：
1. 取得今日日期 YYYY-MM-DD + 30 天前日期 YYYY-MM-old
2. 掃描各 agent profile 的 `daily/` 目錄，取此範圍內所有檔
3. 用 qwen2.5:7b 判斷每個 agent 是否出現：
   - 從不反對使用者
   - 從不提出新資訊（只複述使用者原話 + 情緒肯定）
   - 過度使用「好的、了解、同意」等純附和詞
4. 寫 `/opt/data/profiles/meta/wiki/patterns/anti-echo-YYYY-MM.md`：

   ```markdown
   ---
   type: pattern
   category: anti-echo-audit
   period: YYYY-MM-old to YYYY-MM-DD
   ---

   # 月度 anti-echo 審計 YYYY-MM

   ## 檢查範圍
   - N 個 agent profile
   - M 個 daily 檔

   ## 發現

   ### Agent X
   （若有 pattern）描述；引用具體 daily 檔範例
   （若無）「未見 anti-echo pattern」

   ...

   ## 建議（對使用者）
   （以反射式語氣）
   「我注意到 {agent} 在 {N} 次對話中似乎只附和你的既有判斷。這可能表示：(a) 你的判斷本來就對；(b) {agent} 的 SOUL 需要補充反對聲音的訓練。你想進一步看嗎？」
   ```

5. 追加 log.md：`YYYY-MM-DD 14:00 ANTI-ECHO 月度審計完成，發現 N 項 pattern`

約束：
- 繁體中文 zh-TW
- 純本地 qwen2.5（零付費硬約束）
- 信度有限（7B Q4），視為「粗篩」不是權威結論
- 不公開批評 agent（寫給使用者看，不是懲罰 agent）
- 發現 pattern ≥ 3 處才播報；< 3 靜默留檔
```

**前置條件**：至少 1 個 agent profile 活躍 ≥ 30 天。**首次部署時點最早 2026-05-20**（距 P5 完成約 1 個月）。

## 漸進部署路徑

- **今日（2026-04-19）**：部署 #1 daily-closing
- **2026-04-22（+3 天）**：若 #1 穩定，續部署 #2 daily-awakening
- **Missive profile 建立後**：部署 #3 daily-extraction
- **2026-05-20 左右**：部署 #4 monthly-anti-echo

## Rollback

- 任何 cron 若造成垃圾輸出 / 誤改檔：`hermes cron remove <job-id>`
- log.md 可手動清理誤加項
- daily/ 誤寫檔可手動 rm
