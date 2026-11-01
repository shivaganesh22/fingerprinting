"""Unit tests for robots.txt parsing, caching, and politeness checks."""

from __future__ import annotations

from fpstudy.robots import RobotsChecker


def test_robots_allowed_and_disallowed() -> None:
    checker = RobotsChecker()
    robots_txt = """
User-agent: *
Disallow: /admin
Disallow: /private/
Allow: /private/public.html
Crawl-delay: 10
"""
    checker.set_robots_content("https://example.com", robots_txt)

    ua = "Mozilla/5.0 fpstudy-research/1.0"
    assert checker.is_allowed("https://example.com/", ua) is True
    assert checker.is_allowed("https://example.com/index.html", ua) is True
    assert checker.is_allowed("https://example.com/admin", ua) is False
    assert checker.is_allowed("https://example.com/admin/login", ua) is False
    assert checker.is_allowed("https://example.com/private/secret.pdf", ua) is False
    assert checker.is_allowed("https://example.com/private/public.html", ua) is True

    delay = checker.get_crawl_delay("https://example.com")
    assert delay == 10.0


def test_robots_full_disallow() -> None:
    checker = RobotsChecker()
    robots_txt = "User-agent: *\nDisallow: /\n"
    checker.set_robots_content("https://blocked.com", robots_txt)

    assert checker.is_allowed("https://blocked.com/", "test-agent") is False
    assert checker.is_allowed("https://blocked.com/page", "test-agent") is False
