"""Integration tests using local HTTP fixture servers and Playwright automation."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from fpstudy.analysis.compare import CountermeasureComparator
from fpstudy.analysis.prevalence import PrevalenceAnalyzer
from fpstudy.config import StudyConfig
from fpstudy.crawler.browser import BrowserManager
from fpstudy.crawler.runner import CrawlRunner
from fpstudy.crawler.visit import SiteVisitor
from fpstudy.detection.classify import ScriptClassifier
from fpstudy.instrumentation.loader import InstrumentationLoader
from fpstudy.storage.store import DataStore


@pytest.mark.asyncio
async def test_hook_stealth_and_native_appearance(
    fixture_server: str,
) -> None:
    """Verify that hooks preserve Function.prototype.toString [native code] appearance."""
    loader = InstrumentationLoader()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        await loader.inject(ctx)
        page = await ctx.new_page()

        await page.goto(f"{fixture_server}/hook_stealth.html")
        results = await page.evaluate("() => window.__stealth_results")

        # Must report [native code]
        assert "[native code]" in results["canvas_toDataURL_native_str"]
        assert results["canvas_toDataURL_name"] == "toDataURL"
        if results["webgl_getParameter_native_str"] != "n/a":
            assert "[native code]" in results["webgl_getParameter_native_str"]

        await browser.close()


@pytest.mark.asyncio
async def test_canvas_fingerprinting_detection(
    fixture_server: str,
    test_config: StudyConfig,
) -> None:
    """Test that canonical canvas FP is flagged and benign drawing app is not flagged."""
    bm = BrowserManager(test_config, "baseline")
    await bm.start()
    loader = InstrumentationLoader()
    visitor = SiteVisitor(test_config, loader)
    classifier = ScriptClassifier(test_config)

    try:
        # 1. FP canvas page
        ctx_fp = await bm.create_context()
        visit_fp, events_fp, _ = await visitor.visit_site(
            ctx_fp, "run_test", "fp-canvas.local", f"{fixture_server}/fp_canvas.html"
        )
        assert visit_fp.status == "ok"
        class_fp = classifier.classify_visit(
            "run_test", visit_fp.visit_id, "fp-canvas.local", events_fp
        )
        canvas_flag = any(c.vector == "canvas" and c.flagged == 1 for c in class_fp)
        assert canvas_flag is True
        await ctx_fp.close()

        # 2. Benign canvas page
        ctx_benign = await bm.create_context()
        visit_b, events_b, _ = await visitor.visit_site(
            ctx_benign, "run_test", "benign-canvas.local", f"{fixture_server}/benign_canvas.html"
        )
        assert visit_b.status == "ok"
        class_b = classifier.classify_visit(
            "run_test", visit_b.visit_id, "benign-canvas.local", events_b
        )
        canvas_b_flag = any(c.vector == "canvas" and c.flagged == 1 for c in class_b)
        assert canvas_b_flag is False
        await ctx_benign.close()

    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_webgl_fingerprinting_detection(
    fixture_server: str,
    test_config: StudyConfig,
) -> None:
    """Test that WebGL FP probe is flagged and benign 3D scene is not flagged."""
    bm = BrowserManager(test_config, "baseline")
    await bm.start()
    loader = InstrumentationLoader()
    visitor = SiteVisitor(test_config, loader)
    classifier = ScriptClassifier(test_config)

    try:
        # FP WebGL
        ctx_fp = await bm.create_context()
        visit_fp, events_fp, _ = await visitor.visit_site(
            ctx_fp, "run_test", "fp-webgl.local", f"{fixture_server}/fp_webgl.html"
        )
        class_fp = classifier.classify_visit(
            "run_test", visit_fp.visit_id, "fp-webgl.local", events_fp
        )
        webgl_flag = any(c.vector == "webgl" and c.flagged == 1 for c in class_fp)
        assert webgl_flag is True
        await ctx_fp.close()

        # Benign WebGL
        ctx_b = await bm.create_context()
        visit_b, events_b, _ = await visitor.visit_site(
            ctx_b, "run_test", "benign-webgl.local", f"{fixture_server}/benign_webgl.html"
        )
        class_b = classifier.classify_visit(
            "run_test", visit_b.visit_id, "benign-webgl.local", events_b
        )
        webgl_b_flag = any(c.vector == "webgl" and c.flagged == 1 for c in class_b)
        assert webgl_b_flag is False
        await ctx_b.close()

    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_audio_fingerprinting_detection(
    fixture_server: str,
    test_config: StudyConfig,
) -> None:
    """Test that AudioContext fingerprinting is flagged and benign playback is not."""
    bm = BrowserManager(test_config, "baseline")
    await bm.start()
    loader = InstrumentationLoader()
    visitor = SiteVisitor(test_config, loader)
    classifier = ScriptClassifier(test_config)

    try:
        # FP Audio
        ctx_fp = await bm.create_context()
        visit_fp, events_fp, _ = await visitor.visit_site(
            ctx_fp, "run_test", "fp-audio.local", f"{fixture_server}/fp_audio.html"
        )
        class_fp = classifier.classify_visit(
            "run_test", visit_fp.visit_id, "fp-audio.local", events_fp
        )
        audio_flag = any(c.vector == "audio" and c.flagged == 1 for c in class_fp)
        assert audio_flag is True
        await ctx_fp.close()

        # Benign Audio
        ctx_b = await bm.create_context()
        visit_b, events_b, _ = await visitor.visit_site(
            ctx_b, "run_test", "benign-audio.local", f"{fixture_server}/benign_audio.html"
        )
        class_b = classifier.classify_visit(
            "run_test", visit_b.visit_id, "benign-audio.local", events_b
        )
        audio_b_flag = any(c.vector == "audio" and c.flagged == 1 for c in class_b)
        assert audio_b_flag is False
        await ctx_b.close()

    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_fonts_fingerprinting_detection(
    fixture_server: str,
    test_config: StudyConfig,
) -> None:
    """Test that font enumeration >= 30 fonts is flagged and benign text is not."""
    bm = BrowserManager(test_config, "baseline")
    await bm.start()
    loader = InstrumentationLoader()
    visitor = SiteVisitor(test_config, loader)
    classifier = ScriptClassifier(test_config)

    try:
        # FP Fonts (35 distinct fonts)
        ctx_fp = await bm.create_context()
        visit_fp, events_fp, _ = await visitor.visit_site(
            ctx_fp, "run_test", "fp-fonts.local", f"{fixture_server}/fp_fonts.html"
        )
        class_fp = classifier.classify_visit(
            "run_test", visit_fp.visit_id, "fp-fonts.local", events_fp
        )
        fonts_flag = any(c.vector == "fonts" and c.flagged == 1 for c in class_fp)
        assert fonts_flag is True
        await ctx_fp.close()

        # Benign Fonts
        ctx_b = await bm.create_context()
        visit_b, events_b, _ = await visitor.visit_site(
            ctx_b, "run_test", "benign-fonts.local", f"{fixture_server}/benign_fonts.html"
        )
        class_b = classifier.classify_visit(
            "run_test", visit_b.visit_id, "benign-fonts.local", events_b
        )
        fonts_b_flag = any(c.vector == "fonts" and c.flagged == 1 for c in class_b)
        assert fonts_b_flag is False
        await ctx_b.close()

    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_third_party_and_inline_attribution(
    fixture_server: str,
    test_config: StudyConfig,
) -> None:
    """Verify script attribution for third-party script and inline script."""
    bm = BrowserManager(test_config, "baseline")
    await bm.start()
    loader = InstrumentationLoader()
    visitor = SiteVisitor(test_config, loader)

    try:
        # Inline attribution
        ctx_inline = await bm.create_context()
        v_in, events_in, _ = await visitor.visit_site(
            ctx_inline, "run_test", "inline.local", f"{fixture_server}/inline_fp.html"
        )
        assert len(events_in) > 0
        assert any("inline:" in (e.script_url or "") for e in events_in)
        await ctx_inline.close()

        # Iframe attribution
        ctx_iframe = await bm.create_context()
        v_if, events_if, _ = await visitor.visit_site(
            ctx_iframe, "run_test", "iframe.local", f"{fixture_server}/iframe_fp.html"
        )
        assert len(events_if) > 0
        assert any("fp_canvas.html" in (e.frame_url or "") for e in events_if)
        await ctx_iframe.close()

    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_robots_disallowed_behavior(
    robots_disallow_server: str,
    test_config: StudyConfig,
    tmp_datastore: DataStore,
) -> None:
    """Verify crawler respects robots.txt disallowing / and records skipped_robots."""
    from urllib.parse import urlparse

    parsed = urlparse(robots_disallow_server)
    domain = parsed.netloc

    runner = CrawlRunner(test_config, condition_name="baseline", store=tmp_datastore)
    await runner.run([domain], resume=False)

    visits = tmp_datastore.get_visits(runner.run_id)
    assert len(visits) == 1
    assert visits[0]["status"] == "skipped_robots"


@pytest.mark.asyncio
async def test_end_to_end_crawl_classify_analyse(
    fixture_server: str,
    test_config: StudyConfig,
    tmp_datastore: DataStore,
    tmp_path: Path,
) -> None:
    """End-to-end pipeline test across local fixture pages under baseline and blocklist conditions."""
    # 1. Baseline crawl
    runner_base = CrawlRunner(
        test_config,
        condition_name="baseline",
        store=tmp_datastore,
        run_id="run_baseline_e2e",
    )
    # Target fixture domains
    domains = [f"{fixture_server}/thirdparty_fp.html"]
    await runner_base.run(domains, resume=False)

    # Classify baseline
    classifier = ScriptClassifier(test_config, store=tmp_datastore)
    res_base = classifier.classify_run("run_baseline_e2e")
    assert res_base["total_sites_visited"] == 1

    # Prevalence analyzer
    analyzer = PrevalenceAnalyzer(tmp_datastore)
    prev_base = analyzer.compute_prevalence("run_baseline_e2e")
    assert prev_base["denominator"]["successful_ok"] == 1

    # 2. Blocklist crawl
    filter_path = tmp_path / "fixture_blocklist.txt"
    filter_path.write_text("||127.0.0.1^\n", encoding="utf-8")
    test_config.conditions.conditions["blocklist"].lists = [str(filter_path)]
    runner_block = CrawlRunner(
        test_config,
        condition_name="blocklist",
        store=tmp_datastore,
        run_id="run_blocklist_e2e",
    )
    await runner_block.run(domains, resume=False)
    classifier.classify_run("run_blocklist_e2e")
    blocklist_visits = tmp_datastore.get_visits("run_blocklist_e2e")
    assert blocklist_visits[0]["blocked_requests_count"] > 0

    # 3. Countermeasure comparison
    comparator = CountermeasureComparator(tmp_datastore)
    comp_res = comparator.compare_runs("run_baseline_e2e", "run_blocklist_e2e")
    assert comp_res["n_paired_domains"] == 1
    assert "binary_outcomes_mcnemar" in comp_res
