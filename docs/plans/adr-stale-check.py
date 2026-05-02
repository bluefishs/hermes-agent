#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ADR Stale Check — 季度結算與長期 proposed 警示

掃描所有 ADR，找出狀態為 proposed/executing/Phase 但日期 ≥ N 天前的項目，
產出 stale 警告。整合到 check-doc-drift.sh CI 模式（過 stale 即 exit 1）。

設計原則（per ADR-0029 Governance Lessons Registry 精神 + 路線圖 #15）：
- ADR 從 proposed 起進入 90 天 grace
- ≥ 90 天仍 proposed → stale，要求季度結算（accept / reject / defer-with-reason）
- ≥ 180 天 → critical，強制決議
- accepted 後不重新計算
- defer 必須在 ADR body 加 `**defer_until**: YYYY-MM-DD` 欄位才豁免 stale

執行：
    python adr-stale-check.py                 # 列警示
    python adr-stale-check.py --threshold 90  # 改閾值
    python adr-stale-check.py --ci            # 過 stale 即 exit 1
    python adr-stale-check.py --json          # 機器可讀

採納路徑（CK_AaaP）：
    cp <hermes-agent>/docs/plans/adr-stale-check.py CK_AaaP/scripts/checks/adr-stale-check.py
    chmod +x CK_AaaP/scripts/checks/adr-stale-check.py
    # 在 check-doc-drift.sh CI 段加：
    #   python "$REPO_ROOT/scripts/checks/adr-stale-check.py" --ci || EXIT=1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from pathlib import Path

# 引用 generate-adr-registry 的 parsing 邏輯（duck-typed import）
SCRIPT_DIR = Path(__file__).resolve().parent
# 此腳本將部署到 CK_AaaP/scripts/checks/，generate-adr-registry.py 在 CK_AaaP/scripts/
# 採納時 sys.path 補上 parent 即可 import
sys.path.insert(0, str(SCRIPT_DIR.parent))

# 嘗試從 generate-adr-registry import；若 stand-alone 跑（如本草稿）則 inline 重寫
try:
    from importlib import import_module  # noqa
    _gen = import_module("generate-adr-registry")
    _scan_repo = _gen._scan_repo
    _extract_metadata = _gen._extract_metadata
    ADR_DIRS = _gen.ADR_DIRS
    _NAME_PATTERNS = _gen._NAME_PATTERNS
    _SKIP_NAMES = _gen._SKIP_NAMES
except Exception:
    # Fallback 內建版本（與 generate-adr-registry 同源邏輯）
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    CKPROJECT_ROOT = Path(__file__).resolve().parents[3]  # docs/plans → hermes-agent → CKProject
    ADR_DIRS = {
        "CK_AaaP":           CKPROJECT_ROOT / "CK_AaaP" / "adrs",
        "CK_Missive":        CKPROJECT_ROOT / "CK_Missive" / "docs" / "adr",
        "CK_DigitalTunnel":  CKPROJECT_ROOT / "CK_DigitalTunnel" / "docs" / "adr",
        "CK_PileMgmt":       CKPROJECT_ROOT / "CK_PileMgmt" / "docs" / "adr",
        "CK_lvrland_Webmap": CKPROJECT_ROOT / "CK_lvrland_Webmap" / "docs" / "adr",
        "CK_Showcase":       CKPROJECT_ROOT / "CK_Showcase" / "docs" / "adr",
    }
    _NAME_PATTERNS = [re.compile(r"^(?:ADR-)?(\d{3,4})[-_](.+?)\.md$", re.IGNORECASE)]
    _SKIP_NAMES = {"README.md", "TEMPLATE.md"}

    def _extract_metadata(path: Path) -> dict:
        meta = {"title": "", "status": "", "date": "", "defer_until": ""}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return meta
        for line in text.splitlines()[:50]:
            s = line.strip()
            if not meta["title"] and s.startswith("# "):
                t = s[2:].strip()
                t = re.sub(r"^ADR[-_ ]\d+[:：\s]*", "", t, flags=re.IGNORECASE)
                meta["title"] = t
            if not meta["status"]:
                m = re.search(r"\*\*(?:狀態|status)\*\*\s*[:：]?\s*(.+?)(?:\s|$)", s, re.IGNORECASE)
                if m:
                    meta["status"] = m.group(1).strip().rstrip("。.,")
            if not meta["date"]:
                m = re.search(r"(\d{4}-\d{2}(?:-\d{2})?)", s)
                if m and ("日期" in s or "date" in s.lower() or "Date" in s):
                    meta["date"] = m.group(1)
            if not meta["defer_until"]:
                m = re.search(r"\*\*defer_until\*\*\s*[:：]?\s*(\d{4}-\d{2}-\d{2})", s, re.IGNORECASE)
                if m:
                    meta["defer_until"] = m.group(1)
        return meta


