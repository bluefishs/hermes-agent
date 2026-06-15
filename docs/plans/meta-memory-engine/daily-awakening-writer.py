#!/usr/bin/env python3
"""
Daily awakening writer — 07:30 晨間 briefing。

設計：
- 讀前日 daily/{yesterday}.md
- 若前日有 2+ 實質摘要條目 → 寫 briefings/morning-{today}.md 含 1-3 句晨報
- 若前日靜默日（no entries）→ 寫「靜默日跟進：無新項」
- 若前日檔不存在 → 寫「（尚無昨日紀錄）」
- 不依賴 LLM；純 Python

輸出檔：briefings/morning-YYYY-MM-DD.md（idempotent）
stdout: 簡短成功 log，hermes cron agent 會收到但 prompt 會指示 [SILENT] 忽略
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")


def read_yesterday_summary(daily_path: Path) -> tuple[list[str], str | None]:
    """讀前日 daily，回傳 (今日動作條目列表, pattern 欄位原文)。"""
    if not daily_path.exists():
        return [], None

    text = daily_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 抽出 "## 今日動作摘要" 至下一個 ## 之間的內容
    summary_entries: list[str] = []
    pattern_text: str | None = None
    in_summary = False
    in_pattern = False
    pattern_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 今日動作摘要"):
            in_summary = True
            in_pattern = False
            continue
        if stripped.startswith("## 可 escalate") or stripped.startswith("## 可 escalate 或 pattern"):
            in_summary = False
            in_pattern = True
            continue
        if stripped.startswith("## "):
            in_summary = False
            in_pattern = False
            continue

        if in_summary and stripped.startswith("- "):
            summary_entries.append(stripped)
        if in_pattern and stripped and not stripped.startswith("#"):
            pattern_lines.append(stripped)

    if pattern_lines:
        pattern_text = " ".join(pattern_lines)

    return summary_entries, pattern_text


def build_morning_briefing(today: str, yesterday: str, entries: list[str], pattern: str | None) -> str:
    """組出 morning briefing 內容。"""
    if not entries:
        body = f"昨日（{yesterday}）為靜默日（無實質 wiki 動作）。今日繼續推進既有計畫。"
    else:
        top = entries[:3]
        body = f"昨日（{yesterday}）有 {len(entries)} 條紀錄，要點如下：\n\n"
        body += "\n".join(top)
        if len(entries) > 3:
            body += f"\n\n（...完整見 daily/{yesterday}.md）"
        if pattern and not pattern.startswith("（"):
            body += f"\n\n**Pattern 觀察**：{pattern}"

    return f"""---
type: briefing
category: morning
date: {today}
based_on: daily/{yesterday}.md
generated_by: daily-awakening-writer.py
---

# 晨間 Briefing {today}

{body}

---

（本 briefing 由 script 自動產生；語意加工待未來強化 LLM 環境或手動補）
"""


def main() -> int:
    now = datetime.now(TPE)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    wiki_root = Path("/opt/data/profiles/meta/wiki")
    daily_yesterday = wiki_root / "daily" / f"{yesterday}.md"
    briefings_dir = wiki_root / "briefings"
    morning_path = briefings_dir / f"morning-{today}.md"

    briefings_dir.mkdir(parents=True, exist_ok=True)

    entries, pattern = read_yesterday_summary(daily_yesterday)

    content = build_morning_briefing(today, yesterday, entries, pattern)
    morning_path.write_text(content, encoding="utf-8")

    print(f"[daily-awakening-writer] {today}: wrote {morning_path} "
          f"(based on {yesterday}, {len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
