"""
ck-observability-bridge tools — Hermes skill loader entry

依 ADR-0022 規範；只讀紀律；observer 姿態。
3 Loki tools 完整實作；prom/grafana/alertmanager 5 tools 留 stub。

部署：CK_AaaP session 採納後複製到
  platform/services/docs/hermes-skills/ck-observability-bridge/tools.py
runtime 安裝：~/.hermes/skills/ck-observability-bridge/tools.py
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

# ── Environment ────────────────────────────────────────────
LOKI_URL = os.environ.get("OBS_LOKI_URL", "http://host.docker.internal:13100")
PROM_URL = os.environ.get("OBS_PROMETHEUS_URL", "http://host.docker.internal:19090")
GRAFANA_URL = os.environ.get("OBS_GRAFANA_URL", "http://host.docker.internal:13000")
ALERT_URL = os.environ.get("OBS_ALERTMANAGER_URL", "http://host.docker.internal:19093")
TIMEOUT_S = float(os.environ.get("OBS_TIMEOUT_S", "45"))
DEFAULT_WINDOW = os.environ.get("OBS_DEFAULT_WINDOW", "1h")
SAFE_MODE = os.environ.get("OBS_SAFE_MODE", "true").lower() == "true"

ERROR_PATTERN = r'(?i)(error|exception|traceback|fatal|panic|critical)'
NOISE_CONTAINERS = {"ck-platform-node-exporter"}  # metrics scrape errors are normal


# ── HTTP helpers ───────────────────────────────────────────
def _http_get_json(url: str, params: dict[str, Any] | None = None) -> dict:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ns(seconds_ago: float) -> str:
    return str(int((time.time() - seconds_ago) * 1_000_000_000))


def _parse_window(window: str) -> int:
    """Parse window string like '1h', '24h', '30m' into seconds."""
    m = re.match(r"^(\d+)([smhd])$", window.strip())
    if not m:
        return 3600
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _err(code: str, msg: str, **extra) -> str:
    payload = {"error": code, "tool": extra.pop("tool", ""), "message": msg, **extra}
    return json.dumps(payload, ensure_ascii=False)


# ── Tool 1: obs_loki_query ─────────────────────────────────
def obs_loki_query(selector: str, window: str = "", filter: str = "", limit: int = 50) -> str:
    """
    查某 container / project / job 在指定時間窗的日誌。

    Args:
        selector: LogQL stream selector，e.g. '{container="ck_missive_backend"}'
        window: 時間窗，e.g. '1h' / '6h' / '24h'（預設 OBS_DEFAULT_WINDOW）
        filter: 額外文字 regex filter
        limit: 最多回傳幾條（default 50）
    """
    win = window or DEFAULT_WINDOW
    seconds = _parse_window(win)
    logql = selector
    if filter:
        logql += f' |~ "{filter}"'
    try:
        data = _http_get_json(
            f"{LOKI_URL}/loki/api/v1/query_range",
            {"query": logql, "start": _ns(seconds), "end": _ns(0), "limit": str(limit)},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        return _err("loki_http_error", body, tool="obs_loki_query", status=e.code)
    except urllib.error.URLError as e:
        return _err("loki_unreachable", str(e.reason), tool="obs_loki_query", url=LOKI_URL)

    streams = []
    top_errors: list[str] = []
    error_re = re.compile(ERROR_PATTERN)
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        ident = labels.get("container") or labels.get("service") or "<no-label>"
        entries = []
        for ts_ns, line in stream.get("values", []):
            entries.append({
                "ts": int(ts_ns) // 1_000_000_000,
                "line": line[:200],
            })
            if error_re.search(line) and len(top_errors) < 10:
                top_errors.append(f"{ident}: {line[:160]}")
        streams.append({"labels": labels, "entries_count": len(entries), "sample": entries[:3]})

    return json.dumps({
        "selector": selector,
        "window": win,
        "streams_count": len(streams),
        "streams": streams,
        "top_errors": top_errors,
    }, ensure_ascii=False)


# ── Tool extension: obs_loki_errors（retro §3.F） ──────────
def obs_loki_errors(window: str = "24h", exclude_noise: bool = True) -> str:
    """
    近 N 小時 ERROR-pattern 統計（by container）。預設排除 metrics scrape noise。

    Args:
        window: 時間窗，e.g. '1h' / '24h'
        exclude_noise: 是否排除已知噪音來源（ck-platform-node-exporter 等）
    """
    seconds = _parse_window(window)
    logql = f'{{container=~".+"}} |~ "{ERROR_PATTERN}"'
    try:
        data = _http_get_json(
            f"{LOKI_URL}/loki/api/v1/query_range",
            {"query": logql, "start": _ns(seconds), "end": _ns(0), "limit": "5000"},
        )
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        return _err("loki_unreachable", str(e), tool="obs_loki_errors")

    counter: Counter[str] = Counter()
    samples: dict[str, str] = {}
    excluded_count = 0
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        ident = labels.get("container") or "<no-container>"
        if exclude_noise and ident in NOISE_CONTAINERS:
            excluded_count += sum(1 for _ in stream.get("values", []))
            continue
        for _ts_ns, line in stream.get("values", []):
            counter[ident] += 1
            samples.setdefault(ident, line[:160].strip())

    return json.dumps({
        "window": window,
        "total_errors": sum(counter.values()),
        "distinct_containers": len(counter),
        "excluded_noise_count": excluded_count if exclude_noise else 0,
        "by_container": [
            {"container": c, "count": n, "sample": samples.get(c, "")}
            for c, n in counter.most_common()
        ],
    }, ensure_ascii=False)


# ── Tool extension: obs_loki_briefing（retro §3.F） ────────
def obs_loki_briefing(window: str = "24h") -> str:
    """
    Markdown briefing 格式：近 N 小時 ERROR 摘要 + 紀律提醒。
    給 cron daily-closing 寫入 wiki/briefings/ 用。
    """
    raw = obs_loki_errors(window=window, exclude_noise=True)
    parsed = json.loads(raw)
    if "error" in parsed:
        return raw  # forward error as-is

    today = time.strftime("%Y-%m-%d")
    now = time.strftime("%H:%M:%S")
    lines: list[str] = []
    lines.append(f"# 觀測 Briefing — 近 {window} ERROR")
    lines.append("")
    lines.append(f"產生時間：{today} {now}（Taipei） | 排除噪音：{parsed['excluded_noise_count']} 行")
    lines.append("")

    by_c = parsed["by_container"]
    if not by_c:
        lines.append("> 靜默期：本時段無偵測到 ERROR-level pattern（已排除已知噪音）。")
        return json.dumps({"markdown": "\n".join(lines)}, ensure_ascii=False)

    lines.append(f"## 摘要")
    lines.append("")
    lines.append(f"- 共 {parsed['total_errors']} 條 ERROR-pattern 訊息，分散於 {parsed['distinct_containers']} 個容器")
    lines.append("- 前三大來源：")
    for item in by_c[:3]:
        lines.append(f"  - `{item['container']}` ×{item['count']}")
    lines.append("")
    lines.append("## 各容器詳情")
    lines.append("")
    for item in by_c:
        lines.append(f"### `{item['container']}` ×{item['count']}")
        lines.append("")
        lines.append(f"  - `{item['sample']}`")
        lines.append("")
    lines.append("## 紀律提醒")
    lines.append("")
    lines.append("- 本 briefing 僅彙整觀測；**不**自動干預（restart / kill）")
    lines.append("- 業務含義由對應 agent 解讀")
    lines.append("- 若需根因，建議：`docker logs <container> --tail 200 --since 1h`")

    return json.dumps({"markdown": "\n".join(lines)}, ensure_ascii=False)


# ── Stubs for ADR-0022 Tools 2-6 ───────────────────────────
def obs_prom_query(query: str, window: str = "", step: str = "") -> str:
    return _err("not_implemented", "obs_prom_query is stub; ADR-0022 Tool 2 pending",
                tool="obs_prom_query")


def obs_grafana_dashboard_url(dashboard_id: str = "", dashboard_name: str = "",
                              variables: dict | None = None) -> str:
    return _err("not_implemented", "obs_grafana_dashboard_url is stub; ADR-0022 Tool 3 pending",
                tool="obs_grafana_dashboard_url")


def obs_alertmanager_silence(matchers: list, duration: str, comment: str) -> str:
    if SAFE_MODE:
        return json.dumps({
            "dry_run": True,
            "would_silence": {"matchers": matchers, "duration": duration, "comment": comment},
            "note": "OBS_SAFE_MODE=true; set false + confirm to actually silence",
        }, ensure_ascii=False)
    return _err("not_implemented", "obs_alertmanager_silence write path is stub; ADR-0022 Tool 4 pending",
                tool="obs_alertmanager_silence")


def obs_container_health(project_prefix: str) -> str:
    return _err("not_implemented", "obs_container_health is stub; ADR-0022 Tool 5 pending",
                tool="obs_container_health")


def obs_alert_active(project_filter: str = "", severity: str = "") -> str:
    return _err("not_implemented", "obs_alert_active is stub; ADR-0022 Tool 6 pending",
                tool="obs_alert_active")


# ── Health check ───────────────────────────────────────────
def _check_loki() -> bool:
    try:
        with urllib.request.urlopen(f"{LOKI_URL}/ready", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _check_prometheus() -> bool:
    try:
        with urllib.request.urlopen(f"{PROM_URL}/-/ready", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


# ── Hermes skill loader entry ──────────────────────────────
def register_all(registry) -> int:
    """
    依 hermes-skill-contract-v2 §2.2 register_all 契約註冊 8 tools.
    Loki 3 tools 完整實作；其他 5 為 stub 但仍註冊（讓 LLM 看到 description）。
    """
    count = 0
    for fn, desc in [
        (obs_loki_query,
         "Query Loki by LogQL stream selector for given time window. Returns streams + top_errors."),
        (obs_loki_errors,
         "Count ERROR-pattern lines per container in last window; excludes known noise sources by default."),
        (obs_loki_briefing,
         "Markdown briefing of recent ERROR pattern; for daily cron summary."),
        (obs_prom_query,
         "Prometheus instant/range query (STUB; ADR-0022 Tool 2 pending)."),
        (obs_grafana_dashboard_url,
         "Build Grafana dashboard deep-link URL (STUB; ADR-0022 Tool 3 pending)."),
        (obs_alertmanager_silence,
         "Silence an alert (DRY-RUN by default via OBS_SAFE_MODE; ADR-0022 Tool 4)."),
        (obs_container_health,
         "List container health by project prefix (STUB; ADR-0022 Tool 5 pending)."),
        (obs_alert_active,
         "List currently firing/pending Alertmanager alerts (STUB; ADR-0022 Tool 6 pending)."),
    ]:
        registry.register(
            name=fn.__name__,
            description=desc,
            handler=fn,
            check_fn=_check_loki if fn.__name__.startswith("obs_loki_") else _check_prometheus,
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
