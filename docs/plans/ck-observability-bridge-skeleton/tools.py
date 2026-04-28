"""
ck-observability-bridge tools — Hermes skill loader entry

依 ADR-0022 規範；只讀紀律；observer 姿態。
8 tools 全實作；alertmanager_silence 預設 SAFE_MODE dry-run。

部署：CK_AaaP session 採納後複製到
  platform/services/docs/hermes-skills/ck-observability-bridge/tools.py
runtime 安裝：~/.hermes/skills/ck-observability-bridge/tools.py
"""
from __future__ import annotations

import json
import os
import re
import statistics
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
GRAFANA_TOKEN = os.environ.get("OBS_GRAFANA_TOKEN", "")
TIMEOUT_S = float(os.environ.get("OBS_TIMEOUT_S", "45"))
DEFAULT_WINDOW = os.environ.get("OBS_DEFAULT_WINDOW", "1h")
SAFE_MODE = os.environ.get("OBS_SAFE_MODE", "true").lower() == "true"

ERROR_PATTERN = r'(?i)(error|exception|traceback|fatal|panic|critical)'
NOISE_CONTAINERS = {"ck-platform-node-exporter"}  # metrics scrape errors are normal


# ── HTTP helpers ───────────────────────────────────────────
def _http_get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return data


def _http_post_form(url: str, params: dict[str, Any]) -> dict[str, Any]:
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return data


def _http_post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return data


def _ns(seconds_ago: float) -> str:
    return str(int((time.time() - seconds_ago) * 1_000_000_000))


