"""Publication-grade Matplotlib plotting routines and LaTeX table generators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class ReportGenerator:
    """Generates publication-quality figures (PNG/PDF) and LaTeX tables for the dissertation."""

    def __init__(
        self,
        figures_dir: Path | str = "reports/figures",
        tables_dir: Path | str = "reports/tables",
    ):
        self.figures_dir = Path(figures_dir)
        self.tables_dir = Path(tables_dir)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self._setup_style()

    def _setup_style(self) -> None:
        """Apply clean aesthetic formatting suitable for dissertation graphics."""
        plt.rcParams.update(
            {
                "font.family": "sans-serif",
                "font.size": 10,
                "axes.titlesize": 12,
                "axes.labelsize": 11,
                "xtick.labelsize": 9,
                "ytick.labelsize": 9,
                "figure.autolayout": True,
                "axes.edgecolor": "#444444",
                "axes.linewidth": 0.8,
                "grid.alpha": 0.3,
                "grid.linestyle": "--",
            }
        )

    def plot_prevalence_bars(
        self,
        prevalence_data: dict[str, Any],
        filename_base: str = "figure_prevalence_vectors",
    ) -> tuple[Path, Path]:
        """Plot prevalence proportions with 95% Wilson confidence interval error bars."""
        vectors = ["canvas", "webgl", "audio", "fonts"]
        labels = ["Canvas", "WebGL", "AudioContext", "Font Probing"]

        props = []
        err_low = []
        err_high = []

        by_vec = prevalence_data.get("by_vector", {})
        for v in vectors:
            v_data = by_vec.get(v, {})
            p = v_data.get("prevalence", 0.0)
            low = v_data.get("ci_lower", 0.0)
            high = v_data.get("ci_upper", 0.0)
            props.append(p * 100)
            err_low.append((p - low) * 100)
            err_high.append((high - p) * 100)

        # Include overall
        overall = prevalence_data.get("overall", {})
        p_ov = overall.get("prevalence", 0.0)
        props.append(p_ov * 100)
        err_low.append((p_ov - overall.get("ci_lower", 0.0)) * 100)
        err_high.append((overall.get("ci_upper", 0.0) - p_ov) * 100)
        labels.append("Overall (Any)")

        fig, ax = plt.subplots(figsize=(7, 4.2), dpi=300)
        x = np.arange(len(labels))
        colors = ["#2b5c8f", "#3e7cb1", "#68a3c8", "#88b7d5", "#e76f51"]

        yerr = [err_low, err_high]
        bars = ax.bar(
            x, props, yerr=yerr, capsize=4, color=colors, edgecolor="#222222", linewidth=0.8
        )

        ax.set_ylabel("Prevalence (%)")
        ax.set_title("Prevalence of Browser Fingerprinting Vectors (with 95% Wilson CIs)")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.grid(axis="y")
        ax.set_ylim(0, max(props + [10]) * 1.25)

        for bar in bars:
            h = bar.get_height()
            ax.annotate(
                f"{h:.1f}%",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        png_path = self.figures_dir / f"{filename_base}.png"
        pdf_path = self.figures_dir / f"{filename_base}.pdf"
        fig.savefig(png_path)
        fig.savefig(pdf_path)
        plt.close(fig)
        return png_path, pdf_path

    def plot_countermeasure_comparison(
        self,
        comparison_data: dict[str, Any],
        filename_base: str = "figure_countermeasure_comparison",
    ) -> tuple[Path, Path]:
        """Plot paired before/after prevalence comparison showing countermeasure mitigation."""
        vectors = ["any", "canvas", "webgl", "audio", "fonts"]
        labels = ["Overall", "Canvas", "WebGL", "Audio", "Fonts"]

        base_vals = []
        treat_vals = []

        mcn = comparison_data.get("binary_outcomes_mcnemar", {})
        for v in vectors:
            v_res = mcn.get(v, {})
            base_vals.append(v_res.get("baseline_prevalence", 0.0) * 100)
            treat_vals.append(v_res.get("treatment_prevalence", 0.0) * 100)

        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
        x = np.arange(len(labels))
        width = 0.35

        ax.bar(x - width / 2, base_vals, width, label="Baseline", color="#457b9d", edgecolor="#222")
        ax.bar(
            x + width / 2,
            treat_vals,
            width,
            label="Countermeasure",
            color="#2a9d8f",
            edgecolor="#222",
        )

        ax.set_ylabel("Prevalence on Paired Domains (%)")
        ax.set_title("Tracking Exposure Reduction Across Countermeasure Conditions")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        ax.grid(axis="y")

        png_path = self.figures_dir / f"{filename_base}.png"
        pdf_path = self.figures_dir / f"{filename_base}.pdf"
        fig.savefig(png_path)
        fig.savefig(pdf_path)
        plt.close(fig)
        return png_path, pdf_path

    def plot_failure_taxonomy(
        self,
        status_breakdown: dict[str, int],
        filename_base: str = "figure_failure_taxonomy",
    ) -> tuple[Path, Path]:
        """Plot horizontal bar chart of crawler visit outcomes."""
        fig, ax = plt.subplots(figsize=(7, 3.8), dpi=300)

        statuses = list(status_breakdown.keys())
        counts = [status_breakdown[s] for s in statuses]
        y = np.arange(len(statuses))

        colors = ["#2a9d8f" if s == "ok" else "#e76f51" for s in statuses]
        ax.barh(y, counts, color=colors, edgecolor="#222")
        ax.set_yticks(y)
        ax.set_yticklabels(statuses)
        ax.set_xlabel("Number of Visits")
        ax.set_title("Crawler Visit Failure Taxonomy and Outcome Breakdown")
        ax.grid(axis="x")

        png_path = self.figures_dir / f"{filename_base}.png"
        pdf_path = self.figures_dir / f"{filename_base}.pdf"
        fig.savefig(png_path)
        fig.savefig(pdf_path)
        plt.close(fig)
        return png_path, pdf_path

    def export_prevalence_table(
        self,
        prevalence_data: dict[str, Any],
        filename_base: str = "table_prevalence_summary",
    ) -> tuple[Path, Path]:
        """Export prevalence statistics as both CSV and publication-ready LaTeX snippet."""
        rows = []
        vectors = ["canvas", "webgl", "audio", "fonts"]

        by_vec = prevalence_data.get("by_vector", {})
        for v in vectors:
            v_data = by_vec.get(v, {})
            rows.append(
                {
                    "Vector": v.capitalize(),
                    "Count": v_data.get("count", 0),
                    "Total": v_data.get("total", 0),
                    "Prevalence (%)": f"{v_data.get('prevalence', 0.0) * 100:.2f}%",
                    "95% CI Lower": f"{v_data.get('ci_lower', 0.0) * 100:.2f}%",
                    "95% CI Upper": f"{v_data.get('ci_upper', 0.0) * 100:.2f}%",
                }
            )

        overall = prevalence_data.get("overall", {})
        rows.append(
            {
                "Vector": "Overall (Any Vector)",
                "Count": overall.get("count", 0),
                "Total": overall.get("total", 0),
                "Prevalence (%)": f"{overall.get('prevalence', 0.0) * 100:.2f}%",
                "95% CI Lower": f"{overall.get('ci_lower', 0.0) * 100:.2f}%",
                "95% CI Upper": f"{overall.get('ci_upper', 0.0) * 100:.2f}%",
            }
        )

        df = pd.DataFrame(rows)
        csv_path = self.tables_dir / f"{filename_base}.csv"
        df.to_csv(csv_path, index=False)

        col_align = "l" + "r" * (len(df.columns) - 1)
        header_str = " & ".join(df.columns) + " \\\\"
        row_strs = [" & ".join(str(val) for val in row) + " \\\\" for row in df.values]

        latex_snippet = (
            "\\begin{table}[htbp]\n"
            "\\centering\n"
            "\\caption{Prevalence of Browser Fingerprinting Vectors with 95\\% Wilson CIs}\n"
            "\\label{tab:prevalence_summary}\n"
            f"\\begin{{tabular}}{{{col_align}}}\n"
            "\\hline\n"
            f"{header_str}\n"
            "\\hline\n" + "\n".join(row_strs) + "\n\\hline\n"
            "\\end{tabular}\n"
            "\\end{table}\n"
        )
        tex_path = self.tables_dir / f"{filename_base}.tex"
        tex_path.write_text(latex_snippet, encoding="utf-8")

        return csv_path, tex_path