# 視為 in-flight 的狀態（需要季度結算的）
_IN_FLIGHT_TERMS = ("proposed", "提案", "executing", "執行中", "實施中",
                    "phase", "draft", "in progress")


@dataclass
class StaleADR:
    repo: str
    fqid: str
    title: str
    status: str
    date: str
    age_days: int
    severity: str  # "stale" | "critical"
    deferred: bool
    defer_until: str

    def __post_init__(self):
        # FQID 格式：<Repo>#<NNNN>
        pass


def _is_in_flight(status: str) -> bool:
    s = (status or "").lower()
    return any(t in s for t in _IN_FLIGHT_TERMS)


def _parse_date(date_str: str) -> date | None:
    if not date_str or date_str == "—":
        return None
    s = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def scan_stale(threshold_days: int = 90, critical_days: int = 180) -> list[StaleADR]:
    """掃所有 ADR repo，回傳 stale 清單（按 age 降序）。"""
    today = datetime.now(timezone.utc).date()
    stale: list[StaleADR] = []

    for repo, adr_dir in ADR_DIRS.items():
        if not adr_dir.is_dir():
            continue
        for entry in sorted(adr_dir.iterdir()):
            if not entry.is_file() or entry.name in _SKIP_NAMES:
                continue
            if entry.suffix.lower() != ".md":
                continue
            m = None
            for pat in _NAME_PATTERNS:
                m = pat.match(entry.name)
                if m:
                    break
            if not m:
                continue
            num = int(m.group(1))
            fqid = f"{repo}#{num:04d}"

            meta = _extract_metadata(entry)
            if not _is_in_flight(meta["status"]):
                continue

            adr_date = _parse_date(meta["date"])
            if adr_date is None:
                continue
            age = (today - adr_date).days
            if age < threshold_days:
                continue

            # defer 豁免機制
            defer_dt = _parse_date(meta.get("defer_until", ""))
            deferred = defer_dt is not None and defer_dt >= today

            severity = "critical" if age >= critical_days else "stale"
            stale.append(StaleADR(
                repo=repo,
                fqid=fqid,
                title=meta["title"],
                status=meta["status"],
                date=meta["date"],
                age_days=age,
                severity=severity,
                deferred=deferred,
                defer_until=meta.get("defer_until", ""),
            ))

    return sorted(stale, key=lambda s: -s.age_days)


def render_text(stale: list[StaleADR], threshold: int, critical: int) -> str:
    if not stale:
        return f"✅ ADR Stale Check passed (no in-flight ADR > {threshold}d)"

    lines = [f"⚠️  ADR Stale Check — {len(stale)} item(s) require quarterly sweep"]
    lines.append(f"   threshold: {threshold}d   critical: {critical}d")
    lines.append("")

    by_severity = {"critical": [], "stale": []}
    for s in stale:
        if s.deferred:
            continue
        by_severity[s.severity].append(s)

    if by_severity["critical"]:
        lines.append("🔴 CRITICAL（≥ {}d，需強制決議）：".format(critical))
        for s in by_severity["critical"]:
            lines.append(f"   {s.fqid}  {s.age_days:3d}d  [{s.status}]  {s.title[:60]}")
        lines.append("")

    if by_severity["stale"]:
        lines.append("🟡 STALE（≥ {}d 待結算）：".format(threshold))
        for s in by_severity["stale"]:
            lines.append(f"   {s.fqid}  {s.age_days:3d}d  [{s.status}]  {s.title[:60]}")
        lines.append("")

    deferred = [s for s in stale if s.deferred]
    if deferred:
        lines.append("ℹ️  Deferred（已標 defer_until，豁免）：")
        for s in deferred:
            lines.append(f"   {s.fqid}  defer_until={s.defer_until}  {s.title[:60]}")
        lines.append("")

    lines.append("解決方式（per ADR-0029 Governance Lessons + roadmap #15）：")
    lines.append("  - accepted：在 ADR body 加「**接受日期**: YYYY-MM-DD」")
    lines.append("  - rejected：把狀態改 rejected 並補 rationale 段")
    lines.append("  - defer：在 ADR body 加「**defer_until**: YYYY-MM-DD」（最多延 90d）")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="ADR stale check (per ADR-0029 / roadmap #15)")
    parser.add_argument("--threshold", type=int, default=90,
                        help="stale threshold in days (default 90)")
    parser.add_argument("--critical", type=int, default=180,
                        help="critical threshold in days (default 180)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--ci", action="store_true",
                        help="exit 1 if any non-deferred stale found")
    args = parser.parse_args()

    stale = scan_stale(args.threshold, args.critical)

    if args.json:
        print(json.dumps([asdict(s) for s in stale], ensure_ascii=False, indent=2))
    else:
        print(render_text(stale, args.threshold, args.critical))

    if args.ci:
        non_deferred = [s for s in stale if not s.deferred]
        return 1 if non_deferred else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
