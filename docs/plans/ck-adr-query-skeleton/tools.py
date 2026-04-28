"""
ck-adr-query tools — Hermes skill loader entry

依 retro §3.E 提案；只讀紀律；observer 姿態。
Variant B：讀 wiki/raw/adr-index.json（host cron 30min 萃取）。

部署：CK_AaaP session 採納後複製到
  platform/services/docs/hermes-skills/ck-adr-query/tools.py
runtime 安裝：~/.hermes/skills/ck-adr-query/tools.py
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# ── Environment ────────────────────────────────────────────
INDEX_PATH = Path(os.environ.get(
    "ADR_INDEX_PATH",
    "/opt/data/profiles/meta/wiki/raw/adr-index.json",
))
STALE_DAYS = 30


# ── Helpers ────────────────────────────────────────────────
def _load_index() -> dict[str, Any] | None:
    if not INDEX_PATH.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _stale_warn(index: dict[str, Any]) -> str | None:
    """Return warning message if index is older than STALE_DAYS, else None."""
    try:
        mtime = INDEX_PATH.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        if age_days > STALE_DAYS:
            return (
                f"⚠️ ADR index is {age_days:.0f} days old. "
                "Re-run host cron: python scripts/adr-query-poc.py index --pretty > ~/.hermes/profiles/meta/wiki/raw/adr-index.json"
            )
    except OSError:
        pass
    return None


def _err(code: str, msg: str, **extra: Any) -> str:
    return json.dumps({"error": code, "message": msg, **extra}, ensure_ascii=False)


def _wrap(payload: dict[str, Any], index: dict[str, Any]) -> str:
    warning = _stale_warn(index)
    if warning:
        payload["_warning"] = warning
    return json.dumps(payload, ensure_ascii=False)


# ── Tool 1: adr_search ─────────────────────────────────────
def adr_search(query: str, repo: str = "", lifecycle: str = "") -> str:
    """
    搜尋跨 repo ADR。回 FQID + title + lifecycle，依 hit count 排序。

    Args:
        query: 關鍵字（zh-TW 或英文皆可，case-insensitive）
        repo: 限定 repo (e.g. CK_Missive)；空字串 = 全部
        lifecycle: 限定 lifecycle (proposed/accepted/executing/deprecated)；空字串 = 全部
    """
    index = _load_index()
    if index is None:
        return _err("index_missing",
                    f"ADR index not found at {INDEX_PATH}; host cron may not have run yet",
                    path=str(INDEX_PATH))

    needle = query.lower()
    hits: list[dict[str, Any]] = []
    for adr in index.get("adrs", []):
        if repo and adr["repo"] != repo:
            continue
        if lifecycle and adr["lifecycle"] != lifecycle:
            continue
        text = (adr.get("title", "") + " " + adr.get("status", "")).lower()
        if needle in text:
            hits.append(adr)

    return _wrap({
        "query": query,
        "repo_filter": repo or None,
        "lifecycle_filter": lifecycle or None,
        "hits_count": len(hits),
        "hits": [
            {"fqid": a["fqid"], "title": a["title"], "lifecycle": a["lifecycle"], "date": a["date"]}
            for a in hits[:20]
        ],
    }, index)


# ── Tool 2: adr_list ───────────────────────────────────────
def adr_list(repo: str = "", lifecycle: str = "") -> str:
    """
    列出 ADR，可依 repo 與 lifecycle 過濾。

    Args:
        repo: 限定 repo；空字串 = 全部
        lifecycle: 限定 lifecycle；空字串 = 全部
    """
    index = _load_index()
    if index is None:
        return _err("index_missing", f"ADR index not found at {INDEX_PATH}")

    items = index.get("adrs", [])
    if repo:
        items = [a for a in items if a["repo"] == repo]
    if lifecycle:
        items = [a for a in items if a["lifecycle"] == lifecycle]

    return _wrap({
        "repo_filter": repo or None,
        "lifecycle_filter": lifecycle or None,
        "count": len(items),
        "items": [
            {"fqid": a["fqid"], "title": a["title"], "lifecycle": a["lifecycle"], "date": a["date"]}
            for a in items
        ],
    }, index)


# ── Tool 3: adr_lifecycle ──────────────────────────────────
def adr_lifecycle(fqid: str) -> str:
    """
    取單一 ADR 的 lifecycle 狀態。

    Args:
        fqid: e.g. "CK_Missive#0006"
    """
    index = _load_index()
    if index is None:
        return _err("index_missing", f"ADR index not found at {INDEX_PATH}")

    for adr in index.get("adrs", []):
        if adr["fqid"] == fqid:
            return _wrap({
                "fqid": adr["fqid"],
                "title": adr["title"],
                "status": adr["status"],
                "lifecycle": adr["lifecycle"],
                "date": adr["date"],
                "host_path": adr["path"],
            }, index)

    return _err("not_found", f"ADR {fqid} not in index",
                hint="Use adr_list to enumerate available FQIDs")


# ── Tool 4: adr_collisions ─────────────────────────────────
def adr_collisions() -> str:
    """
    列出跨 repo 編號碰撞（同號不同主題）。治理 first-class concern。
    """
    index = _load_index()
    if index is None:
        return _err("index_missing", f"ADR index not found at {INDEX_PATH}")

    return _wrap({
        "total_collisions": index.get("total_collisions", 0),
        "collisions": index.get("collisions", []),
        "advice": "Use FQID format <Repo>#<NNNN> when referencing across repos to avoid ambiguity",
    }, index)


# ── Tool 5: adr_read（stub） ───────────────────────────────
def adr_read(fqid: str) -> str:
    """
    讀 ADR 全文。

    ⚠️ 容器邊界限制：本 skill 在 hermes runtime 容器內，看不到 D:/CKProject。
    回 host path 引導使用者於 host 端讀取或進對應 repo session。
    """
    index = _load_index()
    if index is None:
        return _err("index_missing", f"ADR index not found at {INDEX_PATH}")

    for adr in index.get("adrs", []):
        if adr["fqid"] == fqid:
            return _wrap({
                "fqid": fqid,
                "title": adr["title"],
                "host_path": adr["path"],
                "note": (
                    "Full body not available inside hermes container. "
                    f"Read at host: cat {adr['path']}  "
                    f"or open in editor on host system."
                ),
            }, index)

    return _err("not_found", f"ADR {fqid} not in index")


# ── Health check ───────────────────────────────────────────
def _check_index() -> bool:
    return INDEX_PATH.exists() and _load_index() is not None


# ── Hermes skill loader entry ──────────────────────────────
def register_all(registry: Any) -> int:
    """依 hermes-skill-contract-v2 §2.2 register_all 契約註冊 5 tools."""
    count = 0
    for fn, desc in [
        (adr_search,
         "Search CK ecosystem ADRs by keyword. Filters: repo, lifecycle. Returns FQID + title + lifecycle."),
        (adr_list,
         "List ADRs filtered by repo and/or lifecycle. Returns FQID + title + date."),
        (adr_lifecycle,
         "Get lifecycle status of one ADR by FQID (e.g. 'CK_Missive#0006')."),
        (adr_collisions,
         "List ADR number collisions across repos (governance concern)."),
        (adr_read,
         "Read ADR full text (returns host path; container boundary limit)."),
    ]:
        registry.register(
            name=fn.__name__,
            description=desc,
            handler=fn,
            check_fn=_check_index,
        )
        count += 1
    return count


# ── CLI for local testing ──────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: tools.py <tool_name> [args...]")
        sys.exit(1)
    tool = sys.argv[1]
    fn = globals().get(tool)
    if not callable(fn):
        print(f"unknown tool: {tool}")
        sys.exit(1)
    print(fn(*sys.argv[2:]))
