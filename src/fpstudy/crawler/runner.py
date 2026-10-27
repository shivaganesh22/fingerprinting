"""Crawl runner orchestrating concurrency, rate limits, robots.txt, retries, and persistence."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import signal
import subprocess
import uuid
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import Browser

from fpstudy.config import StudyConfig
from fpstudy.crawler.browser import BrowserManager
from fpstudy.crawler.visit import SiteVisitor
from fpstudy.instrumentation.loader import InstrumentationLoader
from fpstudy.ratelimit import RateLimiter
from fpstudy.robots import RobotsChecker
from fpstudy.sample import generate_candidate_urls
from fpstudy.storage.schema import RunRecord, VisitRecord
from fpstudy.storage.store import DataStore

logger = logging.getLogger(__name__)


def get_git_commit() -> str | None:
    """Retrieve current git HEAD commit hash if available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


class CrawlRunner:
    """Manages multi-domain crawling across experimental countermeasure conditions."""

    def __init__(
        self,
        config: StudyConfig,
        condition_name: str = "baseline",
        store: DataStore | None = None,
        run_id: str | None = None,
    ):
        self.config = config
        self.condition_name = condition_name
        self.store = store or DataStore(config.storage.database_path)
        self.run_id = (
            run_id
            or f"run_{condition_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )

        self.browser_manager = BrowserManager(config, condition_name)
        self.instrumentation_loader = InstrumentationLoader(
            max_events=config.instrumentation.max_events_per_visit
        )
        self.site_visitor = SiteVisitor(config, self.instrumentation_loader)

        self.robots_checker = RobotsChecker()
        self.rate_limiter = RateLimiter(
            min_domain_delay_seconds=config.crawler.min_domain_delay_seconds,
            global_concurrency=config.crawler.concurrency,
        )

        self._shutdown_requested = False

    def compute_config_hash(self) -> str:
        """Compute stable SHA-256 hash of current configuration."""
        raw_json = json.dumps(self.config.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

    async def execute_canary(self, browser: Browser) -> dict[str, Any]:
        """Execute condition canary self-check. Fails loudly if defense is inactive."""
        logger.info(f"Executing self-check canary for condition '{self.condition_name}'...")
        canary_res = await self.browser_manager.condition.self_check(browser)
        passed = canary_res.get("passed", False)
        if not passed:
            msg = f"Canary self-check FAILED for condition '{self.condition_name}': {canary_res.get('details')}"
            logger.error(msg)
            raise RuntimeError(msg)
        logger.info(f"Canary self-check PASSED for condition '{self.condition_name}'.")
        return canary_res

    async def crawl_domain(
        self,
        domain: str,
        semaphore: asyncio.Semaphore,
    ) -> VisitRecord | None:
        """Crawl a single domain with rate limiting, robots.txt verification, and retries."""
        if self._shutdown_requested:
            return None

        # Check candidate URLs
        if domain.startswith("http://") or domain.startswith("https://"):
            target_url = domain
        else:
            candidate_urls = generate_candidate_urls(domain)
            target_url = candidate_urls[0]

        # 1. Robots.txt check
        ua = self.config.crawler.full_user_agent()
        allowed = self.robots_checker.is_allowed(target_url, ua)
        if not allowed:
            logger.info(f"Skipping {domain}: disallowed by robots.txt")
            visit_rec = VisitRecord(
                visit_id=f"v_{uuid.uuid4().hex[:12]}",
                run_id=self.run_id,
                domain=domain,
                initial_url=target_url,
                status="skipped_robots",
                start_time=datetime.now(UTC).isoformat(),
                end_time=datetime.now(UTC).isoformat(),
            )
            self.store.insert_visit(visit_rec)
            return visit_rec

        # 2. Rate limit delay per domain
        await self.rate_limiter.acquire_domain(domain)

        # 3. Context & Visit execution with retries
        max_retries = self.config.crawler.max_retries
        backoff = self.config.crawler.retry_backoff_factor

        async with semaphore:
            for attempt in range(max_retries + 1):
                if self._shutdown_requested:
                    return None

                ctx = None
                try:
                    ctx = await self.browser_manager.create_context()
                    visit_rec, events, scripts = await self.site_visitor.visit_site(
                        ctx, self.run_id, domain, target_url
                    )

                    # If transient failure and attempts remain, retry with backoff
                    if (
                        visit_rec.status in ("timeout", "dns_error", "crash")
                        and attempt < max_retries
                    ):
                        wait_time = (backoff**attempt) * 2.0
                        logger.warning(
                            f"Transient failure on {domain} ({visit_rec.status}). "
                            f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    # Persist records
                    self.store.insert_visit(visit_rec)
                    self.store.insert_events(events)
                    self.store.insert_scripts(scripts)
                    return visit_rec

                except Exception as exc:
                    logger.error(f"Error visiting {domain} on attempt {attempt}: {exc}")
                    if attempt == max_retries:
                        visit_rec = VisitRecord(
                            visit_id=f"v_{uuid.uuid4().hex[:12]}",
                            run_id=self.run_id,
                            domain=domain,
                            initial_url=target_url,
                            status="crash",
                            start_time=datetime.now(UTC).isoformat(),
                            end_time=datetime.now(UTC).isoformat(),
                            error_message=str(exc),
                        )
                        self.store.insert_visit(visit_rec)
                        return visit_rec
                finally:
                    if ctx:
                        with contextlib.suppress(Exception):
                            await ctx.close()

        return None

    async def run(
        self,
        domains: list[str],
        resume: bool = True,
        limit: int | None = None,
    ) -> RunRecord:
        """Execute crawl across the specified domain list."""
        # Enforce responsible crawling ethics
        self.config.crawler.verify_contact_configured()

        # Handle SIGINT gracefully
        loop = asyncio.get_running_loop()

        def _handle_sigint() -> None:
            logger.warning("SIGINT received. Commencing graceful crawler shutdown...")
            self._shutdown_requested = True

        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(signal.SIGINT, _handle_sigint)

        target_domains = domains[:limit] if limit is not None else domains

        # Check completed domains if resuming
        completed: set[str] = set()
        if resume:
            completed = self.store.get_completed_domains(self.run_id)
            if completed:
                logger.info(f"Resuming run {self.run_id}: {len(completed)} domains already crawled")

        remaining = [d for d in target_domains if d not in completed]
        logger.info(
            f"Starting crawl for {len(remaining)} domains under condition '{self.condition_name}'"
        )

        # Initialize browser and run record
        browser = await self.browser_manager.start()
        canary_res = await self.execute_canary(browser)
        system_manifest = self.browser_manager.get_system_manifest()

        run_rec = RunRecord(
            run_id=self.run_id,
            condition=self.condition_name,
            config_hash=self.compute_config_hash(),
            start_time=datetime.now(UTC).isoformat(),
            git_commit=get_git_commit(),
            tranco_list_id=self.config.sample.tranco_list_id,
            browser_version=system_manifest.get("browser_version"),
            os_info=system_manifest.get("os_info"),
            library_versions={
                "python": system_manifest.get("python_version", ""),
                "fpstudy": "0.1.0",
            },
            canary_passed=1 if canary_res.get("passed") else 0,
            canary_details=canary_res,
        )
        self.store.insert_run(run_rec)

        # Concurrency semaphore
        semaphore = asyncio.Semaphore(self.config.crawler.concurrency)

        try:
            # Batch domain visits concurrently
            tasks = [self.crawl_domain(d, semaphore) for d in remaining]
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self.store.finish_run(self.run_id)
            await self.browser_manager.close()

        logger.info(f"Crawl completed for run {self.run_id}")
        return run_rec
