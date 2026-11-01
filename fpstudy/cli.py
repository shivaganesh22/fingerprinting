"""Command-line interface for the fingerprinting study pipeline using Typer."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fpstudy.analysis.breakage import BreakageAnalyzer
from fpstudy.analysis.compare import CountermeasureComparator
from fpstudy.analysis.plots import ReportGenerator
from fpstudy.analysis.prevalence import PrevalenceAnalyzer
from fpstudy.analysis.validation import ValidationTooling
from fpstudy.config import load_study_config
from fpstudy.crawler.browser import BrowserManager
from fpstudy.crawler.conditions import get_available_conditions
from fpstudy.crawler.runner import CrawlRunner
from fpstudy.detection.classify import ScriptClassifier
from fpstudy.sample import SampleManager
from fpstudy.storage.store import DataStore

app = typer.Typer(
    name="fpstudy",
    help="Browser Fingerprinting Measurement Pipeline and Privacy Countermeasure Evaluator.",
    add_completion=False,
)
console = Console()


def setup_logging(json_format: bool = False, verbose: bool = False) -> None:
    """Configure console or JSON structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    if json_format:

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                log_obj = {
                    "timestamp": self.formatTime(record, self.datefmt),
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                }
                return json.dumps(log_obj)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logging.root.handlers = [handler]
        logging.root.setLevel(level)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


