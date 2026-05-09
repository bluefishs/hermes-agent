"""Token-bucket rate limiter for the gateway HTTP server.

Disabled by default (HERMES_GATEWAY_RATE_LIMIT_RPM=0); set to a positive
integer to enable. Identity = Bearer key when present, else
`anon:<x-forwarded-for|remote>`. Health/metrics paths are always exempt.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenBucket:
    capacity: float
    refill_rate_per_sec: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def try_acquire(self, now: Optional[float] = None) -> tuple[bool, float]:
        """Attempt to consume one token.

        Returns (allowed, retry_after_seconds). retry_after is 0 when allowed.
        """
        if now is None:
            now = time.monotonic()
        elapsed = max(0.0, now - self.last_refill)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, 0.0
        deficit = 1.0 - self.tokens
        retry = deficit / self.refill_rate_per_sec if self.refill_rate_per_sec > 0 else 60.0
        return False, retry


class RateLimitStore:
    """Per-identity token buckets with opportunistic stale eviction.

    Single asyncio.Lock guards the dict; bucket math itself is fast so the
    critical section stays microseconds. For high-throughput deployments
    swap for shard-locked or Redis-backed implementation.
    """

    def __init__(
        self,
        rpm: int,
        burst: int,
        max_buckets: int = 10_000,
        idle_evict_seconds: float = 600.0,
    ) -> None:
        self.rpm = rpm
        self.burst = max(1, burst) if rpm > 0 else 1
        self.max_buckets = max_buckets
        self.idle_evict_seconds = idle_evict_seconds
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self.rpm > 0

    async def acquire(self, identity: str) -> tuple[bool, float]:
        if not self.enabled:
            return True, 0.0
        async with self._lock:
            bucket = self._buckets.get(identity)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=float(self.burst),
                    refill_rate_per_sec=self.rpm / 60.0,
                )
                self._buckets[identity] = bucket
                self._maybe_evict_locked()
            return bucket.try_acquire()

    def _maybe_evict_locked(self) -> None:
        if len(self._buckets) <= self.max_buckets:
            return
        cutoff = time.monotonic() - self.idle_evict_seconds
        stale = [k for k, b in self._buckets.items() if b.last_refill < cutoff]
        for k in stale:
            self._buckets.pop(k, None)


def _build_store_from_env() -> RateLimitStore:
    rpm = int(os.environ.get("HERMES_GATEWAY_RATE_LIMIT_RPM", "0") or 0)
    burst = int(os.environ.get("HERMES_GATEWAY_RATE_LIMIT_BURST", str(max(rpm, 1))))
    return RateLimitStore(rpm=rpm, burst=burst)


_default_store: Optional[RateLimitStore] = None


def get_default_store() -> RateLimitStore:
    global _default_store
    if _default_store is None:
        _default_store = _build_store_from_env()
    return _default_store


def reset_default_store_for_tests() -> None:
    """Force re-read of env vars; tests use this after monkeypatching."""
    global _default_store
    _default_store = None


_EXEMPT_PREFIXES = ("/health", "/v1/health", "/metrics")


def is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path == p for p in _EXEMPT_PREFIXES)


def identity_from_request(request) -> str:
    """Derive a stable rate-limit key.

    Bearer key (when present) gets its own bucket. Anonymous callers share
    a bucket per source IP.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return f"key:{token[:16]}"
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return f"anon:{fwd.split(',')[0].strip()}"
    remote = getattr(request, "remote", None) or "unknown"
    return f"anon:{remote}"


def make_middleware(store: Optional[RateLimitStore] = None):
    """Build an aiohttp middleware bound to the given (or default) store."""
    try:
        from aiohttp import web
    except ImportError:  # aiohttp optional in some deploys
        return None

    @web.middleware
    async def rate_limit_middleware(request, handler):
        s = store or get_default_store()
        if not s.enabled or is_exempt(request.path):
            return await handler(request)
        identity = identity_from_request(request)
        allowed, retry_after = await s.acquire(identity)
        if allowed:
            return await handler(request)
        headers = {
            "Retry-After": str(max(1, int(retry_after + 0.5))),
            "X-RateLimit-Limit": str(s.rpm),
        }
        return web.json_response(
            {
                "error": {
                    "code": "rate_limited",
                    "message": f"Rate limit exceeded ({s.rpm} req/min). Retry after {retry_after:.1f}s.",
                }
            },
            status=429,
            headers=headers,
        )

    return rate_limit_middleware
