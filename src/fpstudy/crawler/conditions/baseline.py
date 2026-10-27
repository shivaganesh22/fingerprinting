"""Baseline condition: Stock browser with no defensive modifications."""

from __future__ import annotations

from typing import Any

from playwright.async_api import Browser, BrowserContext

from fpstudy.crawler.conditions.base import BaseCondition, register_condition


@register_condition("baseline")
class BaselineCondition(BaseCondition):
    """Stock browser condition establishing baseline fingerprinting prevalence."""

    async def prepare(self) -> None:
        """No external rules or files needed for baseline."""
        pass

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Create standard isolated browser context."""
        return await browser.new_context(**context_options)

    async def teardown(self) -> None:
        """No persistent resources to clean up."""
        pass

    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Canary check: verify browser context creates normally and executes JS."""
        ctx = await browser.new_context()
        try:
            page = await ctx.new_page()
            res = await page.evaluate("() => 1 + 1")
            return {
                "passed": res == 2,
                "details": {"eval_result": res, "message": "Baseline context functional"},
            }
        finally:
            await ctx.close()
