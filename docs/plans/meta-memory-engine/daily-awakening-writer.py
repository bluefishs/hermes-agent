#!/usr/bin/env python3
"""
Daily awakening writer — 07:30 晨間 briefing。

設計：
- 讀前日 daily/{yesterday}.md
- 若前日有 2+ 實質摘要條目 → 寫 briefings/morning-{today}.md 含 1-3 句晨報
- 若前日靜默日（no entries）→ 寫「靜默日跟進：無新項」
- 若前日檔不存在 → 寫「（尚無昨日紀錄）」
- 不依賴 LLM；純 Python
- 【S3 段C，2026-07-07】跨平臺聯邦：對已激活平臺逐一拉 memory_digest（經 bridge
  query.py，段A/B 已通），原始摘要落 wiki/raw/federation/<platform>-<date>.md，
  briefing 併入「跨平臺意識體」段。單一平臺失敗只標「(digest 不可達，跳過)」，
  不阻斷本地 briefing（fault isolation，契約 s3-meta-federation-briefing-design §2C）。

輸出檔：briefings/morning-YYYY-MM-DD.md（idempotent）
stdout: 簡短成功 log，hermes cron agent 會收到但 prompt 會指示 [SILENT] 忽略
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")

# S3 段C：已激活平臺 → 對應 bridge query.py（各平臺意識體成長摘要來源）。
# 擴充新平臺＝該域後端先比照坤哥開 digest 端點（ADR-CK-003 §6），再加一行。
FEDERATION_PLATFORMS = {
    "missive": "/opt/data/skills/ck-missive-bridge/scripts/query.py",
}

# R-4（2026-07-08）：digest 端點偶發 CF 502，單次失敗即丟整晚 digest → 失敗後重試 1 次。
_FED_RETRIES = 1
_FED_RETRY_DELAY_S = 30


def _run_memory_digest(query_py: str) -> tuple[dict, str]:
    """跑一次 query.py memory_digest。回 (payload, 失敗原因)；成功時原因為空字串。"""
    proc = subprocess.run(
        [sys.executable, query_py, "memory_digest"],
        capture_output=True, text=True, timeout=60,
        cwd=str(Path(query_py).parent),
    )
    raw = (proc.stdout or "").strip()
    try:
        payload = json.loads(raw or "{}")
    except ValueError:
        return {}, (f"stdout 非 JSON（rc={proc.returncode}，"
                    f"stderr 尾：{(proc.stderr or '')[-200:].strip() or '無'}）")
    if payload.get("ok") and payload.get("data", {}).get("digest_text"):
        return payload, ""
    # R-3（2026-07-08 儀器化）：非 ok payload 曾整整兩晚靜默吞掉 no_token（ops 容器缺
    # MISSIVE env），briefing 只見籠統「不可達」→ 把 query.py 的 error/message 帶出來。
    reason = payload.get("error") or "payload 無 digest_text"
    if payload.get("message"):
        reason = f"{reason}：{payload['message'][:120]}"
    return payload, str(reason)


def collect_federation(wiki_root: Path, today: str) -> list[tuple[str, str | None, str]]:
    """逐平臺拉 memory_digest；成功→寫 raw/federation/ 並回 digest_text，失敗→(None, 原因)。

    全程 fault-isolated：任何平臺任何錯誤都只影響該平臺段落，絕不 raise。
    失敗原因一律進 stdout（cron output 只保 stdout）與 briefing 該平臺行。
    """
    results: list[tuple[str, str | None, str]] = []
    fed_dir = wiki_root / "raw" / "federation"
    for platform, query_py in FEDERATION_PLATFORMS.items():
        digest_text: str | None = None
        fail_reason = ""
        try:
            for attempt in range(1 + _FED_RETRIES):
                payload, fail_reason = _run_memory_digest(query_py)
                if not fail_reason:
                    break
                if attempt < _FED_RETRIES:
                    print(f"[daily-awakening-writer] federation {platform} 第 {attempt + 1} 次失敗"
                          f"（{fail_reason}），{_FED_RETRY_DELAY_S}s 後重試")
                    time.sleep(_FED_RETRY_DELAY_S)
            if not fail_reason:
                data = payload["data"]
                digest_text = data["digest_text"]
                fed_dir.mkdir(parents=True, exist_ok=True)
                raw_path = fed_dir / f"{platform}-{today}.md"
                raw_path.write_text(
                    f"---\ntype: federation_digest\nplatform: {platform}\n"
                    f"consciousness: {data.get('consciousness', platform)}\n"
                    f"as_of: {data.get('as_of', '')}\ncollected: {today}\n---\n\n"
                    f"# {data.get('consciousness', platform)} 成長摘要（{today} 收）\n\n"
                    f"{digest_text}\n\n## 原始 growth\n\n```json\n"
                    f"{json.dumps(data.get('growth', {}), ensure_ascii=False, indent=2)}\n```\n",
                    encoding="utf-8",
                )
        except Exception as e:  # noqa: BLE001 — 聯邦收集絕不阻斷本地 briefing（契約 fault isolation）
            fail_reason = f"{type(e).__name__}: {e}"
        if fail_reason:
            print(f"[daily-awakening-writer] federation {platform} 收集失敗（跳過）: {fail_reason}")
        results.append((platform, digest_text, fail_reason))
    return results


def build_federation_section(results: list[tuple[str, str | None, str]], today: str) -> str:
    """組「跨平臺意識體」段落（無平臺配置時回空字串）。"""
    if not results:
        return ""
    lines = ["\n## 跨平臺意識體\n"]
    for platform, digest_text, fail_reason in results:
        if digest_text:
            lines.append(f"**{platform}**：{digest_text}")
            lines.append(f"（原始：raw/federation/{platform}-{today}.md）\n")
        else:
            lines.append(f"**{platform}**：(digest 不可達：{fail_reason or '原因不明'}，跳過)\n")
    return "\n".join(lines)


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

    # S3 段C：跨平臺聯邦段（collect 失敗只影響該平臺段落，絕不阻斷本地 briefing）
    fed_results = collect_federation(wiki_root, today)
    fed_section = build_federation_section(fed_results, today)
    if fed_section:
        footer = "---\n\n（本 briefing 由 script 自動產生"
        if footer in content:
            content = content.replace(footer, f"{fed_section}\n{footer}", 1)
        else:  # 模板變動時 fallback：附加於文末
            content += fed_section

    morning_path.write_text(content, encoding="utf-8")

    fed_ok = sum(1 for _, t, _r in fed_results if t)
    print(f"[daily-awakening-writer] {today}: wrote {morning_path} "
          f"(based on {yesterday}, {len(entries)} entries, "
          f"federation {fed_ok}/{len(fed_results)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
