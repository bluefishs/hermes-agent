#!/usr/bin/env python3
"""Manual verification helper for the 5 ADR-0020 Phase 1 native tool bridges.

Pure-stdlib (urllib) probe of each bridge's primary endpoint, using the same
env var names and URL shapes as ``tools/{missive,observability,showcase,
pilemgmt}_tool.py`` plus the lvrland-local skill (dynamic-manifest only;
fallback tool not yet wired into hermes-agent — D3 audit). Designed for use
after a CK_AaaP / receiving-repo session has injected the env vars into
``hermes-stack/.env`` or the operator shell, so you can confirm at a glance
which bridges are reachable.

Usage::

    python scripts/verify-bridges.py [--bridge missive|observability|showcase|pilemgmt|lvrland|all]
    python scripts/verify-bridges.py            # equivalent to --bridge all
    python scripts/verify-bridges.py --bridge observability

Exit code 0 if every probed bridge with its env set responds 2xx;
non-zero if any probe fails (HTTP error / unreachable / non-2xx).

Env vars consulted (set the ones for bridges you want probed; missing env
vars are reported as SKIPPED, not as failures):

- MISSIVE_BASE_URL                      (+ MISSIVE_API_TOKEN optional)
- OBS_PROMETHEUS_URL
- OBS_LOKI_URL
- OBS_GRAFANA_URL             (+ OBS_GRAFANA_USER/PASS optional)
- OBS_ALERTMANAGER_URL
- SHOWCASE_BASE_URL                     (+ SHOWCASE_API_TOKEN optional)
- PILE_BASE_URL                         (PILE_API_TOKEN intentionally not used —
                                         pile_health is the only no-auth action)
- LVRLAND_BASE_URL                      (+ LVRLAND_API_TOKEN optional;
                                         probes /api/health; full tool list
                                         is dynamic via /api/agent/tools)

This script DOES NOT import the hermes tool registry; it talks HTTP directly
so ops can verify reachability independent of hermes runtime state.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

TIMEOUT_S = 10


@dataclass
class ProbeResult:
    bridge: str
    label: str
    status: str  # "OK" | "FAIL" | "SKIP"
    detail: str


def _http_get(url: str, headers: Optional[dict] = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")[:200]
    except urllib.error.URLError as e:
        return 0, f"URLError: {e.reason}"
    except TimeoutError:
        return 0, f"timeout after {TIMEOUT_S}s"


def _probe(
    bridge: str,
    label: str,
    env_key: str,
    path: str,
    extra_headers: Optional[dict] = None,
) -> ProbeResult:
    base = os.environ.get(env_key)
    if not base:
        return ProbeResult(bridge, label, "SKIP", f"{env_key} not set")
    base = base.rstrip("/")
    url = base + path
    code, body = _http_get(url, extra_headers)
    if 200 <= code < 300:
        return ProbeResult(bridge, label, "OK", f"{code} {url}")
    return ProbeResult(
        bridge,
        label,
        "FAIL",
        f"{code} {url} :: {body[:120]}",
    )


def probe_missive() -> ProbeResult:
    headers = {}
    token = os.environ.get("MISSIVE_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _probe("missive", "missive_health", "MISSIVE_BASE_URL", "/health", headers)


def probe_observability_prom() -> ProbeResult:
    # Use a trivial query so backend latency is minimal
    base = os.environ.get("OBS_PROMETHEUS_URL")
    if not base:
        return ProbeResult(
            "observability", "prometheus_query", "SKIP", "OBS_PROMETHEUS_URL not set"
        )
    base = base.rstrip("/")
    url = base + "/api/v1/query?query=" + urllib.parse.quote("up")
    code, body = _http_get(url)
    if 200 <= code < 300:
        return ProbeResult("observability", "prometheus_query", "OK", f"{code} {url}")
    return ProbeResult("observability", "prometheus_query", "FAIL", f"{code} {url} :: {body[:120]}")


def probe_observability_loki() -> ProbeResult:
    return _probe(
        "observability", "loki_labels", "OBS_LOKI_URL", "/loki/api/v1/labels"
    )


def probe_observability_grafana() -> ProbeResult:
    headers = {}
    user = os.environ.get("OBS_GRAFANA_USER")
    password = os.environ.get("OBS_GRAFANA_PASS")
    if user and password:
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"
    return _probe(
        "observability", "grafana_health", "OBS_GRAFANA_URL", "/api/health", headers
    )


def probe_observability_alert() -> ProbeResult:
    return _probe(
        "observability", "alerts_active", "OBS_ALERTMANAGER_URL", "/api/v2/alerts"
    )


def probe_showcase() -> ProbeResult:
    headers = {}
    token = os.environ.get("SHOWCASE_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _probe("showcase", "showcase_health", "SHOWCASE_BASE_URL", "/api/health", headers)


def probe_pilemgmt() -> ProbeResult:
    return _probe("pilemgmt", "pile_health", "PILE_BASE_URL", "/api/health")


def probe_lvrland() -> ProbeResult:
    headers = {}
    token = os.environ.get("LVRLAND_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _probe("lvrland", "lvrland_health", "LVRLAND_BASE_URL", "/api/health", headers)


PROBES_BY_BRIDGE = {
    "missive": [probe_missive],
    "observability": [
        probe_observability_prom,
        probe_observability_loki,
        probe_observability_grafana,
        probe_observability_alert,
    ],
    "showcase": [probe_showcase],
    "pilemgmt": [probe_pilemgmt],
    "lvrland": [probe_lvrland],
}


def run(bridge_filter: str) -> int:
    bridges = ["missive", "observability", "showcase", "pilemgmt", "lvrland"]
    if bridge_filter != "all":
        if bridge_filter not in PROBES_BY_BRIDGE:
            print(f"unknown bridge: {bridge_filter}", file=sys.stderr)
            return 2
        bridges = [bridge_filter]

    results: list[ProbeResult] = []
    for b in bridges:
        for probe in PROBES_BY_BRIDGE[b]:
            results.append(probe())

    width_bridge = max((len(r.bridge) for r in results), default=8)
    width_label = max((len(r.label) for r in results), default=14)
    for r in results:
        print(
            f"  [{r.status:<4}] {r.bridge:<{width_bridge}}  {r.label:<{width_label}}  "
            f"{r.detail}"
        )

    n_ok = sum(1 for r in results if r.status == "OK")
    n_fail = sum(1 for r in results if r.status == "FAIL")
    n_skip = sum(1 for r in results if r.status == "SKIP")
    print(f"\n  Summary: {n_ok} OK | {n_fail} FAIL | {n_skip} SKIP")
    return 0 if n_fail == 0 else 1


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--bridge",
        default="all",
        choices=["missive", "observability", "showcase", "pilemgmt", "lvrland", "all"],
        help="Which bridge to probe (default: all).",
    )
    args = p.parse_args(argv)
    return run(args.bridge)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
