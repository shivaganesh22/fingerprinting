"""Single-site visit logic, metric collection, and failure taxonomy."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import BrowserContext, Response
from playwright.async_api import Error as PlaywrightError

from fpstudy.config import StudyConfig
from fpstudy.instrumentation.loader import InstrumentationLoader, is_third_party_script
from fpstudy.storage.schema import EventRecord, ScriptRecord, VisitRecord

logger = logging.getLogger(__name__)


def classify_failure_taxonomy(
    exc: Exception | None,
    http_status: int | None,
    page_content: str = "",
) -> str:
    """Map exceptions, HTTP status codes, and page text to standardized failure taxonomy."""
    if exc is None:
        if http_status is not None:
            if 400 <= http_status < 500:
                if http_status in (403, 429) and any(
                    tok in page_content.lower()
                    for tok in ("captcha", "challenge", "bot detection", "cloudflare", "datadome")
                ):
                    return "blocked_bot_suspected"
                return "http_4xx"
            if 500 <= http_status < 600:
                return "http_5xx"
        return "ok"

    msg = str(exc).lower()

    if "err_name_not_resolved" in msg or "dns" in msg:
        return "dns_error"
    if "timeout" in msg:
        return "timeout"
    if "err_cert" in msg or "ssl" in msg or "tls" in msg:
        return "tls_error"
    if "crash" in msg or "target closed" in msg:
        return "crash"
    if any(
        tok in msg or tok in page_content.lower()
        for tok in ("blocked", "access denied", "cloudflare", "challenge", "captcha")
    ):
        return "blocked_bot_suspected"

    return "other"


class SiteVisitor:
    """Executes a single domain visit within an isolated browser context."""

    def __init__(
        self,
        config: StudyConfig,
        instrumentation_loader: InstrumentationLoader,
    ):
        self.config = config
        self.loader = instrumentation_loader

    async def visit_site(
        self,
        context: BrowserContext,
        run_id: str,
        domain: str,
        initial_url: str,
    ) -> tuple[VisitRecord, list[EventRecord], list[ScriptRecord]]:
        """Visit site, record metrics, dwell, scroll, collect events and script attributions."""
        visit_id = f"v_{uuid.uuid4().hex[:12]}"
        start_time_iso = datetime.now(UTC).isoformat()
        time.monotonic()

        events: list[EventRecord] = []
        observed_scripts: set[str] = set()

        requests_count = 0
        failed_requests_count = 0
        blocked_requests_count = 0
        console_errors_count = 0

        # Inject hooks into context
        await self.loader.inject(context)

        page = await context.new_page()

        # Listen for console errors
        def _on_console(msg: Any) -> None:
            nonlocal console_errors_count
            if msg.type == "error":
                console_errors_count += 1

        page.on("console", _on_console)

        # Track network requests
        def _on_request(req: Any) -> None:
            nonlocal requests_count
            requests_count += 1
            if req.resource_type == "script":
                observed_scripts.add(req.url)

        def _on_request_failed(req: Any) -> None:
            nonlocal failed_requests_count, blocked_requests_count
            failed_requests_count += 1
            failure_text = (req.failure or "").lower().replace("-", "_")
            # Exclude internal browser cross-origin defenses like ORB/CORB (not privacy countermeasure blocks)
            if "blocked_by_orb" in failure_text or "blocked_by_corb" in failure_text:
                return
            # Match genuine countermeasure blocks (DNR, Brave Shields, Playwright route aborts)
            if any(
                token in failure_text
                for token in (
                    "blockedbyclient",
                    "blocked_by_client",
                    "err_blocked_by_client",
                    "err_blocked_by_response",
                    "err_blocked_by_administrator",
                )
            ):
                blocked_requests_count += 1

        page.on("request", _on_request)
        page.on("requestfailed", _on_request_failed)

        # Expose binding for streaming events
        await self.loader.bind_page(page, visit_id, events)

        # Execution parameters
        nav_timeout_ms = int(self.config.crawler.navigation_timeout_seconds * 1000)
        dwell_time_s = self.config.crawler.dwell_time_seconds

        final_url: str | None = None
        http_status: int | None = None
        load_time_ms: float | None = None
        dwell_time_ms: float | None = None
        error_message: str | None = None
        caught_exc: Exception | None = None
        page_text = ""

        try:
            # 1. Navigation
            t_nav_start = time.monotonic()
            response: Response | None = await page.goto(
                initial_url,
                wait_until="load",
                timeout=nav_timeout_ms,
            )
            load_time_ms = (time.monotonic() - t_nav_start) * 1000.0

            if response:
                http_status = response.status
            final_url = page.url

            # 2. Dwell time
            t_dwell_start = time.monotonic()
            await asyncio.sleep(dwell_time_s)

            # 3. Gentle scroll interaction
            with contextlib.suppress(Exception):
                await page.evaluate(
                    "() => window.scrollTo(0, Math.min(500, document.body.scrollHeight / 2))"
                )

            dwell_time_ms = (time.monotonic() - t_dwell_start) * 1000.0

            try:
                page_text = await page.content()
            except Exception:
                page_text = ""

        except PlaywrightError as exc:
            caught_exc = exc
            error_message = str(exc)
            final_url = page.url if page else None
        except Exception as exc:
            caught_exc = exc
            error_message = str(exc)

        # Drain any residual events from page
        drain_info = await self.loader.drain_events(page, visit_id, events)

        # Map status
        status = classify_failure_taxonomy(caught_exc, http_status, page_text)

        end_time_iso = datetime.now(UTC).isoformat()

        # Compile script attributions
        for e in events:
            if e.script_url:
                observed_scripts.add(e.script_url)

        script_records: list[ScriptRecord] = [
            ScriptRecord(
                visit_id=visit_id,
                script_url=s_url,
                is_third_party=int(is_third_party_script(s_url, final_url or initial_url)),
            )
            for s_url in observed_scripts
        ]

        visit_rec = VisitRecord(
            visit_id=visit_id,
            run_id=run_id,
            domain=domain,
            initial_url=initial_url,
            final_url=final_url,
            status=status,
            http_status=http_status,
            load_time_ms=load_time_ms,
            dwell_time_ms=dwell_time_ms,
            console_errors_count=console_errors_count,
            requests_count=requests_count,
            failed_requests_count=failed_requests_count,
            blocked_requests_count=blocked_requests_count,
            events_count=len(events),
            events_truncated=int(drain_info.get("truncated", False)),
            start_time=start_time_iso,
            end_time=end_time_iso,
            error_message=error_message,
        )

        with contextlib.suppress(Exception):
            await page.close()

        return visit_rec, events, script_records
