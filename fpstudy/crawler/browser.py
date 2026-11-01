"""Browser management and context instantiation."""

from __future__ import annotations

import platform
from typing import Any

from playwright.async_api import Browser, Playwright, async_playwright

from fpstudy.config import StudyConfig
from fpstudy.crawler.conditions.base import BaseCondition, get_condition_class


class BrowserManager:
    """Manages browser lifecycle and deterministic context creation."""

    def __init__(self, config: StudyConfig, condition_name: str = "baseline"):
        self.config = config
        self.condition_name = condition_name
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._condition_instance: BaseCondition | None = None

    @property
    def condition(self) -> BaseCondition:
        """Get or initialize condition instance."""
        if self._condition_instance is None:
            cond_defs = self.config.conditions.conditions
            if self.condition_name not in cond_defs:
                raise ValueError(f"Unknown condition '{self.condition_name}' in config")
            definition = cond_defs[self.condition_name]
            cls = get_condition_class(self.condition_name)
            self._condition_instance = cls(definition, self.config)
        return self._condition_instance

    async def start(self) -> Browser:
        """Start Playwright and launch browser instance."""
        self._playwright = await async_playwright().start()
        # Set reference on playwright for persistent context fallback in extension conditions
        browser_type_name = self.condition.definition.browser_type
        launcher = getattr(self._playwright, browser_type_name, self._playwright.chromium)

        launch_kwargs: dict[str, Any] = {
            "headless": bool(self.condition.definition.headless is not False),
        }
        if self.condition.definition.executable_path:
            launch_kwargs["executable_path"] = self.condition.definition.executable_path

        self._browser = await launcher.launch(**launch_kwargs)
        # Store playwright reference on browser object for extension helper
        browser_obj: Any = self._browser
        browser_obj._playwright = self._playwright

        await self.condition.prepare()
        return self._browser

    def get_context_options(self) -> dict[str, Any]:
        """Produce deterministic context options across all conditions."""
        crawler_cfg = self.config.crawler
        return {
            "viewport": {
                "width": crawler_cfg.viewport.width,
                "height": crawler_cfg.viewport.height,
            },
            "locale": crawler_cfg.locale,
            "timezone_id": crawler_cfg.timezone_id,
            "user_agent": crawler_cfg.full_user_agent(),
            "ignore_https_errors": True,
        }

    async def create_context(self) -> Any:
        """Create a fresh isolated browser context for one site visit."""
        if self._browser is None:
            await self.start()
        assert self._browser is not None
        opts = self.get_context_options()
        return await self.condition.launch_context(self._browser, opts)

    async def close(self) -> None:
        """Clean up condition, browser, and playwright resources."""
        if self._condition_instance:
            await self._condition_instance.teardown()
            self._condition_instance = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def get_system_manifest(self) -> dict[str, Any]:
        """Capture browser and OS environment details for the run manifest."""
        version = self._browser.version if self._browser else "unknown"
        return {
            "browser_type": self.condition.definition.browser_type,
            "browser_version": version,
            "os_info": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python_version": platform.python_version(),
        }