def _parse_window(window: str) -> int:
    """Parse window string like '1h', '24h', '30m' into seconds."""
    m = re.match(r"^(\d+)([smhd])$", window.strip())
    if not m:
        return 3600
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _err(code: str, msg: str, **extra: Any) -> str:
    payload: dict[str, Any] = {
        "error": code,
        "tool": extra.pop("tool", ""),
        "message": msg,
        **extra,
    }
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

    streams: list[dict[str, Any]] = []
    top_errors: list[str] = []
    error_re = re.compile(ERROR_PATTERN)
    for stream in data.get("data", {}).get("result", []):
        labels = stream.get("stream", {})
        ident = labels.get("container") or labels.get("service") or "<no-label>"
        entries: list[dict[str, Any]] = []
        for ts_ns, line in stream.get("values", []):
            entries.append({"ts": int(ts_ns) // 1_000_000_000, "line": line[:200]})
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
        return raw

    today = time.strftime("%Y-%m-%d")
    now = time.strftime("%H:%M:%S")
    lines: list[str] = []
    lines.append(f"# 觀測 Briefing — 近 {window} ERROR")
    lines.append("")
    lines.append(
        f"產生時間：{today} {now}（Taipei） | 排除噪音：{parsed['excluded_noise_count']} 行"
    )
    lines.append("")

    by_c = parsed["by_container"]
    if not by_c:
        lines.append("> 靜默期：本時段無偵測到 ERROR-level pattern（已排除已知噪音）。")
        return json.dumps({"markdown": "\n".join(lines)}, ensure_ascii=False)

    lines.append("## 摘要")
    lines.append("")
    lines.append(
        f"- 共 {parsed['total_errors']} 條 ERROR-pattern 訊息，"
        f"分散於 {parsed['distinct_containers']} 個容器"
    )
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


# ── Tool 2: obs_prom_query ─────────────────────────────────
def obs_prom_query(query: str, window: str = "", step: str = "15s") -> str:
    """
    PromQL range query with summary (min/max/avg/last/trend).

    Args:
        query: PromQL expression, e.g. 'rate(container_cpu_usage_seconds_total[5m])'
        window: e.g. '1h' / '24h'（預設 OBS_DEFAULT_WINDOW）
        step: query step (default '15s')
    """
    win = window or DEFAULT_WINDOW
    seconds = _parse_window(win)
    end = time.time()
    start = end - seconds
    try:
        data = _http_post_form(
            f"{PROM_URL}/api/v1/query_range",
            {"query": query, "start": str(start), "end": str(end), "step": step},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        return _err("prom_http_error", body, tool="obs_prom_query", status=e.code)
    except urllib.error.URLError as e:
        return _err("prom_unreachable", str(e.reason), tool="obs_prom_query", url=PROM_URL)

    if data.get("status") != "success":
        return _err("prom_query_failed", data.get("error", "unknown"),
                    tool="obs_prom_query", errorType=data.get("errorType"))

    series_summary: list[dict[str, Any]] = []
    for series in data.get("data", {}).get("result", []):
        values = [float(v[1]) for v in series.get("values", [])
                  if v[1] not in ("NaN", "+Inf", "-Inf")]
        if not values:
            continue
        last = values[-1]
        first = values[0]
        trend = "flat"
        if last > first * 1.1:
            trend = "rising"
        elif last < first * 0.9:
            trend = "falling"
        series_summary.append({
            "metric": series.get("metric", {}),
            "samples": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.fmean(values),
            "first": first,
            "last": last,
            "trend": trend,
        })

    return json.dumps({
        "query": query,
        "window": win,
        "step": step,
        "series_count": len(series_summary),
        "series": series_summary[:50],
    }, ensure_ascii=False)


# ── Tool 3: obs_grafana_dashboard_url ──────────────────────
def obs_grafana_dashboard_url(
    dashboard_id: str = "",
    dashboard_name: str = "",
    variables: dict[str, Any] | None = None,
) -> str:
    """
    Build Grafana dashboard deep-link URL.

    Args:
        dashboard_id: dashboard UID (preferred)
        dashboard_name: dashboard slug/title (fallback search)
        variables: dict of template var values, e.g. {"container": "ck_missive_backend"}
    """
    if not dashboard_id and not dashboard_name:
        return _err("missing_arg",
                    "Provide either dashboard_id (UID) or dashboard_name",
                    tool="obs_grafana_dashboard_url")

    headers = {"Authorization": f"Bearer {GRAFANA_TOKEN}"} if GRAFANA_TOKEN else {}

    if not dashboard_id and dashboard_name:
        try:
            results = _http_get_json(
                f"{GRAFANA_URL}/api/search",
                {"query": dashboard_name, "type": "dash-db"},
                headers=headers,
            )
        except urllib.error.HTTPError as e:
            return _err("grafana_http_error", str(e.code),
                        tool="obs_grafana_dashboard_url", status=e.code)
        except urllib.error.URLError as e:
            return _err("grafana_unreachable", str(e.reason),
                        tool="obs_grafana_dashboard_url", url=GRAFANA_URL)
        items = results if isinstance(results, list) else results.get("results", [])
        if not items:
            return _err("not_found", f"No dashboard matched '{dashboard_name}'",
                        tool="obs_grafana_dashboard_url")
        dashboard_id = items[0].get("uid", "")
        dashboard_name = items[0].get("title", dashboard_name)

    try:
        meta = _http_get_json(
            f"{GRAFANA_URL}/api/dashboards/uid/{dashboard_id}",
            headers=headers,
        )
    except urllib.error.HTTPError as e:
        return _err("grafana_http_error", "dashboard fetch failed",
                    tool="obs_grafana_dashboard_url", status=e.code)
    except urllib.error.URLError as e:
        return _err("grafana_unreachable", str(e.reason),
                    tool="obs_grafana_dashboard_url")

    dash = meta.get("dashboard", {})
    title = dash.get("title", dashboard_name or dashboard_id)
    url_path = meta.get("meta", {}).get("url", f"/d/{dashboard_id}")
    full_url = f"{GRAFANA_URL.rstrip('/')}{url_path}"

    if variables:
        qs = urllib.parse.urlencode({f"var-{k}": v for k, v in variables.items()})
        full_url += ("&" if "?" in full_url else "?") + qs

    return json.dumps({
        "dashboard_id": dashboard_id,
        "title": title,
        "url": full_url,
        "variables": variables or {},
    }, ensure_ascii=False)


# ── Tool 4: obs_alertmanager_silence ───────────────────────
def obs_alertmanager_silence(
    matchers: list[dict[str, Any]],
    duration: str = "1h",
    comment: str = "",
    mode: str = "query",
) -> str:
    """
    Silence an alert. SAFE_MODE=true forces dry-run regardless of mode.

    Args:
        matchers: list of {name, value, isRegex} per Alertmanager v2 schema
        duration: e.g. '1h', '30m'
        comment: required by Alertmanager
        mode: 'query' (dry-run preview) or 'run' (actually create silence)
    """
    seconds = _parse_window(duration)
    starts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ends = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + seconds))
    payload: dict[str, Any] = {
        "matchers": matchers,
        "startsAt": starts,
        "endsAt": ends,
        "createdBy": "hermes-ck-observability-bridge",
        "comment": comment or "silenced via Hermes",
    }

    if mode != "run" or SAFE_MODE:
        return json.dumps({
            "dry_run": True,
            "reason": "OBS_SAFE_MODE=true" if SAFE_MODE else "mode=query",
            "would_post": payload,
            "note": "set OBS_SAFE_MODE=false and pass mode='run' to actually silence",
        }, ensure_ascii=False)

    try:
        data = _http_post_json(f"{ALERT_URL}/api/v2/silences", payload)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        return _err("alertmanager_http_error", body,
                    tool="obs_alertmanager_silence", status=e.code)
    except urllib.error.URLError as e:
        return _err("alertmanager_unreachable", str(e.reason),
                    tool="obs_alertmanager_silence", url=ALERT_URL)

    return json.dumps({
        "silenceID": data.get("silenceID", ""),
        "endsAt": ends,
        "matchers": matchers,
    }, ensure_ascii=False)


# ── Tool 5: obs_container_health ───────────────────────────
def obs_container_health(project_prefix: str) -> str:
    """
    List container running state by project_prefix via cAdvisor metrics.

    Args:
        project_prefix: e.g. 'ck_missive_' / 'ck_pilemgmt_' / 'ck_tunnel_'
    """
    if not project_prefix:
        return _err("missing_arg", "project_prefix is required",
                    tool="obs_container_health")
    promql = f'container_last_seen{{name=~"{project_prefix}.*"}}'
    try:
        data = _http_post_form(f"{PROM_URL}/api/v1/query", {"query": promql})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        return _err("prom_http_error", body, tool="obs_container_health", status=e.code)
    except urllib.error.URLError as e:
        return _err("prom_unreachable", str(e.reason),
                    tool="obs_container_health", url=PROM_URL)

    if data.get("status") != "success":
        return _err("prom_query_failed", data.get("error", "unknown"),
                    tool="obs_container_health")

    now = time.time()
    containers: list[dict[str, Any]] = []
    for entry in data.get("data", {}).get("result", []):
        metric = entry.get("metric", {})
        name = metric.get("name", "")
        if not name:
            continue
        ts = float(entry.get("value", [0, 0])[1] or 0)
        age = now - ts
        state = "running" if age < 120 else "stale" if age < 600 else "down"
        containers.append({
            "container": name,
            "image": metric.get("image", ""),
            "last_seen_ago_s": int(age),
            "state": state,
        })
    containers.sort(key=lambda x: (x["state"] != "running", x["container"]))

    summary: Counter[str] = Counter(c["state"] for c in containers)
    return json.dumps({
        "project_prefix": project_prefix,
        "total": len(containers),
        "summary": dict(summary),
        "containers": containers,
    }, ensure_ascii=False)


# ── Tool 6: obs_alert_active ───────────────────────────────
def obs_alert_active(project_filter: str = "", severity: str = "") -> str:
    """
    List currently firing/pending Alertmanager alerts.

    Args:
        project_filter: substring match against alert labels (project / container / service)
        severity: 'critical' / 'warning' / 'info' / '' for all
    """
    try:
        alerts = _http_get_json(f"{ALERT_URL}/api/v2/alerts")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:200]
        return _err("alertmanager_http_error", body,
                    tool="obs_alert_active", status=e.code)
    except urllib.error.URLError as e:
        return _err("alertmanager_unreachable", str(e.reason),
                    tool="obs_alert_active", url=ALERT_URL)

    items = alerts if isinstance(alerts, list) else alerts.get("alerts", [])
    rows: list[dict[str, Any]] = []
    for a in items:
        labels = a.get("labels", {})
        if severity and labels.get("severity") != severity:
            continue
        if project_filter:
            haystack = " ".join(str(v) for v in labels.values())
            if project_filter not in haystack:
                continue
        rows.append({
            "alertname": labels.get("alertname", ""),
            "severity": labels.get("severity", ""),
            "state": a.get("status", {}).get("state", "active"),
            "starts_at": a.get("startsAt", ""),
            "summary": a.get("annotations", {}).get("summary", ""),
            "labels": labels,
        })

    by_severity: Counter[str] = Counter(r["severity"] for r in rows)
    return json.dumps({
        "project_filter": project_filter or None,
        "severity_filter": severity or None,
        "total": len(rows),
        "by_severity": dict(by_severity),
        "alerts": rows,
    }, ensure_ascii=False)


