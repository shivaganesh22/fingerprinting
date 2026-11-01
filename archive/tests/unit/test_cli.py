"""Unit tests for fpstudy Typer CLI commands using CliRunner."""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from fpstudy.cli import app
from fpstudy.storage.schema import ClassificationRecord, RunRecord, VisitRecord
from fpstudy.storage.store import DataStore

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Browser Fingerprinting Measurement Pipeline" in result.stdout
    assert "sample" in result.stdout
    assert "crawl" in result.stdout
    assert "classify" in result.stdout
    assert "validate" in result.stdout
    assert "analyse" in result.stdout
    assert "report" in result.stdout
    assert "selfcheck" in result.stdout


def test_cli_sample_offline() -> None:
    # Use bundled sample
    result = runner.invoke(app, ["sample", "--top-n", "5"])
    assert result.exit_code == 0
    assert "Successfully sampled" in result.stdout


def test_cli_classify_and_report_roundtrip() -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        db_path = tf.name

    store = DataStore(db_path)
    run_id = "run_cli_test"
    store.insert_run(
        RunRecord(run_id=run_id, condition="baseline", config_hash="h1", start_time="2026-10-27")
    )
    store.insert_visit(
        VisitRecord(
            visit_id="v_c1",
            run_id=run_id,
            domain="clitest.com",
            initial_url="https://clitest.com/",
            status="ok",
            start_time="2026-10-27",
        )
    )

    # Classify
    res_cls = runner.invoke(app, ["classify", "--run-id", run_id])
    assert res_cls.exit_code == 0

    # Report
    res_rep = runner.invoke(app, ["report"])
    assert res_rep.exit_code == 0

    Path(db_path).unlink(missing_ok=True)


def test_cli_validate_template_generation() -> None:
    with tempfile.TemporaryDirectory() as td:
        csv_path = str(Path(td) / "labels.csv")
        # Run validate without labels should warn or succeed
        res = runner.invoke(app, ["validate", "--labels", csv_path])
        assert res.exit_code == 0 or "Notice" in res.stdout


def test_cli_validate_with_annotated_labels() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "val.sqlite")
        store = DataStore(db_path)
        store.insert_run(
            RunRecord(run_id="r_val", condition="baseline", config_hash="h", start_time="2026")
        )
        store.insert_visit(
            VisitRecord(
                visit_id="v_val",
                run_id="r_val",
                domain="example.com",
                initial_url="https://example.com/",
                status="ok",
                start_time="2026",
            )
        )
        store.insert_classifications(
            [
                ClassificationRecord(
                    run_id="r_val",
                    visit_id="v_val",
                    domain="example.com",
                    script_url="https://example.com/s.js",
                    vector="canvas",
                    flagged=1,
                    confidence="high",
                )
            ]
        )

        cfg_file = Path(td) / "cfg.yaml"
        cfg_file.write_text(
            f"storage:\n  database_path: {db_path}\n",
            encoding="utf-8",
        )

        csv_file = Path(td) / "labels.csv"
        csv_file.write_text(
            "sample_id,domain,script_url,vector,predicted_flag,confidence,ground_truth_label,notes\n"
            "samp_001,example.com,https://example.com/s.js,canvas,1,high,1,Confirmed\n",
            encoding="utf-8",
        )

        res = runner.invoke(
            app, ["validate", "--labels", str(csv_file), "--config-file", str(cfg_file)]
        )
        assert res.exit_code == 0
        assert "Classifier Validation Metrics" in res.stdout
        assert "Overall" in res.stdout


def test_cli_selfcheck() -> None:
    res = runner.invoke(app, ["selfcheck"])
    assert res.exit_code == 0
    assert "Playwright Chromium launched successfully" in res.stdout
    assert "All environment checks and canaries PASSED" in res.stdout
