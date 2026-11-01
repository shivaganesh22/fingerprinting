"""Rate limiting and domain concurrency throttling."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from urllib.parse import urlparse


def extract_domain_key(url_or_domain: str) -> str:
    """Extract domain key (hostname) for rate-limiting purposes."""
    if "://" in url_or_domain:
        netloc = urlparse(url_or_domain).netloc
        return netloc.split(":")[0].lower()
    return url_or_domain.split("/")[0].split(":")[0].lower()


class RateLimiter:
    """Enforces per-domain delays and caps global concurrency."""

    def __init__(self, min_domain_delay_seconds: float = 5.0, global_concurrency: int = 4):
        self.min_domain_delay = min_domain_delay_seconds
        self.global_concurrency = global_concurrency
        self._last_access: dict[str, float] = defaultdict(float)
        self._semaphore: asyncio.Semaphore | None = None
        self._lock = asyncio.Lock()

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.global_concurrency)
        return self._semaphore

    async def acquire_domain(
        self, domain_or_url: str, override_delay: float | None = None
    ) -> float:
        """Wait if needed to satisfy the per-domain delay, and update last access timestamp.

        Returns the seconds waited.
        """
        domain = extract_domain_key(domain_or_url)
        delay = override_delay if override_delay is not None else self.min_domain_delay

        waited = 0.0
        async with self._lock:
            now = time.monotonic()
            last_time = self._last_access[domain]
            elapsed = now - last_time
            if elapsed < delay:
                to_wait = delay - elapsed
                waited = to_wait

        if waited > 0:
            await asyncio.sleep(waited)

        async with self._lock:
            self._last_access[domain] = time.monotonic()

        return waited

    def wait_sync(self, domain_or_url: str, override_delay: float | None = None) -> float:
        """Synchronous delay helper for scripts or sync runners."""
        domain = extract_domain_key(domain_or_url)
        delay = override_delay if override_delay is not None else self.min_domain_delay

        now = time.monotonic()
        last_time = self._last_access[domain]
        elapsed = now - last_time
        waited = 0.0
        if elapsed < delay:
            waited = delay - elapsed
            time.sleep(waited)
        self._last_access[domain] = time.monotonic()
        return waited
