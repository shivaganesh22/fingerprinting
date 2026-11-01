"""Brave Shields condition utilizing the Brave browser binary."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext

from fpstudy.crawler.conditions.base import BaseCondition, register_condition

logger = logging.getLogger(__name__)

CANARY_TRACKER = "https://www.google-analytics.com/analytics.js"


@register_condition("brave_shields")
class BraveShieldsCondition(BaseCondition):
    """Brave browser with native Shields ad/tracker and fingerprint protections."""

    def __init__(self, definition: Any, study_config: Any):
        super().__init__(definition, study_config)
        self.executable_path = definition.executable_path or "/usr/bin/brave-browser"
        self._temp_user_data_dirs: list[str] = []

    async def prepare(self) -> None:
        """Verify existence of Brave executable."""
        if not Path(self.executable_path).is_file():
            raise FileNotFoundError(f"Brave executable not found at {self.executable_path}")

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Launch isolated context with Brave's compiled adblock cache loaded."""
        playwright = getattr(browser, "_playwright", None)
        if playwright is None:
            return await browser.new_context(**context_options)

        user_data_dir = tempfile.mkdtemp(prefix="brave_ctx_")
        self._temp_user_data_dirs.append(user_data_dir)

        # Seed Brave adblock cache and local state so Shields rules are active immediately
        src_profile = Path.home() / ".config/BraveSoftware/Brave-Browser"
        if src_profile.is_dir():
            target_default = Path(user_data_dir) / "Default"
            target_default.mkdir(parents=True, exist_ok=True)
            src_adblock = src_profile / "Default" / "adblock_cache"
            if src_adblock.is_dir():
                shutil.copytree(src_adblock, target_default / "adblock_cache", dirs_exist_ok=True)
            src_local_state = src_profile / "Local State"
            if src_local_state.is_file():
                shutil.copy2(src_local_state, Path(user_data_dir) / "Local State")

        options = {
            **context_options,
            "user_data_dir": user_data_dir,
            "executable_path": self.executable_path,
            "headless": True,
        }
        context = await playwright.chromium.launch_persistent_context(**options)
        return cast(BrowserContext, context)

    async def teardown(self) -> None:
        for directory in self._temp_user_data_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        self._temp_user_data_dirs.clear()

    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Canary check: verify that Brave binary exists and Shields blocks canary tracker."""
        exe = Path(self.executable_path)
        if not exe.is_file():
            return {
                "passed": False,
                "details": {
                    "executable_path": str(exe),
                    "installed": False,
                    "error": "Brave binary not found",
                },
            }

        ctx = await self.launch_context(browser, {})
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            blocked = False

            def _on_failed(req: Any) -> None:
                nonlocal blocked
                f = (req.failure or "").lower()
                if CANARY_TRACKER in req.url and any(
                    token in f for token in ("blocked_by_client", "blockedbyclient", "err_failed")
                ):
                    blocked = True

            page.on("requestfailed", _on_failed)
            await page.goto("about:blank")
            await page.evaluate(
                """(url) => {
                    const s = document.createElement('script');
                    s.src = url;
                    document.head.appendChild(s);
                }""",
                CANARY_TRACKER,
            )
            # Give short window for adblock engine to abort request
            import asyncio
            await asyncio.sleep(1.0)

            return {
                "passed": blocked,
                "details": {
                    "executable_path": str(exe),
                    "installed": True,
                    "canary_tracker": CANARY_TRACKER,
                    "shields_blocked": blocked,
                },
            }
        finally:
            await ctx.close()
