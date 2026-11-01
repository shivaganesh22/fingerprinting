"""Unit tests for reporting, breakage analysis, validation tooling, and conditions."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fpstudy.analysis.breakage import BreakageAnalyzer
from fpstudy.analysis.plots import ReportGenerator
from fpstudy.analysis.validation import ValidationTooling, calculate_binary_metrics
from fpstudy.config import StudyConfig
from fpstudy.crawler.conditions.base import get_available_conditions
from fpstudy.crawler.conditions.brave_shields import BraveShieldsCondition
from fpstudy.crawler.conditions.firefox_rfp import FirefoxRFPCondition
from fpstudy.storage.schema import ClassificationRecord, RunRecord, VisitRecord
from fpstudy.storage.store import DataStore


def test_calculate_binary_metrics() -> None:
    y_true = [1, 1, 0, 0, 1]
    y_pred = [1, 0, 0, 1, 1]
    # TP: 2 (idx 0, 4)
    # FP: 1 (idx 3)
    # FN: 1 (idx 1)
    # TN: 1 (idx 2)
    metrics = calculate_binary_metrics(y_true, y_pred)
    assert metrics["confusion_matrix"]["TP"] == 2
    assert metrics["confusion_matrix"]["FP"] == 1
    assert metrics["confusion_matrix"]["FN"] == 1
    assert metrics["confusion_matrix"]["TN"] == 1
    assert metrics["precision"] == 2 / 3
    assert metrics["recall"] == 2 / 3
    assert metrics["f1_score"] == 2 / 3


def test_validation_tooling_generate_and_eval(tmp_datastore: DataStore) -> None:
    store = tmp_datastore
    run_id = "run_val_test"
    store.insert_run(
        RunRecord(run_id=run_id, condition="baseline", config_hash="h1", start_time="2026-10-27")
    )

    # Insert 10 visits and classification records
    records = []
    for i in range(10):
        store.insert_visit(
            VisitRecord(
                visit_id=f"v_{i}",
                run_id=run_id,
                domain=f"domain{i}.com",
                initial_url=f"https://domain{i}.com/",
                status="ok",
                start_time="2026-10-27",
            )
        )
        records.append(
            ClassificationRecord(
                run_id=run_id,
                visit_id=f"v_{i}",
                domain=f"domain{i}.com",
                script_url=f"https://domain{i}.com/script.js",
                vector="canvas",
                flagged=1 if i < 5 else 0,
                confidence="high" if i < 5 else "none",
                evidence={"data": i},
            )
        )
    store.insert_visit(
        VisitRecord(
            visit_id="v_failed",
            run_id=run_id,
            domain="failed.example",
            initial_url="https://failed.example/",
            status="dns_error",
            start_time="2026-10-27",
        )
    )
    records.append(
        ClassificationRecord(
            run_id=run_id,
            visit_id="v_failed",
            domain="failed.example",
            script_url="https://failed.example/fp.js",
            vector="canvas",
            flagged=1,
            confidence="high",
            evidence={"data": "should not enter validation sample"},
        )
    )
    store.insert_classifications(records)

    tooling = ValidationTooling(store)
    with tempfile.TemporaryDirectory() as td:
        out_csv = Path(td) / "template.csv"
        out_ev = Path(td) / "evidence.json"

        # Generate sample template
        tooling.generate_stratified_sample(
            run_id, output_csv_path=out_csv, evidence_json_path=out_ev, sample_size=20
        )
        assert out_csv.is_file()
        assert out_ev.is_file()

        # Fill in ground truth labels
        lines = out_csv.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 11  # Header plus only the ten successful visits.
        assert "failed.example" not in "\n".join(lines)
        annotated_lines = [lines[0]]
        for line in lines[1:]:
            parts = line.split(",")
            parts[6] = parts[4]  # ground_truth = predicted_flag
            annotated_lines.append(",".join(parts))

        annotated_csv = Path(td) / "annotated.csv"
        annotated_csv.write_text("\n".join(annotated_lines), encoding="utf-8")

        eval_res = tooling.evaluate_labels(annotated_csv)
        assert eval_res["overall"]["precision"] == 1.0
        assert eval_res["overall"]["recall"] == 1.0


def test_breakage_analyzer(tmp_datastore: DataStore) -> None:
    store = tmp_datastore
    base_run = "run_health_base"
    treat_run = "run_health_treat"

    store.insert_run(
        RunRecord(run_id=base_run, condition="baseline", config_hash="h", start_time="2026")
    )
    store.insert_run(
        RunRecord(run_id=treat_run, condition="blocklist", config_hash="h", start_time="2026")
    )

    store.insert_visit(
        VisitRecord(
            visit_id="vb_1",
            run_id=base_run,
            domain="site1.com",
            initial_url="https://site1.com/",
            status="ok",
            load_time_ms=1200.0,
            console_errors_count=1,
            failed_requests_count=0,
            blocked_requests_count=0,
            start_time="2026",
        )
    )

    store.insert_visit(
        VisitRecord(
            visit_id="vt_1",
            run_id=treat_run,
            domain="site1.com",
            initial_url="https://site1.com/",
            status="ok",
            load_time_ms=900.0,
            console_errors_count=0,
            failed_requests_count=2,
            blocked_requests_count=2,
            start_time="2026",
        )
    )

    analyzer = BreakageAnalyzer(store)
    base_health = analyzer.analyze_run_health(base_run)
    assert base_health["success_rate"] == 1.0
    assert base_health["load_time_ms"]["median"] == 1200.0

    comp = analyzer.compare_breakage(base_run, treat_run)
    assert comp["delta_load_time_median_ms"] == -300.0  # Countermeasure loaded faster


def test_report_generator_plots_and_tables() -> None:
    with tempfile.TemporaryDirectory() as td:
        fig_dir = Path(td) / "figures"
        tab_dir = Path(td) / "tables"
        rep_gen = ReportGenerator(figures_dir=fig_dir, tables_dir=tab_dir)

        dummy_prev = {
            "by_vector": {
                "canvas": {
                    "prevalence": 0.05,
                    "ci_lower": 0.03,
                    "ci_upper": 0.08,
                    "count": 5,
                    "total": 100,
                },
                "webgl": {
                    "prevalence": 0.12,
                    "ci_lower": 0.08,
                    "ci_upper": 0.16,
                    "count": 12,
                    "total": 100,
                },
                "audio": {
                    "prevalence": 0.02,
                    "ci_lower": 0.01,
                    "ci_upper": 0.04,
                    "count": 2,
                    "total": 100,
                },
                "fonts": {
                    "prevalence": 0.15,
                    "ci_lower": 0.11,
                    "ci_upper": 0.20,
                    "count": 15,
                    "total": 100,
                },
            },
            "overall": {
                "prevalence": 0.22,
                "ci_lower": 0.17,
                "ci_upper": 0.28,
                "count": 22,
                "total": 100,
            },
        }

        # 1. Prevalence plot
        png, pdf = rep_gen.plot_prevalence_bars(dummy_prev, "test_prevalence")
        assert png.is_file() and png.stat().st_size > 0
        assert pdf.is_file() and pdf.stat().st_size > 0

        # 2. Comparison plot
        dummy_comp = {
            "binary_outcomes_mcnemar": {
                "any": {"baseline_prevalence": 0.25, "treatment_prevalence": 0.08},
                "canvas": {"baseline_prevalence": 0.05, "treatment_prevalence": 0.01},
                "webgl": {"baseline_prevalence": 0.12, "treatment_prevalence": 0.03},
                "audio": {"baseline_prevalence": 0.02, "treatment_prevalence": 0.00},
                "fonts": {"baseline_prevalence": 0.15, "treatment_prevalence": 0.04},
            }
        }
        png_c, pdf_c = rep_gen.plot_countermeasure_comparison(dummy_comp, "test_comp")
        assert png_c.is_file() and pdf_c.is_file()

        # 3. Failure taxonomy plot
        dummy_tax = {"ok": 90, "timeout": 5, "http_4xx": 3, "skipped_robots": 2}
        png_t, pdf_t = rep_gen.plot_failure_taxonomy(dummy_tax, "test_tax")
        assert png_t.is_file() and pdf_t.is_file()

        # 4. LaTeX and CSV export
        csv_p, tex_p = rep_gen.export_prevalence_table(dummy_prev, "test_table")
        assert csv_p.is_file() and tex_p.is_file()
        assert "\\begin{table}" in tex_p.read_text(encoding="utf-8")


def test_condition_classes_instantiation(test_config: StudyConfig) -> None:
    avail = get_available_conditions()
    assert "baseline" in avail
    assert "blocklist" in avail
    assert "canvas_defender" in avail
    assert "extension_ublock" in avail
    assert "brave_shields" in avail
    assert "firefox_rfp" in avail

    # Test BraveShields describe and self-check fallback
    brave_def = test_config.conditions.conditions.get("brave_shields")
    if brave_def:
        brave = BraveShieldsCondition(brave_def, test_config)
        desc = brave.describe()
        assert desc["name"] == "brave_shields"

    # Test Firefox describe
    fx_def = test_config.conditions.conditions.get("firefox_rfp")
    if fx_def:
        fx = FirefoxRFPCondition(fx_def, test_config)
        assert fx.describe()["name"] == "firefox_rfp"
