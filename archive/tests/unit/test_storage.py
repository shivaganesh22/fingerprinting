"""Unit tests for SQLite DataStore round-trips, indexes, and JSONL export/import."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fpstudy.storage.schema import EventRecord, RunRecord, VisitRecord
from fpstudy.storage.store import DataStore


def test_datastore_lifecycle(tmp_datastore: DataStore) -> None:
    store = tmp_datastore

    # 1. Run insertion
    run = RunRecord(
        run_id="run_test_01",
        condition="baseline",
        config_hash="abc123hash",
        start_time="2026-10-27T10:00:00",
    )
    store.insert_run(run)
    fetched_run = store.get_run("run_test_01")
    assert fetched_run is not None
    assert fetched_run["condition"] == "baseline"

    # 2. Visit insertion
    visit = VisitRecord(
        visit_id="v_001",
        run_id="run_test_01",
        domain="example.com",
        initial_url="https://example.com/",
        status="ok",
        start_time="2026-10-27T10:00:01",
    )
    store.insert_visit(visit)
    visits = store.get_visits("run_test_01")
    assert len(visits) == 1
    assert visits[0]["domain"] == "example.com"

    # 3. Events insertion
    evt = EventRecord(
        visit_id="v_001",
        ts=15.0,
        api="canvas",
        method_or_property="toDataURL",
        args_summary={"width": 100, "height": 50},
        return_summary={},
        script_url="https://example.com/fp.js",
    )
    store.insert_events([evt])
    evts = store.get_events_for_visit("v_001")
    assert len(evts) == 1
    assert evts[0]["method_or_property"] == "toDataURL"

    # 4. Completed domains query (for resuming)
    completed = store.get_completed_domains("run_test_01")
    assert "example.com" in completed


def test_jsonl_export_import(tmp_datastore: DataStore) -> None:
    store = tmp_datastore

    run = RunRecord(
        run_id="run_export_test",
        condition="blocklist",
        config_hash="def456",
        start_time="2026-10-27T10:00:00",
    )
    store.insert_run(run)

    visit = VisitRecord(
        visit_id="v_exp_01",
        run_id="run_export_test",
        domain="export.org",
        initial_url="https://export.org/",
        status="ok",
        start_time="2026-10-27T10:00:01",
    )
    store.insert_visit(visit)

    evt = EventRecord(
        visit_id="v_exp_01",
        ts=2.0,
        api="webgl",
        method_or_property="getParameter",
        args_summary={"pname": 123},
        return_summary={},
    )
    store.insert_events([evt])

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        export_file = Path(tf.name)

    try:
        store.export_jsonl("run_export_test", export_file)
        assert export_file.is_file()
        assert export_file.stat().st_size > 0

        # Import into fresh store
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf_db:
            new_db = Path(tf_db.name)

        new_store = DataStore(new_db)
        new_store.import_jsonl(export_file)

        assert new_store.get_run("run_export_test") is not None
        assert len(new_store.get_visits("run_export_test")) == 1
        assert len(new_store.get_events_for_visit("v_exp_01")) == 1

        new_db.unlink(missing_ok=True)
    finally:
        export_file.unlink(missing_ok=True)
