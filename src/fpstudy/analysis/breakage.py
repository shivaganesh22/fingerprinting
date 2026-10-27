"""Page breakage and health comparison across experimental conditions."""

from __future__ import annotations

from typing import Any

import numpy as np

from fpstudy.storage.store import DataStore


class BreakageAnalyzer:
    """Evaluates whether countermeasures degrade page performance or cause functional breakage."""

    def __init__(self, store: DataStore):
        self.store = store

    def analyze_run_health(self, run_id: str) -> dict[str, Any]:
        """Compute performance and health metrics for a run."""
        visits = self.store.get_visits(run_id)
        if not visits:
            return {
                "run_id": run_id,
                "total_visits": 0,
                "success_rate": 0.0,
                "load_time_ms": {"mean": 0.0, "median": 0.0, "std": 0.0, "p95": 0.0},
                "console_errors_per_page": {"mean": 0.0, "median": 0.0},
                "failed_requests_per_page": {"mean": 0.0, "median": 0.0},
                "blocked_requests_per_page": {"mean": 0.0, "median": 0.0},
            }

        total = len(visits)
        ok_visits = [v for v in visits if v["status"] == "ok"]
        n_ok = len(ok_visits)

        load_times = [v["load_time_ms"] for v in ok_visits if v["load_time_ms"] is not None]
        console_errors = [v["console_errors_count"] for v in ok_visits]
        failed_requests = [v["failed_requests_count"] for v in ok_visits]
        blocked_requests = [v["blocked_requests_count"] for v in ok_visits]

        return {
            "run_id": run_id,
            "total_visits": total,
            "success_rate": (n_ok / total) if total > 0 else 0.0,
            "load_time_ms": {
                "mean": float(np.mean(load_times)) if load_times else 0.0,
                "median": float(np.median(load_times)) if load_times else 0.0,
                "std": float(np.std(load_times)) if load_times else 0.0,
                "p95": float(np.percentile(load_times, 95)) if load_times else 0.0,
            },
            "console_errors_per_page": {
                "mean": float(np.mean(console_errors)) if console_errors else 0.0,
                "median": float(np.median(console_errors)) if console_errors else 0.0,
            },
            "failed_requests_per_page": {
                "mean": float(np.mean(failed_requests)) if failed_requests else 0.0,
                "median": float(np.median(failed_requests)) if failed_requests else 0.0,
            },
            "blocked_requests_per_page": {
                "mean": float(np.mean(blocked_requests)) if blocked_requests else 0.0,
                "median": float(np.median(blocked_requests)) if blocked_requests else 0.0,
            },
        }

    def compare_breakage(self, baseline_run_id: str, treatment_run_id: str) -> dict[str, Any]:
        """Compare health and breakage metrics between baseline and treatment."""
        base_health = self.analyze_run_health(baseline_run_id)
        treat_health = self.analyze_run_health(treatment_run_id)

        delta_success_rate = treat_health["success_rate"] - base_health["success_rate"]
        delta_load_time_median = (
            treat_health["load_time_ms"]["median"] - base_health["load_time_ms"]["median"]
        )

        return {
            "baseline": base_health,
            "treatment": treat_health,
            "delta_success_rate": delta_success_rate,
            "delta_load_time_median_ms": delta_load_time_median,
        }
