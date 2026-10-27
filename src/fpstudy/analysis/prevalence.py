"""Prevalence estimation, Wilson score confidence intervals, and breakdowns."""

from __future__ import annotations

import math
from typing import Any

from fpstudy.storage.store import DataStore


def wilson_score_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Calculate the Wilson score confidence interval for a binomial proportion.

    Returns (proportion, lower_bound, upper_bound).
    """
    if total <= 0:
        return 0.0, 0.0, 0.0

    p = successes / total
    # z for 95% is 1.959963984540054
    # Standard normal quantile approximations
    z_map = {
        0.90: 1.6448536269514722,
        0.95: 1.959963984540054,
        0.99: 2.5758293035489004,
    }
    z = z_map.get(round(confidence, 2), 1.959964)

    denominator = 1.0 + (z**2) / total
    center = (p + (z**2) / (2.0 * total)) / denominator
    margin = (z * math.sqrt((p * (1.0 - p) / total) + (z**2) / (4.0 * (total**2)))) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return p, lower, upper


class PrevalenceAnalyzer:
    """Computes prevalence rates, Wilson CIs, and stratified breakdowns for a crawl run."""

    def __init__(self, store: DataStore):
        self.store = store

    def compute_prevalence(self, run_id: str) -> dict[str, Any]:
        """Compute prevalence per vector and overall among successfully visited domains."""
        visits = self.store.get_visits(run_id)
        classifications = self.store.get_classifications_for_run(run_id)

        # Failure table / denominator accounting
        total_visits = len(visits)
        status_counts: dict[str, int] = {}
        for v in visits:
            st = v["status"]
            status_counts[st] = status_counts.get(st, 0) + 1

        successful_visits = [v for v in visits if v["status"] == "ok"]
        n_successful = len(successful_visits)
        ok_domains = {v["domain"] for v in successful_visits}

        # Track vectors per domain
        domain_vectors: dict[str, set] = {d: set() for d in ok_domains}
        domain_3p: dict[str, bool] = dict.fromkeys(ok_domains, False)
        domain_1p: dict[str, bool] = dict.fromkeys(ok_domains, False)
        provider_counts: dict[str, int] = {}

        for c in classifications:
            dom = c["domain"]
            if dom not in ok_domains:
                continue
            if c["flagged"]:
                vector = c["vector"]
                domain_vectors[dom].add(vector)
                if c["is_third_party"]:
                    domain_3p[dom] = True
                else:
                    domain_1p[dom] = True

                s_url = c["script_url"]
                provider_counts[s_url] = provider_counts.get(s_url, 0) + 1

        vectors = ["canvas", "webgl", "audio", "fonts"]
        vector_stats: dict[str, Any] = {}

        for vec in vectors:
            count = sum(1 for d in ok_domains if vec in domain_vectors[d])
            prop, low, high = wilson_score_interval(count, n_successful)
            vector_stats[vec] = {
                "count": count,
                "total": n_successful,
                "prevalence": prop,
                "ci_lower": low,
                "ci_upper": high,
            }

        # Overall (any vector)
        any_count = sum(1 for d in ok_domains if len(domain_vectors[d]) > 0)
        overall_prop, overall_low, overall_high = wilson_score_interval(any_count, n_successful)

        # 1p vs 3p
        count_3p = sum(1 for d in ok_domains if domain_3p[d])
        count_1p = sum(1 for d in ok_domains if domain_1p[d])
        p_3p, low_3p, high_3p = wilson_score_interval(count_3p, n_successful)
        p_1p, low_1p, high_1p = wilson_score_interval(count_1p, n_successful)

        return {
            "run_id": run_id,
            "denominator": {
                "total_attempted": total_visits,
                "successful_ok": n_successful,
                "status_breakdown": status_counts,
            },
            "overall": {
                "count": any_count,
                "total": n_successful,
                "prevalence": overall_prop,
                "ci_lower": overall_low,
                "ci_upper": overall_high,
            },
            "by_vector": vector_stats,
            "party_breakdown": {
                "third_party": {
                    "count": count_3p,
                    "prevalence": p_3p,
                    "ci_lower": low_3p,
                    "ci_upper": high_3p,
                },
                "first_party": {
                    "count": count_1p,
                    "prevalence": p_1p,
                    "ci_lower": low_1p,
                    "ci_upper": high_1p,
                },
            },
            "top_providers": sorted(provider_counts.items(), key=lambda x: x[1], reverse=True)[:15],
        }

    def compute_rank_band_breakdown(
        self,
        run_id: str,
        domain_ranks: dict[str, int],
        bands: list[tuple[int, int]] | None = None,
    ) -> list[dict[str, Any]]:
        """Compute prevalence stratified by Tranco rank bands (e.g. 1-100, 101-500, 501-1000)."""
        if bands is None:
            bands = [(1, 100), (101, 500), (501, 1000), (1001, 5000)]

        visits = self.store.get_visits(run_id)
        classifications = self.store.get_classifications_for_run(run_id)

        ok_visits = {v["domain"] for v in visits if v["status"] == "ok"}
        fp_domains = {c["domain"] for c in classifications if c["flagged"]}

        results = []
        for start, end in bands:
            band_domains = [d for d in ok_visits if start <= domain_ranks.get(d, 999999) <= end]
            total_in_band = len(band_domains)
            fp_in_band = sum(1 for d in band_domains if d in fp_domains)
            prop, low, high = wilson_score_interval(fp_in_band, total_in_band)

            results.append(
                {
                    "band": f"{start}-{end}",
                    "start_rank": start,
                    "end_rank": end,
                    "total_domains": total_in_band,
                    "flagged_domains": fp_in_band,
                    "prevalence": prop,
                    "ci_lower": low,
                    "ci_upper": high,
                }
            )

        return results
