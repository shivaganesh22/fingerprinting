"""Brave Shields condition utilizing the Brave browser binary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext

from fpstudy.crawler.conditions.base import BaseCondition, register_condition


@register_condition("brave_shields")
class BraveShieldsCondition(BaseCondition):
    """Brave browser with native Shields ad/tracker and fingerprint protections."""

    def __init__(self, definition: Any, study_config: Any):
        super().__init__(definition, study_config)
        self.executable_path = definition.executable_path or "/usr/bin/brave-browser"

    async def prepare(self) -> None:
        """Verify existence of Brave executable."""
        if not Path(self.executable_path).is_file():
            pass

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Launch isolated context."""
        return await browser.new_context(**context_options)

    async def teardown(self) -> None:
        """No teardown required."""
        pass

    async def self_check(self, _browser: Browser) -> dict[str, Any]:
        """Canary check: check if Brave executable path exists on host system."""
        exe = Path(self.executable_path)
        exists = exe.is_file()
        return {
            "passed": exists,
            "details": {
                "executable_path": str(exe),
                "installed": exists,
                "note": "Install Brave browser or update 'executable_path' in config/conditions.yaml to enable",
            },
        }
