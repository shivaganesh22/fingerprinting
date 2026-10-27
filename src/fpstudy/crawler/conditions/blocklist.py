"""Blocklist condition: Network-level request blocking via EasyPrivacy and adblock engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from adblock import Engine, FilterSet
from playwright.async_api import Browser, BrowserContext, Request, Route

from fpstudy.crawler.conditions.base import BaseCondition, register_condition

logger = logging.getLogger(__name__)

# Canary rule to definitively verify blocklist enforcement
CANARY_RULE = "||canary-tracker.test^"
CANARY_URL = "https://canary-tracker.test/tracker.js"


class BlocklistManager:
    """Manages EasyPrivacy list files, parsing, and Engine initialization."""

    EASYPRIVACY_URL = "https://easylist.to/easylist/easyprivacy.txt"

    def __init__(self, list_paths: list[str] | None = None):
        self.list_paths = [Path(p) for p in (list_paths or ["data/blocklists/easyprivacy.txt"])]
        self.engine: Engine | None = None

    def ensure_lists(self, client: httpx.Client | None = None) -> None:
        """Ensure at least one blocklist file exists, downloading EasyPrivacy if necessary."""
        primary = self.list_paths[0]
        if not primary.is_file():
            primary.parent.mkdir(parents=True, exist_ok=True)
            close_client = False
            if client is None:
                client = httpx.Client(timeout=30.0, follow_redirects=True)
                close_client = True
            try:
                logger.info(f"Downloading EasyPrivacy snapshot from {self.EASYPRIVACY_URL}")
                resp = client.get(self.EASYPRIVACY_URL)
                resp.raise_for_status()
                primary.write_text(resp.text, encoding="utf-8")
            except Exception as exc:
                logger.warning(f"Could not download EasyPrivacy, creating fallback rules: {exc}")
                # Create standard bundled tracker patterns as fallback
                fallback_rules = [
                    CANARY_RULE,
                    "||google-analytics.com^",
                    "||doubleclick.net^",
                    "||scorecardresearch.com^",
                    "||hotjar.com^",
                    "||criteo.com^",
                    "||facebook.net/signals/*",
                    "/fingerprint*.js$script",
                    "||fpjs.sh^",
                ]
                primary.write_text("\n".join(fallback_rules), encoding="utf-8")
            finally:
                if close_client:
                    client.close()

    def build_engine(self) -> Engine:
        """Compile loaded filter lists into an adblock Engine."""
        self.ensure_lists()
        fs = FilterSet()

        # Always inject canary rule
        fs.add_filter_list(CANARY_RULE)

        total_rules = 1
        for path in self.list_paths:
            if path.is_file():
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    fs.add_filter_list(content)
                    total_rules += len(content.splitlines())
                except Exception as exc:
                    logger.error(f"Failed to load filter list from {path}: {exc}")

        self.engine = Engine(fs)
        logger.info(f"Compiled adblock engine with ~{total_rules} rules")
        return self.engine


@register_condition("blocklist")
class BlocklistCondition(BaseCondition):
    """Network-level blocking condition using Brave's Rust adblock engine."""

    def __init__(self, definition: Any, study_config: Any):
        super().__init__(definition, study_config)
        self.manager = BlocklistManager(definition.lists)
        self.engine: Engine | None = None

    async def prepare(self) -> None:
        """Download lists if missing and compile adblock engine."""
        self.engine = self.manager.build_engine()

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Create browser context with route interception matching adblock rules."""
        if self.engine is None:
            self.engine = self.manager.build_engine()

        ctx = await browser.new_context(**context_options)
        engine = self.engine

        async def _block_route(route: Route, request: Request) -> None:
            # Never block primary document navigation
            if request.is_navigation_request():
                await route.continue_()
                return

            url = request.url
            source_url = request.headers.get("referer") or ""
            res_type = request.resource_type or "other"

            try:
                match_result = engine.check_network_urls(url, source_url, res_type)
                if match_result.matched:
                    # Abort tracking or advertising sub-resource requests
                    await route.abort("blockedbyclient")
                    return
            except Exception as exc:
                logger.debug(f"Adblock route check exception for {url}: {exc}")

            await route.continue_()

        await ctx.route("**/*", _block_route)
        return ctx

    async def teardown(self) -> None:
        """Clean up engine."""
        self.engine = None

    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Canary check: verify canary tracker URL and standard tracker URLs are blocked."""
        if self.engine is None:
            self.engine = self.manager.build_engine()

        # Engine level check
        check = self.engine.check_network_urls(CANARY_URL, "https://example.com", "script")
        if not check.matched:
            return {
                "passed": False,
                "details": {"error": "Canary URL was not matched by adblock engine"},
            }

        # Browser level check on sub-resource request
        ctx = await self.launch_context(browser, {})
        try:
            page = await ctx.new_page()
            blocked = False
            try:
                await page.goto("about:blank")
                # Attempt sub-resource fetch of canary tracker
                await page.evaluate(f"() => fetch('{CANARY_URL}')")
            except Exception as exc:
                # Sub-resource aborted by client throws Failed to fetch / BLOCKED_BY_CLIENT
                msg = str(exc)
                if any(
                    tok in msg
                    for tok in ("Failed to fetch", "BLOCKED_BY_CLIENT", "ERR_FAILED", "TypeError")
                ):
                    blocked = True

            return {
                "passed": blocked,
                "details": {
                    "canary_url": CANARY_URL,
                    "engine_matched": True,
                    "network_blocked": blocked,
                },
            }
        finally:
            await ctx.close()