# ── Health check ───────────────────────────────────────────
def _check_loki() -> bool:
    try:
        with urllib.request.urlopen(f"{LOKI_URL}/ready", timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


def _check_prometheus() -> bool:
    try:
        with urllib.request.urlopen(f"{PROM_URL}/-/ready", timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


def _check_grafana() -> bool:
    try:
        with urllib.request.urlopen(f"{GRAFANA_URL}/api/health", timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


def _check_alertmanager() -> bool:
    try:
        with urllib.request.urlopen(f"{ALERT_URL}/-/ready", timeout=2) as r:
            return int(r.status) == 200
    except Exception:
        return False


# ── Hermes skill loader entry ──────────────────────────────
def register_all(registry: Any) -> int:
    """依 hermes-skill-contract-v2 §2.2 register_all 契約註冊 8 tools."""
    count = 0
    entries: list[tuple[Any, str, Any]] = [
        (obs_loki_query,
         "Query Loki by LogQL stream selector for given time window. Returns streams + top_errors.",
         _check_loki),
        (obs_loki_errors,
         "Count ERROR-pattern lines per container in last window; excludes known noise sources by default.",
         _check_loki),
        (obs_loki_briefing,
         "Markdown briefing of recent ERROR pattern; for daily cron summary.",
         _check_loki),
        (obs_prom_query,
         "Prometheus PromQL range query with min/max/avg/trend summary per series.",
         _check_prometheus),
        (obs_grafana_dashboard_url,
         "Build Grafana dashboard deep-link URL by UID or name; embeds template variables.",
         _check_grafana),
        (obs_alertmanager_silence,
         "Silence an alert (SAFE_MODE/mode=query forces dry-run; mode='run' creates silence).",
         _check_alertmanager),
        (obs_container_health,
         "List container running state by project prefix via cAdvisor container_last_seen.",
         _check_prometheus),
        (obs_alert_active,
         "List currently firing/pending Alertmanager alerts; filter by project substring + severity.",
         _check_alertmanager),
    ]
    for fn, desc, check in entries:
        registry.register(name=fn.__name__, description=desc, handler=fn, check_fn=check)
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
