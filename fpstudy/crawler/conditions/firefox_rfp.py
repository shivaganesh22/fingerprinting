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
        opts.pop("firefox_user_prefs", None)
        return await browser.new_context(**opts)

    async def teardown(self) -> None:
        """No teardown required."""
        pass

    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Canary check: verify screen dimension spoofing under Firefox RFP."""
        ctx = await self.launch_context(browser, {})
        try:
            page = await ctx.new_page()
            # Under RFP, screen resolution is spoofed to match window inner size
            info = await page.evaluate(
                "() => ({ inner_w: window.innerWidth, screen_w: screen.width })"
            )
            rfp_active = info["screen_w"] == info["inner_w"]
            return {
                "passed": rfp_active,
                "details": {
                    "screen_spoofed": rfp_active,
                    "screen_width": info["screen_w"],
                    "inner_width": info["inner_w"],
                },
            }
        except Exception as exc:
            return {
                "passed": False,
                "details": {"error": f"Firefox RFP check failed (Firefox installed?): {exc}"},
            }
        finally:
            await ctx.close()
