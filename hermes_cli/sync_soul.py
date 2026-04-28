"""Sync SOUL.md from CK_AaaP source-of-truth into running hermes-stack containers.

Default mode is dry-run + diff — actually writing the file requires --apply.
This is intentional: SOUL.md is a load-bearing prompt artifact and runtime
content can diverge from source intentionally (e.g. a different agent persona
deployed on shared hermes runtime).

Usage:
    python -m hermes_cli.sync_soul                    # dry-run + diff
    python -m hermes_cli.sync_soul --apply            # actually copy into containers
    python -m hermes_cli.sync_soul --source PATH      # override source
    python -m hermes_cli.sync_soul --containers a,b   # override target containers

Reads:    D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md (default)
Writes:   docker compose cp → ck-hermes-gateway:/opt/data/SOUL.md
                            → ck-hermes-web:/opt/data/SOUL.md
"""
from __future__ import annotations

import argparse
import difflib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SOURCE = Path(
    os.environ.get(
        "HERMES_SOUL_SOURCE",
        r"D:/CKProject/CK_AaaP/runbooks/hermes-stack/SOUL.md",
    )
)
DEFAULT_CONTAINERS = ("ck-hermes-gateway", "ck-hermes-web")
CONTAINER_PATH = "/opt/data/SOUL.md"


@dataclass
class SyncReport:
    container: str
    runtime_bytes: int
    source_bytes: int
    differs: bool
    runtime_excerpt: str  # first ~80 chars
    diff_lines: list[str]  # unified diff (truncated)
    applied: bool


def _read_runtime_soul(container: str) -> str:
    """cat the runtime SOUL.md from a container; returns empty string on failure."""
    cmd = ["docker", "exec", "-i", container, "sh", "-c", f"cat {CONTAINER_PATH}"]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", errors="replace")


def _docker_cp(source: Path, container: str) -> tuple[bool, str]:
    """Run `docker cp source container:CONTAINER_PATH`. Returns (ok, message)."""
    cmd = ["docker", "cp", str(source), f"{container}:{CONTAINER_PATH}"]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=30)
    except FileNotFoundError:
        return False, "docker CLI not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "docker cp timed out"
    if result.returncode != 0:
        msg = result.stderr.decode("utf-8", errors="replace").strip()
        return False, msg or f"docker cp exited {result.returncode}"
    return True, "ok"


def _diff(source_text: str, runtime_text: str, container: str) -> list[str]:
    diff = difflib.unified_diff(
        runtime_text.splitlines(keepends=False),
        source_text.splitlines(keepends=False),
        fromfile=f"{container}:{CONTAINER_PATH}",
        tofile="source-of-truth",
        lineterm="",
        n=2,
    )
    return list(diff)[:80]


def sync(
    source: Path,
    containers: list[str],
    apply: bool = False,
) -> list[SyncReport]:
    """Compute diff and (optionally) cp source SOUL.md into each container."""
    if not source.exists():
        raise FileNotFoundError(f"source SOUL.md not found: {source}")
    source_text = source.read_text(encoding="utf-8")
    source_bytes = len(source_text.encode("utf-8"))
    reports: list[SyncReport] = []
    for container in containers:
        runtime_text = _read_runtime_soul(container)
        runtime_bytes = len(runtime_text.encode("utf-8"))
        differs = runtime_text != source_text
        diff_lines = _diff(source_text, runtime_text, container) if differs else []
        applied = False
        if apply and differs:
            ok, msg = _docker_cp(source, container)
            applied = ok
            if not ok:
                diff_lines.append(f"[apply-error] {msg}")
        reports.append(SyncReport(
            container=container,
            runtime_bytes=runtime_bytes,
            source_bytes=source_bytes,
            differs=differs,
            runtime_excerpt=runtime_text[:80].replace("\n", " "),
            diff_lines=diff_lines,
            applied=applied,
        ))
    return reports


def _format_report(reports: list[SyncReport], apply: bool) -> str:
    lines: list[str] = []
    mode = "APPLY" if apply else "DRY-RUN"
    lines.append(f"[{mode}] hermes_cli.sync_soul")
    for r in reports:
        lines.append("")
        lines.append(f"── {r.container} ──")
        lines.append(f"  runtime: {r.runtime_bytes:>6} bytes  |  source: {r.source_bytes:>6} bytes")
        if not r.differs:
            lines.append("  [OK] in sync")
            continue
        lines.append(f"  [DRIFT] runtime excerpt: {r.runtime_excerpt!r}")
        if r.applied:
            lines.append("  [APPLIED] docker cp succeeded")
        elif apply:
            lines.append("  [FAIL] apply failed (see diff_lines)")
        else:
            lines.append("  [HINT] re-run with --apply to overwrite runtime")
        if r.diff_lines:
            lines.append("  --- unified diff (max 80 lines) ---")
            for dl in r.diff_lines:
                lines.append(f"    {dl}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # Windows cp950 console can choke on UTF-8 source content; force utf-8 output.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

    parser = argparse.ArgumentParser(
        prog="hermes_cli.sync_soul",
        description="Sync SOUL.md into running hermes-stack containers (default: dry-run + diff).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source SOUL.md path (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--containers",
        type=str,
        default=",".join(DEFAULT_CONTAINERS),
        help=f"Comma-separated container names (default: {','.join(DEFAULT_CONTAINERS)})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually docker cp the source into each container (default: dry-run only)",
    )
    args = parser.parse_args(argv)

    if not shutil.which("docker"):
        print("error: docker CLI not in PATH", file=sys.stderr)
        return 2

    containers = [c.strip() for c in args.containers.split(",") if c.strip()]
    if not containers:
        print("error: no containers given", file=sys.stderr)
        return 2

    try:
        reports = sync(args.source, containers, apply=bool(args.apply))
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    print(_format_report(reports, apply=bool(args.apply)))
    drift_unresolved = any(r.differs and not r.applied for r in reports)
    return 1 if (drift_unresolved and args.apply) else 0


if __name__ == "__main__":
    raise SystemExit(main())
