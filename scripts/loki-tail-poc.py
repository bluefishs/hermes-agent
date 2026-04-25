#!/usr/bin/env python3
"""
ck-loki-tail PoC — 純 stdlib 連 Loki HTTP API 萃取 CK 容器日誌

用法：
  python scripts/loki-tail-poc.py labels
  python scripts/loki-tail-poc.py services                       (列已 ingest 容器)
  python scripts/loki-tail-poc.py query <logql> [--hours N]      (LogQL 查詢)
  python scripts/loki-tail-poc.py errors [--hours 24]            (近 N 小時 ERROR-level 統計)
  python scripts/loki-tail-poc.py briefing [--hours 24]          (Markdown briefing 格式)

Loki endpoint：
  Host:      http://localhost:13100
  Container: http://host.docker.internal:13100
  Override:  LOKI_BASE 環境變數

紀律（依 Taiwan.md 觀察者）：
- 只讀；不寫；不主動干預（不 auto-restart 容器）
- 不解讀業務含義（fmt 後交使用者或對應 agent）
- 不入 wiki 業務真相；僅入 ephemeral briefing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

LOKI_BASE = os.environ.get("LOKI_BASE", "http://localhost:13100")

ERROR_PATTERN = r'(?i)(error|exception|traceback|fatal|panic|critical)'


def _request(path: str, params: dict[str, Any] | None = None, timeout: float = 10) -> dict:
    url = f"{LOKI_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ns(seconds_ago: float) -> str:
    return str(int((time.time() - seconds_ago) * 1_000_000_000))


def cmd_labels(args: argparse.Namespace) -> int:
    data = _request("/loki/api/v1/labels")
    for label in data.get("data", []):
        print(label)
    return 0


def cmd_services(args: argparse.Namespace) -> int:
    data = _request("/loki/api/v1/label/container/values")
    for v in sorted(data.get("data", [])):
        print(v)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    end_ns = _ns(0)
    start_ns = _ns(args.hours * 3600)
    data = _request(
        "/loki/api/v1/query_range",
        {"query": args.logql, "start": start_ns, "end": end_ns, "limit": str(args.limit)},
    )
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        ident = labels.get("container") or labels.get("service") or "<no-label>"
        for ts_ns, line in stream.get("values", []):
            ts_s = int(ts_ns) // 1_000_000_000
            ts_iso = time.strftime("%H:%M:%S", time.localtime(ts_s))
            print(f"[{ts_iso}] {ident}: {line[:200]}")
    return 0


def cmd_errors(args: argparse.Namespace) -> int:
    end_ns = _ns(0)
    start_ns = _ns(args.hours * 3600)
    logql = f'{{container=~".+"}} |~ "{ERROR_PATTERN}"'
    data = _request(
        "/loki/api/v1/query_range",
        {"query": logql, "start": start_ns, "end": end_ns, "limit": "5000"},
    )
    counter: Counter[str] = Counter()
    samples: dict[str, str] = {}
    total = 0
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        ident = labels.get("container") or labels.get("service") or "<no-label>"
        for _ts_ns, line in stream.get("values", []):
            counter[ident] += 1
            total += 1
            samples.setdefault(ident, line[:140].strip())
    print(f"Total ERROR-pattern lines in last {args.hours}h: {total}")
    print(f"Distinct services emitting: {len(counter)}\n")
    for ident, count in counter.most_common():
        print(f"  {count:>6}  {ident}")
        sample = samples.get(ident, "")
        if sample:
            print(f"          ↳ {sample}")
    return 0 if total > 0 else 1


def cmd_briefing(args: argparse.Namespace) -> int:
    end_ns = _ns(0)
    start_ns = _ns(args.hours * 3600)
    logql = f'{{container=~".+"}} |~ "{ERROR_PATTERN}"'
    data = _request(
        "/loki/api/v1/query_range",
        {"query": logql, "start": start_ns, "end": end_ns, "limit": "5000"},
    )
    counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}
    for stream in data.get("data", {}).get("result", []):
        ident = stream.get("stream", {}).get("container") or "<no-container>"
        for _ts_ns, line in stream.get("values", []):
            counter[ident] += 1
            samples.setdefault(ident, []).append(line[:160].strip())

    today = time.strftime("%Y-%m-%d")
    print(f"# 觀測 Briefing — 近 {args.hours}h ERROR 取樣")
    print()
    print(f"產生時間：{today} {time.strftime('%H:%M:%S')}（Taipei）  | Loki query window：{args.hours} 小時")
    print()
    if not counter:
        print("> 靜默期：本時段無偵測到 ERROR-level pattern。")
        return 0
    total = sum(counter.values())
    print(f"## 摘要")
    print()
    print(f"- 共 {total} 條 ERROR-pattern 訊息，分散於 {len(counter)} 個容器")
    print(f"- 前三大來源：")
    for ident, count in counter.most_common(3):
        print(f"  - `{ident}` ×{count}")
    print()
    print("## 各容器詳情")
    print()
    for ident, count in counter.most_common():
        print(f"### `{ident}` ×{count}")
        print()
        sample_lines = samples.get(ident, [])[:3]
        for line in sample_lines:
            print(f"  - `{line}`")
        if len(samples.get(ident, [])) > 3:
            print(f"  - ...（另 {len(samples[ident]) - 3} 條）")
        print()
    print("## 紀律提醒")
    print()
    print("- 本 briefing 僅彙整觀測；**不**自動干預（restart / kill）")
    print("- 業務含義由對應 agent 解讀（Missive 用 ck-missive-bridge）")
    print("- 若需根因，建議：`docker logs <container> --tail 200 --since 1h`")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("labels").set_defaults(fn=cmd_labels)
    sub.add_parser("services").set_defaults(fn=cmd_services)

    q = sub.add_parser("query")
    q.add_argument("logql")
    q.add_argument("--hours", type=int, default=1)
    q.add_argument("--limit", type=int, default=100)
    q.set_defaults(fn=cmd_query)

    e = sub.add_parser("errors")
    e.add_argument("--hours", type=int, default=24)
    e.set_defaults(fn=cmd_errors)

    b = sub.add_parser("briefing")
    b.add_argument("--hours", type=int, default=24)
    b.set_defaults(fn=cmd_briefing)

    args = p.parse_args()
    try:
        return args.fn(args)
    except urllib.error.URLError as ex:
        print(f'{{"error":"loki_unreachable","base":"{LOKI_BASE}","detail":"{ex}"}}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
