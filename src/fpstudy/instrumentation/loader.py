"""Hooks loader, Playwright init_script injection, and event collection pipeline."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import tldextract
from playwright.async_api import BrowserContext, Page

from fpstudy.storage.schema import EventRecord

logger = logging.getLogger(__name__)

# Configure offline-mode tldextract
_tld_extractor = tldextract.TLDExtract(cache_dir="data/.tld_cache", suffix_list_urls=())


def get_etld_plus_one(url_or_domain: str) -> str:
    """Extract registered domain (eTLD+1) using offline tldextract."""
    if not url_or_domain:
        return ""
    # Strip custom pseudo-schemes
    if url_or_domain.startswith("inline:"):
        return ""
    try:
        extracted = _tld_extractor(url_or_domain)
        if (
            hasattr(extracted, "top_domain_under_public_suffix")
            and extracted.top_domain_under_public_suffix
        ):
            return str(extracted.top_domain_under_public_suffix).lower()
        if extracted.domain and extracted.suffix:
            return f"{extracted.domain}.{extracted.suffix}".lower()
        return extracted.domain.lower() if extracted.domain else ""
    except Exception:
        return ""


def is_third_party_script(script_url: str | None, top_level_url: str | None) -> bool:
    """Determine whether a script is 3rd-party relative to the top-level page domain."""
    if not script_url or not top_level_url:
        return False
    if script_url.startswith("inline:"):
        return False
    if script_url.startswith("data:") or script_url.startswith("blob:"):
        return False

    script_etld = get_etld_plus_one(script_url)
    top_etld = get_etld_plus_one(top_level_url)

    if not script_etld or not top_etld:
        return False

    return script_etld != top_etld


class InstrumentationLoader:
    """Manages JavaScript hook injection and bidirectional event streaming."""

    def __init__(self, hooks_js_path: Path | str | None = None, max_events: int = 5000):
        if hooks_js_path is None:
            self.hooks_path = Path(__file__).parent / "hooks.js"
        else:
            self.hooks_path = Path(hooks_js_path)

        if not self.hooks_path.is_file():
            raise FileNotFoundError(f"Hooks script not found at {self.hooks_path}")

        self.max_events = max_events
        self._hooks_content = self.hooks_path.read_text(encoding="utf-8")

    async def inject(self, context: BrowserContext) -> None:
        """Inject hooks script into browser context before any document scripts run."""
        init_script = f"window.__fpstudy_max_events = {self.max_events};\n" + self._hooks_content
        await context.add_init_script(init_script)

    async def bind_page(
        self,
        page: Page,
        visit_id: str,
        event_collector: list[EventRecord],
        on_event_received: Callable[[EventRecord], None] | None = None,
    ) -> None:
        """Expose receiving binding on page and capture streaming events into collector."""

        async def _handle_events(events: list[dict[str, Any]]) -> None:
            for raw in events:
                script_url = raw.get("script_url")
                top_level_url = raw.get("top_level_url") or page.url
                is_3p = int(is_third_party_script(script_url, top_level_url))

                rec = EventRecord(
                    visit_id=visit_id,
                    ts=float(raw.get("ts", 0.0)),
                    api=str(raw.get("api", "")),
                    method_or_property=str(raw.get("method_or_property", "")),
                    args_summary=raw.get("args_summary") or {},
                    return_summary=raw.get("return_summary") or {},
                    script_url=script_url,
                    stack_excerpt=raw.get("stack_excerpt"),
                    frame_url=raw.get("frame_url"),
                    top_level_url=top_level_url,
                    is_third_party=is_3p,
                )
                event_collector.append(rec)
                if on_event_received:
                    on_event_received(rec)

        with contextlib.suppress(Exception):
            await page.expose_function("__fpstudy_push_events", _handle_events)

    async def drain_events(
        self,
        page: Page,
        visit_id: str,
        event_collector: list[EventRecord],
    ) -> dict[str, Any]:
        """Drain any remaining events from in-page buffer and check truncation status."""
        try:
            drain_result = await page.evaluate(
                "() => window.__fpstudy_drain_events ? window.__fpstudy_drain_events() : null"
            )
            if drain_result and isinstance(drain_result, dict):
                raw_events = drain_result.get("events") or []
                for raw in raw_events:
                    script_url = raw.get("script_url")
                    top_level_url = raw.get("top_level_url") or page.url
                    is_3p = int(is_third_party_script(script_url, top_level_url))

                    rec = EventRecord(
                        visit_id=visit_id,
                        ts=float(raw.get("ts", 0.0)),
                        api=str(raw.get("api", "")),
                        method_or_property=str(raw.get("method_or_property", "")),
                        args_summary=raw.get("args_summary") or {},
                        return_summary=raw.get("return_summary") or {},
                        script_url=script_url,
                        stack_excerpt=raw.get("stack_excerpt"),
                        frame_url=raw.get("frame_url"),
                        top_level_url=top_level_url,
                        is_third_party=is_3p,
                    )
                    event_collector.append(rec)

                return {
                    "total_count": drain_result.get("total_count", len(event_collector)),
                    "truncated": bool(drain_result.get("truncated", False)),
                }
        except Exception as exc:
            logger.debug(f"Drain events failed (page possibly closed): {exc}")

        return {
            "total_count": len(event_collector),
            "truncated": False,
        }
