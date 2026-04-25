#!/usr/bin/env python3
"""
ck-adr-query PoC — 純 stdlib 跨 6 repo ADR 查詢

用法：
  python scripts/adr-query-poc.py search <keyword> [--repo CK_X] [--lifecycle accepted]
  python scripts/adr-query-poc.py read <FQID>          e.g. CK_Missive#0006
  python scripts/adr-query-poc.py list [--repo CK_X] [--lifecycle accepted]
  python scripts/adr-query-poc.py lifecycle <FQID>
  python scripts/adr-query-poc.py collisions
  python scripts/adr-query-poc.py index                 (full JSON index — for Variant B cron)

設計依據：docs/plans/skill-ck-adr-query-design.md
紀律：只讀；不杜撰；不改 ADR；stale warn > 30 天。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CKPROJECT_ROOT = Path(os.environ.get("CKPROJECT_ROOT", "D:/CKProject"))

ADR_LOCATIONS: dict[str, list[str]] = {
    "CK_AaaP":              ["adrs"],
    "CK_Missive":           ["docs/adr"],
    "CK_DigitalTunnel":     ["docs/adr"],
    "CK_PileMgmt":          ["docs/adr"],
    "CK_lvrland_Webmap":    ["docs/adr"],
    "CK_Showcase":          ["docs/adr", "docs/architecture/adrs"],
}

NUMBER_RE = re.compile(r"^(?:ADR-)?0*(\d{1,4})[-_]")
TITLE_RE = re.compile(r"^#\s+(?:ADR-?\d+\s*[:：]\s*)?(.+?)\s*$", re.MULTILINE)
STATUS_RE = re.compile(r"^>\s*\*\*狀態\*\*\s*[:：]?\s*(.+?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"^>\s*\*\*日期\*\*\s*[:：]?\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class Adr:
    repo: str
    number: int
    fqid: str
    path: Path
    title: str
    status: str
    date: str

    @property
    def lifecycle(self) -> str:
        s = self.status.lower()
        if "accept" in s or "已採納" in self.status or "已定案" in self.status:
            return "accepted"
        if "propos" in s or "草案" in self.status:
            return "proposed"
        if "deprecat" in s or "退場" in self.status or "廢止" in self.status:
            return "deprecated"
        if "execut" in s or "執行中" in self.status:
            return "executing"
        return "unknown"


def discover_adrs() -> list[Adr]:
    out: list[Adr] = []
    seen: set[tuple[str, int]] = set()
    for repo, sub_paths in ADR_LOCATIONS.items():
        for sub in sub_paths:
            adr_dir = CKPROJECT_ROOT / repo / sub
            if not adr_dir.is_dir():
                continue
            for f in sorted(adr_dir.rglob("*.md")):
                if f.name in {"README.md", "REGISTRY.md", "TEMPLATE.md"}:
                    continue
                m = NUMBER_RE.match(f.name)
                if not m:
                    continue
                num = int(m.group(1))
                if (repo, num) in seen:
                    continue
                seen.add((repo, num))
                try:
                    text = f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                title_m = TITLE_RE.search(text)
                status_m = STATUS_RE.search(text)
                date_m = DATE_RE.search(text)
                out.append(Adr(
                    repo=repo,
                    number=num,
                    fqid=f"{repo}#{num:04d}",
                    path=f,
                    title=(title_m.group(1) if title_m else f.stem).strip(),
                    status=(status_m.group(1) if status_m else "unknown").strip(),
                    date=(date_m.group(1) if date_m else "unknown").strip(),
                ))
    return out


def cmd_search(args: argparse.Namespace) -> int:
    needle = args.query.lower()
    hits: list[tuple[Adr, int]] = []
    for adr in discover_adrs():
        if args.repo and adr.repo != args.repo:
            continue
        if args.lifecycle and adr.lifecycle != args.lifecycle:
            continue
        text = adr.path.read_text(encoding="utf-8", errors="ignore").lower()
        score = text.count(needle)
        if score > 0:
            hits.append((adr, score))
    if not hits:
        print(f'{{"error":"no_match","tried":["{args.query}"]}}')
        return 1
    hits.sort(key=lambda x: -x[1])
    for adr, score in hits[:20]:
        print(f"{adr.fqid:24s} [{adr.lifecycle:11s}] {adr.title}  ({score} hits)")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    target = args.fqid
    for adr in discover_adrs():
        if adr.fqid == target:
            print(adr.path.read_text(encoding="utf-8", errors="ignore"))
            return 0
    print(f'{{"error":"not_found","fqid":"{target}"}}', file=sys.stderr)
    return 1


def cmd_lifecycle(args: argparse.Namespace) -> int:
    for adr in discover_adrs():
        if adr.fqid == args.fqid:
            print(f"FQID:      {adr.fqid}")
            print(f"Title:     {adr.title}")
            print(f"Status:    {adr.status}")
            print(f"Lifecycle: {adr.lifecycle}")
            print(f"Date:      {adr.date}")
            print(f"Path:      {adr.path}")
            return 0
    print(f'{{"error":"not_found","fqid":"{args.fqid}"}}', file=sys.stderr)
    return 1


def cmd_list(args: argparse.Namespace) -> int:
    items = discover_adrs()
    if args.repo:
        items = [a for a in items if a.repo == args.repo]
    if args.lifecycle:
        items = [a for a in items if a.lifecycle == args.lifecycle]
    if not items:
        print(f'{{"error":"no_match"}}')
        return 1
    print(f"{'FQID':24s}  {'STATUS':12s}  {'DATE':12s}  TITLE")
    for a in items:
        print(f"{a.fqid:24s}  {a.lifecycle:12s}  {a.date[:10]:12s}  {a.title[:60]}")
    print(f"\n({len(items)} ADRs)")
    return 0


def cmd_collisions(args: argparse.Namespace) -> int:
    by_num: dict[int, list[Adr]] = {}
    for adr in discover_adrs():
        by_num.setdefault(adr.number, []).append(adr)
    found = 0
    for num in sorted(by_num):
        adrs = by_num[num]
        if len(adrs) > 1:
            found += 1
            print(f"\n#{num:04d} ({len(adrs)} repos):")
            for a in adrs:
                print(f"  {a.fqid:24s}  {a.title[:70]}")
    if found == 0:
        print("(no number collisions)")
    else:
        print(f"\n(total {found} colliding numbers)")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """Output full ADR index as JSON (for Variant B host cron → wiki/raw/adr-index.json)."""
    adrs = discover_adrs()
    by_num: dict[int, list[str]] = {}
    for adr in adrs:
        by_num.setdefault(adr.number, []).append(adr.fqid)
    collisions = {num: fqids for num, fqids in by_num.items() if len(fqids) > 1}

    payload = {
        "schema_version": "1.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ckproject_root": str(CKPROJECT_ROOT),
        "total_adrs": len(adrs),
        "total_collisions": len(collisions),
        "adrs": [
            {
                "fqid": a.fqid,
                "repo": a.repo,
                "number": a.number,
                "title": a.title,
                "status": a.status,
                "lifecycle": a.lifecycle,
                "date": a.date,
                "path": str(a.path).replace("\\", "/"),
            }
            for a in sorted(adrs, key=lambda x: (x.repo, x.number))
        ],
        "collisions": [
            {"number": num, "fqids": fqids} for num, fqids in sorted(collisions.items())
        ],
    }
    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--repo", default="")
    s.add_argument("--lifecycle", default="", choices=["", "proposed", "accepted", "deprecated", "executing"])
    s.set_defaults(fn=cmd_search)

    r = sub.add_parser("read")
    r.add_argument("fqid")
    r.set_defaults(fn=cmd_read)

    lc = sub.add_parser("lifecycle")
    lc.add_argument("fqid")
    lc.set_defaults(fn=cmd_lifecycle)

    ls = sub.add_parser("list")
    ls.add_argument("--repo", default="")
    ls.add_argument("--lifecycle", default="", choices=["", "proposed", "accepted", "deprecated", "executing"])
    ls.set_defaults(fn=cmd_list)

    co = sub.add_parser("collisions")
    co.set_defaults(fn=cmd_collisions)

    idx = sub.add_parser("index", help="Output full JSON index (for Variant B host cron)")
    idx.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    idx.set_defaults(fn=cmd_index)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
