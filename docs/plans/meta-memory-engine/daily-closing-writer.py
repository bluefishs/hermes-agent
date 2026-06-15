#!/usr/bin/env python3
"""
Daily closing writer — 直接寫 daily/YYYY-MM-DD.md，不依賴 LLM。

設計取捨（2026-04-19 決定）：
- qwen2.5:7b Q4 在零付費約束下，cron 觸發的 tool-call 鏈不穩定
- 改以純 Python script 做 idempotent daily journal
- 內容：從 log.md 自動抽今日 entries 作為「今日動作摘要」
- 未來若換更強模型，可改回 agent-driven 版本

印出的 stdout 會由 hermes cron 注入到 agent prompt；實際 file I/O 由本 script 完成。
Agent 任務只剩確認（回 [SILENT] 或一句話）。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")


def extract_today_entries(log_text: str, today: str) -> list[str]:
    """從 log.md 抓出今日日期開頭的條目。"""
    entries: list[str] = []
    prefix = f"- `{today}"
    for line in log_text.splitlines():
        if line.startswith(prefix):
            entries.append(line)
    return entries


def build_daily_content(today: str, entries: list[str]) -> str:
    """組出 daily/YYYY-MM-DD.md 內容。"""
    if not entries:
        summary = "- 靜默日（今日無實質 wiki 動作）"
        pattern = "（本日無）"
        uncertainty = "無"
    else:
        # 最多 7 條，太多則截斷並提示
        if len(entries) <= 7:
            summary = "\n".join(entries)
        else:
            summary = "\n".join(entries[:6]) + f"\n- （...本日共 {len(entries)} 條，僅列前 6；詳見 log.md）"
        pattern = "（由本 script 自動產生，無 LLM 分析；日後手動或換強模型補）"
        uncertainty = "無（script 模式下不做判斷）"

    return f"""---
type: daily
date: {today}
generated_by: daily-closing-writer.py
---

# 今日觀察 {today}

## 今日動作摘要

{summary}

## 可 escalate 或 pattern-emerging

{pattern}

## 未解問題 uncertainty

{uncertainty}
"""


def append_log_entry(log_path: Path, today: str, daily_filename: str) -> None:
    """在 log.md 末尾追加一行記錄 daily 寫入（Taipei 時區）。"""
    now = datetime.now(TPE).strftime("%H:%M")
    entry = f"- `{today} {now}` DAILY 寫入 daily/{daily_filename}（script 模式）\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)


def main() -> int:
    today = datetime.now(TPE).strftime("%Y-%m-%d")
    wiki_root = Path("/opt/data/profiles/meta/wiki")
    log_path = wiki_root / "log.md"
    daily_dir = wiki_root / "daily"
    daily_path = daily_dir / f"{today}.md"

    # 確保 daily/ 存在
    daily_dir.mkdir(parents=True, exist_ok=True)

    # 讀 log
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    entries = extract_today_entries(log_text, today)

    # 寫 daily 檔（idempotent 覆寫）
    content = build_daily_content(today, entries)
    daily_path.write_text(content, encoding="utf-8")

    # 追加 log.md
    if log_path.exists():
        append_log_entry(log_path, today, f"{today}.md")

    # stdout 給 cron 注入 agent（僅供 log）
    print(f"[daily-closing-writer] {today}: wrote {daily_path} ({len(entries)} log entries this day)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
