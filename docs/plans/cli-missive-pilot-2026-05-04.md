# CLI 層 Missive Pilot — 7 天 tool-calling baseline

> **日期**：2026-05-04
> **觸發**：spike 後 R1 風險 surface 重塑、Master Plan v2 W2 排定 Missive 首發
> **路徑選擇**：CLI 層（與 Docker gateway 解耦），不依賴方案 Y 落地
> **狀態**：設計就緒；等候 CK_AaaP session 提供 `CK_Missive/SOUL.md`

---

## §1 目標

在 **CLI 通道**（`python -m hermes_cli.main -p missive chat`）跑 Master Plan v2 §9 第一個成功指標：

> **Missive agent 試跑 7 天 tool-calling 成功率 ≥ 70%**

不依賴 Telegram / Web UI / 方案 Y。所有量測直接來自 CLI 互動歷程。

---

## §2 前置條件

| 項目 | 狀態 | 負責 session |
|---|---|---|
| `~/.hermes/profiles/missive/` 存在 | ✅（spike 已驗）| — |
| `CK_Missive/SOUL.md` 已落地 | ❌ 待 | **CK_AaaP** |
| `~/.hermes/profiles/missive/SOUL.md` symlink/copy 至上 | ❌ 待 | hermes-agent |
| `ck-missive-bridge` skill 已部署 | ✅（v2.0 既有） | — |
| `MCP_SERVICE_TOKEN` 已配 | ✅（既有 .env） | — |
| Missive backend 公網健康 `missive.cksurvey.tw` | ✅ | — |

**啟動條件**：CK_AaaP session 完成 SOUL push + 通知本 session 後，本 session 5 min 內可啟動 W2a。

---

## §3 SOUL Sync 機制

**Spike R3 結論**：Windows Docker 下 symlink 不穩，**改用 copy + 簡單 sync script**。

### 3.1 sync 腳本（本 session 預先準備）

```bash
# scripts/sync-missive-soul.sh
#!/usr/bin/env bash
set -e
SRC="${CK_MISSIVE_REPO:-/d/CKProject/CK_Missive}/SOUL.md"
DST="$HOME/.hermes/profiles/missive/SOUL.md"

if [ ! -f "$SRC" ]; then
  echo "[sync] source not found: $SRC" >&2; exit 1
fi

# Atomic copy + checksum verify
TMP="$DST.tmp.$$"
cp "$SRC" "$TMP"
SRC_HASH=$(sha256sum "$SRC" | awk '{print $1}')
TMP_HASH=$(sha256sum "$TMP" | awk '{print $1}')
if [ "$SRC_HASH" != "$TMP_HASH" ]; then
  rm -f "$TMP"
  echo "[sync] checksum mismatch" >&2; exit 2
fi
mv "$TMP" "$DST"
echo "[sync] $SRC -> $DST ($(wc -c < "$DST") bytes)"
```

執行頻率：CK_Missive/SOUL.md 變更時手動觸發；後續可考慮 cron 每日對齊。

### 3.2 暫不入 git

`~/.hermes/profiles/missive/SOUL.md` 屬 runtime artifact，不入 hermes-agent repo。CK_Missive/SOUL.md 才是 canonical（依 Master Plan v2 D9）。

---

## §4 7 天追蹤格式

### 4.1 量測模式

每日固定流程：
1. **早晨 9:00** 跑 8 條既定 prompt 套組（§5）
2. 每條 prompt 紀錄結果（§4.2 schema）
3. **晚間 22:00** 補一輪自由互動（≥ 3 次），補相同 schema
4. 累計 7 天 ≥ 77 次互動（8 × 7 + 3 × 7）

### 4.2 Schema

`docs/plans/missive-pilot-results/day-YYYY-MM-DD.csv`：

```csv
ts,prompt_id,prompt_summary,tool_called,tool_success,response_quality,notes
2026-05-05T09:00:01,fixed-1,"查今天最新公文",ck-missive-bridge.list_documents,1,4,"前 3 筆正確"
2026-05-05T09:00:30,fixed-2,"找最近 ezbid 標案",ck-missive-bridge.search_keywords,0,2,"timeout 30s"
```

欄位：
- `tool_called`：實際呼叫的 tool（空字串 = 未觸發 tool）
- `tool_success`：1=tool 回 200 + 結果非空、0=失敗或空
- `response_quality`：1–5 主觀評分（1=胡說、3=可用、5=精準）
- `notes`：自由欄

### 4.3 Daily Roll-up

每日 23:30 跑 `scripts/missive-pilot-rollup.py`（**待寫**），輸出：

```
day=2026-05-05
 total_prompts=11
 tool_calls=9 (81.8%)
 tool_success=7 (77.8% of calls; 63.6% of prompts)
 quality_avg=3.4 (median 4)
 notes_keywords: timeout (1), missing_field (1)
```

### 4.4 Week-end 結算

day 7 跑 `scripts/missive-pilot-weekly.py`（**待寫**）：

```
week=2026-05-05..2026-05-11
 total=77
 tool_call_rate=78.4%
 tool_success_rate=72.1%
 quality_p50=4 quality_avg=3.6
 ↑↑ Master Plan v2 §9 目標 70% PASS ✓
 notable_failures:
  - timeout × 4（皆 search_keywords）
  - 401 × 1（凌晨 3:00 token 過期？）
```

---

## §5 8 條既定 prompt 套組

