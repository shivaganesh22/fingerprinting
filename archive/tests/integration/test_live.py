"""Live web smoke test against prominent real-world domains (marked @pytest.mark.live)."""

from __future__ import annotations

import pytest

from fpstudy.config import StudyConfig
from fpstudy.crawler.runner import CrawlRunner
from fpstudy.detection.classify import ScriptClassifier
from fpstudy.storage.store import DataStore


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_web_smoke_crawl(test_config: StudyConfig, tmp_datastore: DataStore) -> None:
    """Politely crawls ~3 prominent live domains to verify real-world pipeline functionality.

    To execute:
        pytest -m live tests/integration/test_live.py
    """
    test_config.crawler.dwell_time_seconds = 3.0
    test_config.crawler.concurrency = 1
    test_config.crawler.min_domain_delay_seconds = 2.0
    test_config.crawler.contact_email = "student-research@university.ac.uk"

    runner = CrawlRunner(
        test_config,
        condition_name="baseline",
        store=tmp_datastore,
        run_id="run_live_smoke",
    )

    live_sample = ["wikipedia.org", "gnu.org", "eff.org"]
    run_rec = await runner.run(live_sample, resume=False)
    assert run_rec.canary_passed == 1

    visits = tmp_datastore.get_visits("run_live_smoke")
    assert len(visits) == len(live_sample)

    classifier = ScriptClassifier(test_config, store=tmp_datastore)
    metrics = classifier.classify_run("run_live_smoke")
    assert metrics["total_sites_visited"] == len(live_sample)
