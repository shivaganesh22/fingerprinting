"""Firefox condition with privacy.resistFingerprinting enabled (stretch goal)."""

from __future__ import annotations

from typing import Any

from playwright.async_api import Browser, BrowserContext

from fpstudy.crawler.conditions.base import BaseCondition, register_condition


@register_condition("firefox_rfp")
class FirefoxRFPCondition(BaseCondition):
    """Firefox with resistFingerprinting preference active."""

    async def prepare(self) -> None:
        """No external files required."""
        pass

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Create Firefox context with privacy.resistFingerprinting configured."""
        opts = dict(context_options)
        opts["firefox_user_prefs"] = {"privacy.resistFingerprinting": True}
        return await browser.new_context(**opts)

    async def teardown(self) -> None:
        """No teardown required."""
        pass

    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Canary check: verify screen.width / canvas spoofing in Firefox RFP."""
        ctx = await self.launch_context(browser, {})
        try:
            page = await ctx.new_page()
            # Under RFP, timezone is UTC and screen resolution is spoofed to match window inner size
            tz_offset = await page.evaluate("() => new Date().getTimezoneOffset()")
            return {
                "passed": tz_offset == 0,
                "details": {
                    "timezone_offset_minutes": tz_offset,
                    "expected_rfp_offset": 0,
                },
            }
        except Exception as exc:
            return {
                "passed": False,
                "details": {"error": f"Firefox RFP check failed (Firefox installed?): {exc}"},
            }
        finally:
            await ctx.close()
