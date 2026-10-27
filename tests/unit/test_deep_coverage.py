"""High-coverage tests exercising conditions, CLI commands, rank bands, and edge cases."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pytest
from playwright.async_api import async_playwright
from typer.testing import CliRunner

from fpstudy.analysis.prevalence import PrevalenceAnalyzer
from fpstudy.cli import app, setup_logging
from fpstudy.config import StudyConfig
from fpstudy.crawler.conditions.brave_shields import BraveShieldsCondition
from fpstudy.crawler.conditions.canvas_defender import CanvasDefenderCondition
from fpstudy.crawler.conditions.extension_ublock import UBlockExtensionCondition, UBlockManager
from fpstudy.crawler.conditions.firefox_rfp import FirefoxRFPCondition
from fpstudy.crawler.visit import classify_failure_taxonomy
from fpstudy.detection.audio import AudioDetector
from fpstudy.detection.blocklist_match import BlocklistMatcher
from fpstudy.detection.fonts import FontsDetector
from fpstudy.instrumentation.loader import is_third_party_script
from fpstudy.sample import SampleManager, generate_candidate_urls
from fpstudy.storage.schema import ClassificationRecord, EventRecord, RunRecord, VisitRecord
from fpstudy.storage.store import DataStore

cli_runner = CliRunner()


def test_is_third_party_script_variations() -> None:
    # 1. Same eTLD+1
    assert is_third_party_script("https://cdn.example.com/lib.js", "https://example.com/") is False
    assert is_third_party_script("https://example.com/app.js", "https://www.example.com/") is False

    # 2. Third-party eTLD+1
    assert is_third_party_script("https://tracker.com/track.js", "https://example.com/") is True
    assert (
        is_third_party_script("https://adservice.google.com/ad.js", "https://news.bbc.co.uk/")
        is True
    )

    # 3. Inline, blob, data
    assert is_third_party_script("inline:123abc456", "https://example.com/") is False
    assert is_third_party_script("blob:https://example.com/uuid", "https://example.com/") is False
    assert is_third_party_script("data:text/javascript;base64,AAA", "https://example.com/") is False
    assert is_third_party_script("", "https://example.com/") is False
    assert is_third_party_script(None, "https://example.com/") is False


def test_rank_band_breakdown(tmp_datastore: DataStore) -> None:
    store = tmp_datastore
    run_id = "run_rank_test"
    store.insert_run(
        RunRecord(run_id=run_id, condition="baseline", config_hash="h", start_time="2026")
    )

    ranks = {
        "top50.com": 20,
        "top200.com": 150,
        "top800.com": 700,
    }

    for dom in ranks:
        store.insert_visit(
            VisitRecord(
                visit_id=f"v_{dom}",
                run_id=run_id,
                domain=dom,
                initial_url=f"https://{dom}/",
                status="ok",
                start_time="2026",
            )
        )
        # top50 and top800 fingerprint
        store.insert_classifications(
            [
                ClassificationRecord(
                    run_id=run_id,
                    visit_id=f"v_{dom}",
                    domain=dom,
                    script_url=f"https://{dom}/s.js",
                    vector="canvas",
                    flagged=1 if dom in ("top50.com", "top800.com") else 0,
                    confidence="high",
                )
            ]
        )

    analyzer = PrevalenceAnalyzer(store)
    bands = [(1, 100), (101, 500), (501, 1000)]
    breakdown = analyzer.compute_rank_band_breakdown(run_id, ranks, bands)

    assert len(breakdown) == 3
    assert breakdown[0]["flagged_domains"] == 1  # top50
    assert breakdown[1]["flagged_domains"] == 0  # top200
    assert breakdown[2]["flagged_domains"] == 1  # top800


def test_fonts_and_audio_alternate_detection_paths() -> None:
    # 1. Fonts detector with DOM element dimensions and document.fonts.check
    fonts_detector = FontsDetector()
    events_fonts = [
        EventRecord(
            visit_id="v_1",
            ts=1.0,
            api="fonts",
            method_or_property="element.offsetWidth",
            args_summary={"fontFamily": f"FontAlpha{i}"},
        )
        for i in range(15)
    ] + [
        EventRecord(
            visit_id="v_1",
            ts=2.0,
            api="fonts",
            method_or_property="document.fonts.check",
            args_summary={"font": f"16px 'FontBeta{i}'"},
        )
        for i in range(16)
    ]
    # Total distinct: 31 fonts >= 30
    res_f = fonts_detector.analyze_events("https://tracker.com/f.js", events_fonts)
    assert res_f.flagged == 1

    # 2. Audio detector with real-time AnalyserNode
    audio_detector = AudioDetector()
    events_audio = [
        EventRecord(visit_id="v_1", ts=1.0, api="audio", method_or_property="AudioContext"),
        EventRecord(visit_id="v_1", ts=2.0, api="audio", method_or_property="createOscillator"),
        EventRecord(visit_id="v_1", ts=3.0, api="audio", method_or_property="createAnalyser"),
        EventRecord(
            visit_id="v_1", ts=4.0, api="audio", method_or_property="analyser.getFloatFrequencyData"
        ),
    ]
    res_a = audio_detector.analyze_events("https://tracker.com/a.js", events_audio)
    assert res_a.flagged == 1
    assert res_a.confidence == "medium"


@pytest.mark.asyncio
async def test_condition_canaries_and_lifecycle(test_config: StudyConfig) -> None:
    with tempfile.TemporaryDirectory() as td:
        # 1. UBlock manager fallback extension creation
        ublock_mgr = UBlockManager(extension_dir=str(Path(td) / "ublock"))
        has_ext = ublock_mgr.ensure_extension()
        assert has_ext is True
        assert (Path(td) / "ublock" / "manifest.json").is_file()

        # 2. UBlock condition self check
        ub_def = test_config.conditions.conditions.get("extension_ublock")
        if ub_def:
            ub_cond = UBlockExtensionCondition(ub_def, test_config)
            ub_cond.manager = ublock_mgr
            chk = await ub_cond.self_check(None)  # type: ignore
            assert chk["passed"] is True

        # 3. Canvas defender describe
        cd_def = test_config.conditions.conditions.get("canvas_defender")
        if cd_def:
            cd_cond = CanvasDefenderCondition(cd_def, test_config)
            assert cd_cond.describe()["type"] == "canvas_defender"

        # 4. Brave shields
        bs_def = test_config.conditions.conditions.get("brave_shields")
        if bs_def:
            bs_cond = BraveShieldsCondition(bs_def, test_config)
            bs_chk = await bs_cond.self_check(None)  # type: ignore
            assert "installed" in bs_chk["details"]

        # 5. Firefox RFP
        fx_def = test_config.conditions.conditions.get("firefox_rfp")
        if fx_def:
            fx_cond = FirefoxRFPCondition(fx_def, test_config)
            assert fx_cond.describe()["name"] == "firefox_rfp"


def test_cli_analyse_and_validate_workflow(tmp_datastore: DataStore) -> None:
    store = tmp_datastore
    base_id = "run_cli_b"
    treat_id = "run_cli_t"

    store.insert_run(
        RunRecord(run_id=base_id, condition="baseline", config_hash="h1", start_time="2026")
    )
    store.insert_run(
        RunRecord(run_id=treat_id, condition="blocklist", config_hash="h2", start_time="2026")
    )

    for rid in (base_id, treat_id):
        store.insert_visit(
            VisitRecord(
                visit_id=f"v_{rid}",
                run_id=rid,
                domain="example.org",
                initial_url="https://example.org/",
                status="ok",
                start_time="2026",
            )
        )
        store.insert_classifications(
            [
                ClassificationRecord(
                    run_id=rid,
                    visit_id=f"v_{rid}",
                    domain="example.org",
                    script_url="https://example.org/fp.js",
                    vector="canvas",
                    flagged=1 if rid == base_id else 0,
                    confidence="high",
                )
            ]
        )

    with tempfile.TemporaryDirectory() as td:
        cfg_file = Path(td) / "custom_config.yaml"
        cfg_file.write_text(
            f"storage:\n  database_path: {tmp_datastore.db_path}\npaths:\n  easyprivacy_path: data/blocklists/easyprivacy.txt\n",
            encoding="utf-8",
        )

        # Run analyse CLI command
        res_an = cli_runner.invoke(
            app,
            [
                "analyse",
                "--baseline",
                base_id,
                "--compare",
                treat_id,
                "--config-file",
                str(cfg_file),
            ],
        )
        assert res_an.exit_code == 0
        assert "Paired McNemar Comparison" in res_an.stdout

        # Run validate --sample
        tmpl_csv = str(Path(td) / "annot_template.csv")
        res_samp = cli_runner.invoke(
            app,
            [
                "validate",
                "--sample",
                "--run-id",
                base_id,
                "--labels",
                tmpl_csv,
                "--config-file",
                str(cfg_file),
            ],
        )
        assert res_samp.exit_code == 0
        assert "Stratified validation template generated" in res_samp.stdout


def test_failure_taxonomy_exhaustive() -> None:
    # 1. Successful / status-based cases
    assert classify_failure_taxonomy(None, 200) == "ok"
    assert classify_failure_taxonomy(None, 301) == "ok"
    assert classify_failure_taxonomy(None, 404) == "http_4xx"
    assert classify_failure_taxonomy(None, 403, "Just normal forbidden") == "http_4xx"
    assert (
        classify_failure_taxonomy(None, 403, "Please complete the Cloudflare challenge")
        == "blocked_bot_suspected"
    )
    assert (
        classify_failure_taxonomy(None, 429, "Bot detection rate limit exceeded")
        == "blocked_bot_suspected"
    )
    assert classify_failure_taxonomy(None, 500) == "http_5xx"
    assert classify_failure_taxonomy(None, 503) == "http_5xx"

    # 2. Exception-based cases
    assert classify_failure_taxonomy(Exception("net::ERR_NAME_NOT_RESOLVED"), None) == "dns_error"
    assert classify_failure_taxonomy(Exception("DNS server failure"), None) == "dns_error"
    assert (
        classify_failure_taxonomy(Exception("Navigation timeout of 30000ms exceeded"), None)
        == "timeout"
    )
    assert (
        classify_failure_taxonomy(Exception("net::ERR_CERT_COMMON_NAME_INVALID"), None)
        == "tls_error"
    )
    assert classify_failure_taxonomy(Exception("SSL handshake failed"), None) == "tls_error"
    assert classify_failure_taxonomy(Exception("Target closed: browser crash"), None) == "crash"
    assert (
        classify_failure_taxonomy(Exception("Access denied by Cloudflare Captcha"), None)
        == "blocked_bot_suspected"
    )
    assert classify_failure_taxonomy(Exception("Unexpected socket reset"), None) == "other"


def test_cli_logging_and_validation_branches() -> None:
    # 1. Structured logging setup
    setup_logging(json_format=True, verbose=True)
    logger = logging.getLogger("test_logger")
    logger.info("JSON formatted log test")

    setup_logging(json_format=False, verbose=False)
    logger.info("Standard formatted log test")

    # 2. Validate without --run-id when generating sample
    res_err = cli_runner.invoke(app, ["validate", "--sample"])
    assert res_err.exit_code != 0
    assert "Must provide --run-id" in res_err.stdout

    # 3. Validate with nonexistent file
    res_none = cli_runner.invoke(app, ["validate", "--labels", "nonexistent_labels.csv"])
    assert "Notice" in res_none.stdout


def test_blocklist_matcher_disconnect_and_easyprivacy() -> None:
    with tempfile.TemporaryDirectory() as td:
        disconnect_file = Path(td) / "disconnect.json"
        disconnect_file.write_text(
            """{
                "categories": {
                    "Advertising": [
                        {
                            "TrackerCorp": {
                                "https://trackercorp.com/": ["trackercorp.com", "adnetwork.io"]
                            }
                        }
                    ]
                }
            }""",
            encoding="utf-8",
        )

        matcher = BlocklistMatcher(easyprivacy_path=None, disconnect_path=disconnect_file)
        assert "trackercorp.com" in matcher._disconnect_domains
        assert "adnetwork.io" in matcher._disconnect_domains

        # Matches Disconnect
        assert matcher.match_script("https://trackercorp.com/track.js") == ["Disconnect"]
        assert matcher.match_script("https://sub.adnetwork.io/pixel.js") == ["Disconnect"]

        # Benign site
        assert matcher.match_script("https://wikipedia.org/app.js") == []

        # Inline script ignored
        assert matcher.match_script("inline:123456") == []


def test_sample_manager_sectors_and_candidate_urls() -> None:
    with tempfile.TemporaryDirectory() as td:
        sample_csv = Path(td) / "tranco.csv"
        sample_csv.write_text(
            "1,google.com\n2,facebook.com\n3,bbc.co.uk\n4,github.com\n", encoding="utf-8"
        )

        sector_csv = Path(td) / "sector.csv"
        sector_csv.write_text("domain\ngoogle.com\ngithub.com\n", encoding="utf-8")

        mgr = SampleManager(download_dir=Path(td), manifest_path=Path(td) / "manifest.json")
        sampled = mgr.get_sample(sample_csv, top_n=10, sector_file=sector_csv)
        assert sampled == ["google.com", "github.com"]

        # Candidate URLs
        urls = generate_candidate_urls("example.com")
        assert urls == ["https://example.com/", "https://www.example.com/", "http://example.com/"]

        urls_ip = generate_candidate_urls("127.0.0.1:8080")
        assert urls_ip == ["http://127.0.0.1:8080/", "https://127.0.0.1:8080/"]


@pytest.mark.asyncio
async def test_canvas_defender_canary_live(test_config: StudyConfig) -> None:
    cd_def = test_config.conditions.conditions.get("canvas_defender")
    assert cd_def is not None
    cd_cond = CanvasDefenderCondition(cd_def, test_config)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        res = await cd_cond.self_check(browser)
        assert res["passed"] is True
        assert res["details"]["active"] is True
        assert res["details"]["noise_detected"] is True
        await browser.close()
