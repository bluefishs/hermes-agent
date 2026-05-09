"""Tests for gateway/rate_limit.py."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from gateway.rate_limit import (
    RateLimitStore,
    TokenBucket,
    identity_from_request,
    is_exempt,
    make_middleware,
    reset_default_store_for_tests,
)


def test_token_bucket_allows_within_capacity():
    bucket = TokenBucket(capacity=3, refill_rate_per_sec=1.0)
    for _ in range(3):
        allowed, retry = bucket.try_acquire()
        assert allowed and retry == 0


def test_token_bucket_rejects_when_drained():
    bucket = TokenBucket(capacity=2, refill_rate_per_sec=1.0)
    bucket.try_acquire()
    bucket.try_acquire()
    allowed, retry = bucket.try_acquire()
    assert not allowed and retry > 0


def test_token_bucket_refills_over_time():
    bucket = TokenBucket(capacity=1, refill_rate_per_sec=10.0)
    assert bucket.try_acquire()[0] is True
    # Advance time manually
    bucket.last_refill -= 0.5  # simulate 0.5s elapsed; refills 5 tokens, capped at 1
    allowed, _ = bucket.try_acquire()
    assert allowed is True


def test_store_disabled_when_rpm_zero():
    store = RateLimitStore(rpm=0, burst=1)
    assert store.enabled is False


@pytest.mark.asyncio
async def test_store_acquire_disabled_always_allows():
    store = RateLimitStore(rpm=0, burst=1)
    for _ in range(100):
        allowed, _ = await store.acquire("anyone")
        assert allowed


@pytest.mark.asyncio
async def test_store_per_identity_isolation():
    store = RateLimitStore(rpm=60, burst=2)
    # Drain alice
    assert (await store.acquire("alice"))[0]
    assert (await store.acquire("alice"))[0]
    assert (await store.acquire("alice"))[0] is False
    # Bob still has full burst
    assert (await store.acquire("bob"))[0]
    assert (await store.acquire("bob"))[0]


def test_is_exempt_paths():
    assert is_exempt("/health")
    assert is_exempt("/health/detailed")
    assert is_exempt("/metrics")
    assert is_exempt("/v1/health")
    assert not is_exempt("/v1/chat/completions")
    assert not is_exempt("/api/jobs")


def test_identity_from_request_uses_bearer_token():
    req = SimpleNamespace(
        headers={"Authorization": "Bearer secret-token-value-1234567890"},
        remote="1.2.3.4",
    )
    ident = identity_from_request(req)
    assert ident.startswith("key:")
    assert "secret-token-val" in ident
    # Truncated — does not include the trailing portion
    assert "1234567890" not in ident


def test_identity_from_request_falls_back_to_xff():
    req = SimpleNamespace(
        headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"},
        remote="1.2.3.4",
    )
    assert identity_from_request(req) == "anon:9.9.9.9"


def test_identity_from_request_falls_back_to_remote():
    req = SimpleNamespace(headers={}, remote="5.6.7.8")
    assert identity_from_request(req) == "anon:5.6.7.8"


@pytest.mark.asyncio
async def test_middleware_returns_429_when_drained():
    pytest.importorskip("aiohttp")
    from aiohttp import web

    store = RateLimitStore(rpm=120, burst=1)
    mw = make_middleware(store)
    assert mw is not None

    async def handler(_request):
        return web.json_response({"ok": True})

    # Build a fake request via aiohttp's testing utilities
    from aiohttp.test_utils import make_mocked_request

    req = make_mocked_request("POST", "/v1/chat/completions",
                              headers={"Authorization": "Bearer key1"})
    resp1 = await mw(req, handler)
    assert resp1.status == 200

    req2 = make_mocked_request("POST", "/v1/chat/completions",
                               headers={"Authorization": "Bearer key1"})
    resp2 = await mw(req2, handler)
    assert resp2.status == 429
    assert "Retry-After" in resp2.headers
    assert int(resp2.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_middleware_skips_exempt_paths():
    pytest.importorskip("aiohttp")
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request

    store = RateLimitStore(rpm=60, burst=1)
    mw = make_middleware(store)

    async def handler(_request):
        return web.json_response({"ok": True})

    # Hit /metrics 10 times; never blocked
    for _ in range(10):
        req = make_mocked_request("GET", "/metrics",
                                  headers={"Authorization": "Bearer same"})
        resp = await mw(req, handler)
        assert resp.status == 200


@pytest.mark.asyncio
async def test_middleware_disabled_when_rpm_zero():
    pytest.importorskip("aiohttp")
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request

    store = RateLimitStore(rpm=0, burst=1)
    mw = make_middleware(store)

    async def handler(_request):
        return web.json_response({"ok": True})

    for _ in range(50):
        req = make_mocked_request("POST", "/v1/chat/completions",
                                  headers={"Authorization": "Bearer same"})
        resp = await mw(req, handler)
        assert resp.status == 200


def test_reset_default_store_picks_up_env(monkeypatch):
    monkeypatch.setenv("HERMES_GATEWAY_RATE_LIMIT_RPM", "30")
    monkeypatch.setenv("HERMES_GATEWAY_RATE_LIMIT_BURST", "5")
    reset_default_store_for_tests()
    from gateway.rate_limit import get_default_store
    store = get_default_store()
    assert store.rpm == 30
    assert store.burst == 5
    assert store.enabled
    # Clean up so other tests get a fresh state
    monkeypatch.delenv("HERMES_GATEWAY_RATE_LIMIT_RPM", raising=False)
    monkeypatch.delenv("HERMES_GATEWAY_RATE_LIMIT_BURST", raising=False)
    reset_default_store_for_tests()