涵蓋 ck-missive-bridge v2.0 主要 tool surface：

| # | prompt（zh-TW） | 預期觸發 tool |
|---|---|---|
| 1 | 「查今天最新進來的公文，前 5 筆即可」 | list_documents |
| 2 | 「最近一週有沒有跟『高雄市』有關的案件？」 | search_keywords |
| 3 | 「公文編號 DOC-2026-001 詳細內容」 | get_document |
| 4 | 「ezbid 最新三筆標案」 | search_ezbid（若 v2.0 有） |
| 5 | 「請列出本週『土地查估』tag 的所有條目」 | list_by_tag |
| 6 | 「今天有哪些案件待回覆？」 | list_pending |
| 7 | 「KG 圖譜上跟 case_id=12345 相關的 entity 有哪些？」 | kg_query |
| 8 | 「最近 3 筆公文摘要 + 我可能要做的事」 | list_documents + summarize（多 tool） |

**設計原則**：
- 涵蓋 list / search / get / tag / pending / kg / multi-tool 七種模式
- 每條 zh-TW、自然語氣、避開明確 tool 名稱（測 LLM 的 tool routing 能力）
- 故意混入 #8 多 tool 場景，測編排能力

---

## §6 容錯與資安

| 場景 | 預期反應 |
|---|---|
| Missive backend down | 工具回 503，agent 回「我目前無法查 Missive，請稍後再試」 |
| MCP_SERVICE_TOKEN 過期 | 401，agent 回「身份驗證失敗，請使用者協助」（不主動嘗試重簽） |
| Tool timeout 30 s | 記錄 timeout=1，回降級訊息 |
| 使用者問業務修改（如「把這筆改成已結案」） | agent 拒絕（依 SOUL §自主權「不修改業務真相」） |

---

## §7 工具：rollup script 草樣

`scripts/missive-pilot-rollup.py`（**本文件附錄，待 PoC 啟動時寫實**）：

```python
"""rollup a day's missive pilot CSV → markdown summary."""
import csv, sys, statistics
from collections import Counter
from pathlib import Path

def main(csv_path: Path):
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    tool_called = sum(1 for r in rows if r["tool_called"])
    tool_ok = sum(1 for r in rows if r["tool_success"] == "1")
    qualities = [int(r["response_quality"]) for r in rows if r["response_quality"]]
    notes = Counter(w for r in rows for w in (r["notes"] or "").split() if len(w) > 2)
    print(f"total={n} tool_calls={tool_called} ({100*tool_called/n:.1f}%)")
    print(f"tool_success={tool_ok} ({100*tool_ok/max(tool_called,1):.1f}% of calls)")
    print(f"quality avg={statistics.mean(qualities):.2f} median={statistics.median(qualities)}")
    print(f"notable: {notes.most_common(5)}")

if __name__ == "__main__":
    main(Path(sys.argv[1]))
```

---

## §8 啟動 SOP（CK_AaaP session 採納後）

```bash
# 1. 拉取 CK_Missive/SOUL.md（CK_AaaP session push 完成後）
cd /d/CKProject/CK_Missive && git pull

# 2. 同步至 missive profile
bash /d/CKProject/hermes-agent/scripts/sync-missive-soul.sh

# 3. 啟動 day-1 量測（早晨 9:00）
mkdir -p /d/CKProject/hermes-agent/docs/plans/missive-pilot-results
DATE=$(date +%Y-%m-%d)
echo "ts,prompt_id,prompt_summary,tool_called,tool_success,response_quality,notes" \
  > /d/CKProject/hermes-agent/docs/plans/missive-pilot-results/day-$DATE.csv

# 4. 互動：對 missive profile 跑 8 條 prompt
# python -m hermes_cli.main -p missive chat
# （手動執行，逐條紀錄到 csv）

# 5. 23:30 跑 rollup
python /d/CKProject/hermes-agent/scripts/missive-pilot-rollup.py \
  /d/CKProject/hermes-agent/docs/plans/missive-pilot-results/day-$DATE.csv
```

---

## §9 風險

| # | 風險 | 緩解 |
|---|---|---|
| M1 | qwen2.5:7b tool routing 能力不足，#8 multi-tool 失敗率高 | 第 3 天若 #8 連 3 天 ≤ 2 評分，下調目標為「single-tool 70%」，標 multi-tool 為下階段 |
| M2 | SOUL.md 7 天內 CK_Missive 改版導致行為漂移 | 每次 SOUL 更新後重啟 day-N 計時；rollup 時記 SOUL hash |
| M3 | Missive backend 凌晨自動重啟，token 失效 | 跳過 token 過期窗口的紀錄；不計入 fail rate |
| M4 | 7 天樣本數不足支撐統計（< 77） | 第 4 天若累計 < 30，調整為加碼日 5 prompt |
| M5 | 主觀 quality 評分漂移（前後不一） | 每日結算時抽 2 條重看；對齊 1–5 標準 |

---

## §10 完成定義

- [ ] 7 天 csv 全到位
- [ ] 7 份 daily rollup
- [ ] 1 份 weekly 結算
- [ ] tool-calling 成功率明確（PASS/FAIL Master Plan v2 §9 70% 門檻）
- [ ] 5 個典型失敗案例（含原 prompt + tool trace + 改善建議）

---

**等候**：CK_Missive/SOUL.md push（CK_AaaP session）+ 使用者授權啟動 day-1（本 session 收到後 5 min 內可動）。
