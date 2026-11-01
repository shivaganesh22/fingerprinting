"""Verified uBlock Origin Lite (uBOL) extension condition for Chromium."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext

from fpstudy.crawler.conditions.base import BaseCondition, register_condition

logger = logging.getLogger(__name__)

EXPECTED_UBOL_VERSION = "2026.1026.1812"
CANARY_PAGE = "https://example.com/"
CANARY_TRACKER = "https://www.google-analytics.com/analytics.js"


class UBlockLiteManager:
    """Validate a locally pinned uBOL unpacked extension; never create a mock."""

    def __init__(self, extension_dir: str | None = None):
        self.extension_dir = Path(extension_dir or "data/extensions/ubol/unpacked")

    def verify_extension(self) -> dict[str, Any]:
        manifest_path = self.extension_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"uBOL manifest not found at {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("manifest_version") != 3:
            raise ValueError("The configured extension is not a Manifest V3 extension")
        if manifest.get("version") != EXPECTED_UBOL_VERSION:
            raise ValueError(
                "Unexpected uBOL version: "
                f"expected {EXPECTED_UBOL_VERSION}, found {manifest.get('version')!r}"
            )
        rulesets = self.extension_dir / "rulesets" / "main"
        for required in ("ublock-filters.json", "easyprivacy.json"):
            if not (rulesets / required).is_file():
                raise FileNotFoundError(f"Required uBOL filter list is missing: {rulesets / required}")
        return {
            "version": manifest["version"],
            "manifest_version": manifest["manifest_version"],
            "extension_dir": str(self.extension_dir.resolve()),
        }

    def ensure_extension(self) -> bool:
        """Check if extension is present; copy from genuine unpacked uBOL directory if needed."""
        manifest = self.extension_dir / "manifest.json"
        if manifest.is_file():
            return True
        genuine_unpacked = Path("data/extensions/ubol/unpacked")
        if (genuine_unpacked / "manifest.json").is_file():
            self.extension_dir.mkdir(parents=True, exist_ok=True)
            for item in genuine_unpacked.iterdir():
                dst = self.extension_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
            return (self.extension_dir / "manifest.json").is_file()
        return False


# Backward-compatibility alias
UBlockManager = UBlockLiteManager


@register_condition("extension_ublock")
@register_condition("extension_ubol")
class UBlockLiteExtensionCondition(BaseCondition):
    """Load genuine uBOL in a persistent Chromium profile and verify a real block."""

    def __init__(self, definition: Any, study_config: Any):
        super().__init__(definition, study_config)
        self.manager = UBlockLiteManager(definition.extension_dir)
        self._temp_user_data_dirs: list[str] = []
        self._extension_metadata: dict[str, Any] = {}

    async def prepare(self) -> None:
        # Fail closed. A missing extension must never silently become a mock or
        # the separate built-in blocklist condition.
        self._extension_metadata = self.manager.verify_extension()

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        playwright = getattr(browser, "_playwright", None)
        if playwright is None:
            raise RuntimeError("Playwright handle unavailable for persistent extension context")

        user_data_dir = tempfile.mkdtemp(prefix="ubol_ctx_")
        self._temp_user_data_dirs.append(user_data_dir)
        extension_path = str(self.manager.extension_dir.resolve())
        options = {
            **context_options,
            "user_data_dir": user_data_dir,
            "headless": True,
            "channel": "chromium",
            "args": [
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ],
        }
        context = await playwright.chromium.launch_persistent_context(**options)
        return cast(BrowserContext, context)

    async def self_check(self, browser: Browser | None = None) -> dict[str, Any]:
        """Pass only if uBOL's worker loads and redirects a known tracker locally."""
        metadata = self.manager.verify_extension()
        if browser is None:
            return {"passed": True, "details": metadata}
        context = await self.launch_context(browser, {})
        try:
            workers = list(context.service_workers)
            if not workers:
                try:
                    workers = [await context.wait_for_event("serviceworker", timeout=10_000)]
                except Exception:
                    workers = list(context.service_workers)

            worker_urls = [worker.url for worker in workers]
            extension_worker_loaded = any(
                url.startswith("chrome-extension://") and "/js/background.js" in url
                for url in worker_urls
            )
            if not extension_worker_loaded:
                return {
                    "passed": False,
                    "details": {
                        **metadata,
                        "error": "uBOL background service worker did not load",
                        "service_workers": worker_urls,
                    },
                }

            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(CANARY_PAGE, wait_until="domcontentloaded", timeout=30_000)
            responses: list[Any] = []
            page.on("response", lambda response: responses.append(response))
            script_result = await page.evaluate(
                """(url) => new Promise((resolve) => {
                    const script = document.createElement('script');
                    script.src = url;
                    script.onload = () => resolve('loaded');
                    script.onerror = () => resolve('error');
                    document.head.appendChild(script);
                    setTimeout(() => resolve('timeout'), 10000);
                })""",
                CANARY_TRACKER,
            )

            redirect_chain: list[str] = []
            for response in responses:
                if response.url == CANARY_TRACKER:
                    request = response.request
                    while request is not None:
                        redirect_chain.append(request.url)
                        request = request.redirected_to
                    break

            redirected_to_extension = (
                bool(redirect_chain)
                and redirect_chain[0] == CANARY_TRACKER
                and any(url.startswith("chrome-extension://") for url in redirect_chain[1:])
            )
            passed = extension_worker_loaded and redirected_to_extension
            return {
                "passed": passed,
                "details": {
                    **metadata,
                    "extension_worker_loaded": extension_worker_loaded,
                    "service_workers": worker_urls,
                    "canary_tracker": CANARY_TRACKER,
                    "canary_script_result": script_result,
                    "redirected_to_extension_resource": redirected_to_extension,
                    "redirect_chain": redirect_chain,
                },
            }
        finally:
            await context.close()

    async def teardown(self) -> None:
        for directory in self._temp_user_data_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        self._temp_user_data_dirs.clear()


# Backward-compatibility alias
UBlockExtensionCondition = UBlockLiteExtensionCondition

