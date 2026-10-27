"""Unit tests for domain rate limiting and concurrency throttling."""

from __future__ import annotations

import time

import pytest

from fpstudy.ratelimit import RateLimiter, extract_domain_key


def test_extract_domain_key() -> None:
    assert extract_domain_key("https://foo.bar.com:8080/path") == "foo.bar.com"
    assert extract_domain_key("BAR.COM/some/page") == "bar.com"


@pytest.mark.asyncio
async def test_async_rate_limiter_delay() -> None:
    limiter = RateLimiter(min_domain_delay_seconds=0.1)

    t0 = time.monotonic()
    w1 = await limiter.acquire_domain("example.com")
    assert w1 == 0.0

    w2 = await limiter.acquire_domain("example.com")
    assert w2 > 0.08
    assert (time.monotonic() - t0) >= 0.09

    # Different domain should not wait
    w3 = await limiter.acquire_domain("other.org")
    assert w3 == 0.0


def test_sync_rate_limiter() -> None:
    limiter = RateLimiter(min_domain_delay_seconds=0.05)
    w1 = limiter.wait_sync("test.net")
    assert w1 == 0.0

    t0 = time.monotonic()
    w2 = limiter.wait_sync("test.net")
    assert w2 > 0.03
    assert (time.monotonic() - t0) >= 0.04
