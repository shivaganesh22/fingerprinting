"""Robots.txt compliance checking, caching, and politeness enforcement."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Fetches, parses, and caches robots.txt rules per origin."""

    def __init__(self, timeout_seconds: float = 10.0, cache_dir: str | None = None):
        self.timeout_seconds = timeout_seconds
        self.cache_dir = cache_dir
        self._parsers: dict[str, RobotFileParser | None] = {}
        self._crawl_delays: dict[str, float | None] = {}

    def get_origin(self, url: str) -> str:
        """Extract scheme://host[:port] origin from a URL."""
        parsed = urlparse(url)
        scheme = parsed.scheme or "http"
        netloc = parsed.netloc or parsed.path.split("/")[0]
        return f"{scheme}://{netloc}"

    def get_robots_url(self, url: str) -> str:
        """Construct the robots.txt URL for a given page URL."""
        origin = self.get_origin(url)
        return f"{origin}/robots.txt"

    def set_robots_content(self, origin: str, content: str) -> None:
        """Explicitly set robots.txt content in cache (useful for testing and offline mode)."""
        origin = self.get_origin(origin)
        rp = RobotFileParser()
        lines = content.splitlines()
        rp.parse(lines)
        self._parsers[origin] = rp
        try:
            raw_delay = rp.crawl_delay("*")
            delay: float | None = float(raw_delay) if raw_delay is not None else None
            if delay is None:
                # Fallback manual parse for crawl-delay if RobotFileParser didn't pick it up
                for line in lines:
                    if line.lower().startswith("crawl-delay:"):
                        delay = float(line.split(":")[1].strip())
                        break
            self._crawl_delays[origin] = delay
        except Exception:
            self._crawl_delays[origin] = None

    def fetch_robots(
        self,
        url: str,
        user_agent: str,
        client: httpx.Client | None = None,
    ) -> RobotFileParser | None:
        """Fetch and parse robots.txt for the given origin, or return cached parser."""
        origin = self.get_origin(url)
        if origin in self._parsers:
            return self._parsers[origin]

        robots_url = self.get_robots_url(url)
        close_client = False
        if client is None:
            client = httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": user_agent},
            )
            close_client = True

        rp = RobotFileParser()
        try:
            resp = client.get(robots_url)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                self._parsers[origin] = rp
                try:
                    delay = rp.crawl_delay(user_agent) or rp.crawl_delay("*")
                    self._crawl_delays[origin] = float(delay) if delay else None
                except Exception:
                    self._crawl_delays[origin] = None
            elif resp.status_code in (401, 403):
                # Access denied to robots.txt typically implies whole site disallowed
                rp.disallow_all = True  # type: ignore[attr-defined]
                self._parsers[origin] = rp
            else:
                # 404 or other status: allow all
                rp.allow_all = True  # type: ignore[attr-defined]
                self._parsers[origin] = rp
        except Exception as exc:
            logger.debug(f"Could not fetch robots.txt for {origin}: {exc}")
            # If robots.txt is unreachable due to connection error, allow with caution or treat as none
            rp.allow_all = True  # type: ignore[attr-defined]
            self._parsers[origin] = rp
        finally:
            if close_client:
                client.close()

        return self._parsers.get(origin)

    def is_allowed(
        self,
        url: str,
        user_agent: str,
        client: httpx.Client | None = None,
    ) -> bool:
        """Determine whether the crawler is permitted to visit url."""
        origin = self.get_origin(url)
        rp = self._parsers.get(origin)
        if rp is None:
            rp = self.fetch_robots(url, user_agent, client)

        if rp is None:
            return True

        if getattr(rp, "disallow_all", False):
            return False
        if getattr(rp, "allow_all", False):
            return True

        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        # Check for specific user agent, then fallback to research token or wildcard
        allowed = rp.can_fetch(user_agent, path)
        if not allowed and "fpstudy" in user_agent:
            # Check if specific fpstudy token is handled
            allowed = rp.can_fetch("fpstudy", path)
        return allowed

    def get_crawl_delay(self, url: str) -> float | None:
        """Retrieve any declared crawl-delay in seconds for the given origin."""
        origin = self.get_origin(url)
        return self._crawl_delays.get(origin)