@app.command()
def sample(
    config_file: str = typer.Option("config/default.yaml", help="Path to default config"),
    list_id: str | None = typer.Option(None, help="Tranco list ID (overrides config)"),
    top_n: int | None = typer.Option(None, help="Top N domains to sample"),
    sector_file: str | None = typer.Option(None, help="Optional CSV with sector domain subset"),
    json_log: bool = typer.Option(False, "--json", help="Output JSON logs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Download Tranco list, verify SHA-256 manifest, and extract deterministic domain sample."""
    setup_logging(json_log, verbose)
    cfg = load_study_config(config_file)
    active_list_id = list_id or cfg.sample.tranco_list_id
    active_top_n = top_n or cfg.sample.top_n
    active_sector = sector_file or cfg.sample.sector_file

    manager = SampleManager(
        download_dir=cfg.sample.download_dir,
        manifest_path=cfg.sample.manifest_path,
    )
    console.print(f"[bold blue]Downloading/Verifying Tranco list {active_list_id}...[/bold blue]")
    try:
        csv_path = manager.download_tranco(active_list_id)
        domains = manager.get_sample(csv_path, active_top_n, active_sector)
        console.print(f"[bold green]Successfully sampled {len(domains)} domains.[/bold green]")
        if domains:
            console.print(f"Sample preview: {domains[:5]} ...")
    except Exception as exc:
        console.print(f"[bold red]Sampling failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def crawl(
    condition: str = typer.Option("baseline", help="Countermeasure condition to run"),
    config_file: str = typer.Option("config/default.yaml", help="Path to master config"),
    limit: int | None = typer.Option(None, help="Limit number of domains for testing"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume interrupted crawl"),
    json_log: bool = typer.Option(False, "--json", help="Output JSON logs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run automated crawler across sampled domains for a specific experimental condition."""
    setup_logging(json_log, verbose)
    cfg = load_study_config(config_file)

    # Load domains
    sample_mgr = SampleManager(cfg.sample.download_dir, cfg.sample.manifest_path)
    sample_csv = cfg.sample.download_dir / f"tranco_{cfg.sample.tranco_list_id}.csv"
    if not sample_csv.is_file():
        console.print(
            f"[bold red]Pinned Tranco file not found: {sample_csv}. "
            "Run 'fpstudy sample' before crawling.[/bold red]"
        )
        raise typer.Exit(code=1)
    try:
        sample_mgr.verify_manifest(cfg.sample.tranco_list_id, sample_csv)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        console.print(f"[bold red]Tranco sample verification failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    domains = sample_mgr.get_sample(sample_csv, cfg.sample.top_n, cfg.sample.sector_file)
    if limit is not None:
        domains = domains[:limit]

    runner = CrawlRunner(cfg, condition_name=condition)
    console.print(
        f"[bold blue]Launching crawl for condition '{condition}' on {len(domains)} domains...[/bold blue]"
    )

    try:
        run_rec = asyncio.run(runner.run(domains, resume=resume, limit=limit))
        console.print(
            f"[bold green]Crawl run completed successfully: {run_rec.run_id}[/bold green]"
        )
    except Exception as exc:
        console.print(f"[bold red]Crawl failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def classify(
    run_id: str = typer.Option(..., "--run-id", help="Run ID to classify from raw events"),
    config_file: str = typer.Option("config/default.yaml", help="Path to config"),
    json_log: bool = typer.Option(False, "--json", help="Output JSON logs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Derive rule-based fingerprinting classifications directly from stored raw events."""
    setup_logging(json_log, verbose)
    cfg = load_study_config(config_file)
    classifier = ScriptClassifier(cfg)

    console.print(f"[bold blue]Classifying raw events for run '{run_id}'...[/bold blue]")
    try:
        res = classifier.classify_run(run_id)
        console.print("[bold green]Classification complete![/bold green]")
        console.print(
            f"Successful sites: {res['successful_sites']}/{res['total_sites_visited']} | "
            f"Sites with a detected signal: {res['sites_fingerprinting']}/"
            f"{res['successful_sites']} ({res['overall_prevalence'] * 100:.1f}%)"
        )
    except Exception as exc:
        console.print(f"[bold red]Classification failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def validate(
    labels: str = typer.Option(
        "data/labelled/validation_sample_template.csv", help="Path to CSV with ground truth"
    ),
    run_id: str | None = typer.Option(None, help="Run ID to draw fresh sample from"),
    generate_sample: bool = typer.Option(
        False, "--sample", help="Generate fresh stratified sample for annotation"
    ),
    config_file: str = typer.Option("config/default.yaml", help="Path to config"),
) -> None:
    """Evaluate detector precision/recall or generate stratified ground-truth sample for labelling."""
    cfg = load_study_config(config_file)
    store = DataStore(cfg.storage.database_path)
    tooling = ValidationTooling(store)

    if generate_sample:
        if not run_id:
            console.print("[bold red]Must provide --run-id when generating sample[/bold red]")
            raise typer.Exit(code=1)
        csv_out = tooling.generate_stratified_sample(run_id, output_csv_path=labels)
        console.print(
            f"[bold green]Stratified validation template generated at {csv_out}[/bold green]"
        )
        return

    if not Path(labels).is_file():
        console.print(
            f"[bold yellow]Notice:[/bold yellow] Labelled file not found: {labels}. Run with --sample to generate template."
        )
        return

    console.print(
        f"[bold blue]Evaluating classifications against labels at {labels}...[/bold blue]"
    )
    try:
        metrics = tooling.evaluate_labels(labels)
        if "error" in metrics:
            console.print(f"[bold yellow]Notice:[/bold yellow] {metrics['error']}")
            return

        table = Table(title="Classifier Validation Metrics (Precision / Recall / F1)")
        table.add_column("Vector", justify="left", style="cyan")
        table.add_column("Precision", justify="right")
        table.add_column("Recall", justify="right")
        table.add_column("F1 Score", justify="right")
        table.add_column("Accuracy", justify="right")

        ov = metrics["overall"]
        table.add_row(
            "Overall",
            f"{ov['precision']:.3f}",
            f"{ov['recall']:.3f}",
            f"{ov['f1_score']:.3f}",
            f"{ov['accuracy']:.3f}",
        )

        for vec, v_m in metrics.get("per_vector", {}).items():
            table.add_row(
                vec.capitalize(),
                f"{v_m['precision']:.3f}",
                f"{v_m['recall']:.3f}",
                f"{v_m['f1_score']:.3f}",
                f"{v_m['accuracy']:.3f}",
            )

        console.print(table)
    except Exception as exc:
        console.print(f"[bold red]Validation failed:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def analyse(
    baseline: str = typer.Option(..., "--baseline", help="Baseline run ID"),
    compare: list[str] = typer.Option(..., "--compare", help="Countermeasure run ID(s) to compare"),
    config_file: str = typer.Option("config/default.yaml", help="Path to config"),
) -> None:
    """Run paired McNemar, Wilcoxon, and breakage comparisons between baseline and countermeasures."""
    cfg = load_study_config(config_file)
    store = DataStore(cfg.storage.database_path)
    prev_analyzer = PrevalenceAnalyzer(store)
    comparator = CountermeasureComparator(store)
    breakage = BreakageAnalyzer(store)
    report_gen = ReportGenerator()

    console.print(f"[bold blue]Computing prevalence for baseline: {baseline}[/bold blue]")
    base_prev = prev_analyzer.compute_prevalence(baseline)
    report_gen.plot_prevalence_bars(base_prev, filename_base=f"figure_prevalence_{baseline}")
    report_gen.export_prevalence_table(base_prev, filename_base=f"table_prevalence_{baseline}")

    for treat_id in compare:
        console.print(
            f"[bold blue]Comparing baseline ({baseline}) against countermeasure ({treat_id})...[/bold blue]"
        )
        comp_res = comparator.compare_runs(baseline, treat_id)
        breakage.compare_breakage(baseline, treat_id)

        report_gen.plot_countermeasure_comparison(
            comp_res, filename_base=f"figure_comparison_{treat_id}"
        )

        table = Table(title=f"Paired McNemar Comparison: Baseline vs {treat_id}")
        table.add_column("Vector", justify="left", style="cyan")
        table.add_column("Paired N", justify="right")
        table.add_column("Base Prev", justify="right")
        table.add_column("Treat Prev", justify="right")
        table.add_column("ARR (95% CI)", justify="center")
        table.add_column("p-value (Holm)", justify="right")

        for vec, res in comp_res.get("binary_outcomes_mcnemar", {}).items():
            arr = res.get("absolute_risk_reduction", 0.0)
            ci = res.get("arr_ci_95")
            ci_text = (
                f"{arr * 100:.1f}% [{ci[0] * 100:.1f}%, {ci[1] * 100:.1f}%]"
                if ci is not None
                else f"{arr * 100:.1f}% (N/A)"
            )
            table.add_row(
                vec.capitalize(),
                str(res.get("n_paired", 0)),
                f"{res.get('baseline_prevalence', 0.0) * 100:.1f}%",
                f"{res.get('treatment_prevalence', 0.0) * 100:.1f}%",
                ci_text,
                f"{res.get('p_value_holm_adjusted', 1.0):.4f}",
            )
        console.print(table)


@app.command()
def report(
    config_file: str = typer.Option("config/default.yaml", help="Path to config"),
) -> None:
    """Regenerate all figures, tables, and summaries from existing stored crawl data."""
    cfg = load_study_config(config_file)
    store = DataStore(cfg.storage.database_path)
    prev = PrevalenceAnalyzer(store)
    report_gen = ReportGenerator()

    # Find runs in database
    with store._get_connection() as conn:
        runs = [
            r["run_id"]
            for r in conn.execute("SELECT run_id FROM runs ORDER BY start_time DESC").fetchall()
        ]

    if not runs:
        console.print(
            "[bold yellow]No completed crawl runs found in storage database.[/bold yellow]"
        )
        return

    console.print(f"[bold blue]Regenerating reports for {len(runs)} runs...[/bold blue]")
    for r_id in runs:
        try:
            p_data = prev.compute_prevalence(r_id)
            report_gen.plot_prevalence_bars(p_data, filename_base=f"figure_prevalence_{r_id}")
            report_gen.export_prevalence_table(p_data, filename_base=f"table_prevalence_{r_id}")
            if "denominator" in p_data and "status_breakdown" in p_data["denominator"]:
                report_gen.plot_failure_taxonomy(
                    p_data["denominator"]["status_breakdown"],
                    filename_base=f"figure_failure_taxonomy_{r_id}",
                )
        except Exception as exc:
            console.print(f"[yellow]Could not generate report for {r_id}: {exc}[/yellow]")

    console.print("[bold green]All report figures and tables generated in reports/[/bold green]")


@app.command()
def selfcheck(
    config_file: str = typer.Option("config/default.yaml", help="Path to config"),
) -> None:
    """Verify host environment, Playwright browsers, hooks stealth, and condition canaries."""
    console.print("[bold blue]Running system self-check and canary verifications...[/bold blue]")
    cfg = load_study_config(config_file)

    async def _async_selfcheck() -> bool:
        all_passed = True
        bm = BrowserManager(cfg, "baseline")
        try:
            browser = await bm.start()
            console.print("  [green]✓[/green] Playwright Chromium launched successfully.")

            # Canary checks for all enabled conditions
            for cond_name in get_available_conditions():
                cond_def = cfg.conditions.conditions.get(cond_name)
                if cond_def and cond_def.enabled:
                    bm_cond = BrowserManager(cfg, cond_name)
                    try:
                        res = await bm_cond.condition.self_check(browser)
                        if res.get("passed"):
                            console.print(
                                f"  [green]✓[/green] Condition canary passed: [cyan]{cond_name}[/cyan]"
                            )
                        else:
                            console.print(
                                f"  [red]✗[/red] Condition canary failed: [cyan]{cond_name}[/cyan] ({res.get('details')})"
                            )
                            all_passed = False
                    except Exception as e:
                        console.print(
                            f"  [red]✗[/red] Condition canary error: [cyan]{cond_name}[/cyan] ({e})"
                        )
                        all_passed = False
                    finally:
                        await bm_cond.close()

        except Exception as exc:
            console.print(f"  [red]✗[/red] Browser self-check failed: {exc}")
            all_passed = False
        finally:
            await bm.close()

        return all_passed

    passed = asyncio.run(_async_selfcheck())
    if passed:
        console.print("[bold green]All environment checks and canaries PASSED.[/bold green]")
        sys.exit(0)
    else:
        console.print("[bold red]Self-check encountered failures.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
