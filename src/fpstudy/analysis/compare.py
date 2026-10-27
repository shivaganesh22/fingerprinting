"""Paired countermeasure comparison using McNemar, Wilcoxon, and effect sizes."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy import stats

from fpstudy.storage.store import DataStore


def mcnemar_test_paired(
    baseline_flags: Sequence[bool | int],
    treatment_flags: Sequence[bool | int],
) -> dict[str, Any]:
    """Execute paired McNemar's test with exact binomial handling for small discordant counts.

    Contingency table:
      b: Baseline=1, Treatment=0 (defense succeeded in mitigating)
      c: Baseline=0, Treatment=1 (new FP observed)
      a: Baseline=1, Treatment=1
      d: Baseline=0, Treatment=0
    """
    if len(baseline_flags) != len(treatment_flags):
        raise ValueError("Baseline and treatment lists must have identical length")

    n = len(baseline_flags)
    if n == 0:
        return {"n": 0, "p_value": 1.0, "statistic": 0.0, "test_type": "none"}

    a = sum(1 for b, t in zip(baseline_flags, treatment_flags, strict=False) if bool(b) and bool(t))
    b = sum(
        1 for b, t in zip(baseline_flags, treatment_flags, strict=False) if bool(b) and not bool(t)
    )
    c = sum(
        1 for b, t in zip(baseline_flags, treatment_flags, strict=False) if not bool(b) and bool(t)
    )
    d = sum(
        1
        for b, t in zip(baseline_flags, treatment_flags, strict=False)
        if not bool(b) and not bool(t)
    )

    discordant = b + c

    # Exact binomial vs continuity-corrected chi2
    if discordant < 25:
        test_type = "exact_binomial"
        if discordant == 0:
            p_val = 1.0
            stat = 0.0
        else:
            # Two-sided binomial test under H0: p = 0.5
            k = min(b, c)
            # scipy.stats.binomtest
            res = stats.binomtest(k, n=discordant, p=0.5, alternative="two-sided")
            p_val = float(res.pvalue)
            stat = float(k)
    else:
        test_type = "continuity_corrected_chi2"
        chi2_stat = ((abs(b - c) - 1.0) ** 2) / discordant
        p_val = float(stats.chi2.sf(chi2_stat, df=1))
        stat = float(chi2_stat)

    # Effect measures
    arr = (b - c) / n  # Absolute Risk Reduction
    # Approximate SE for paired difference
    se_arr = math.sqrt((b + c - ((b - c) ** 2) / n) / (n**2)) if n > 1 else 0.0
    arr_ci = (arr - 1.96 * se_arr, arr + 1.96 * se_arr)

    # Odds ratio: b / c
    odds_ratio = (b / c) if c > 0 else (float("inf") if b > 0 else 1.0)

    p_baseline = (a + b) / n
    p_treatment = (a + c) / n
    relative_reduction = ((p_baseline - p_treatment) / p_baseline) if p_baseline > 0 else 0.0

    return {
        "n_paired": n,
        "contingency_table": {
            "a_both_fp": a,
            "b_baseline_only": b,
            "c_treatment_only": c,
            "d_neither_fp": d,
        },
        "statistic": stat,
        "p_value": p_val,
        "test_type": test_type,
        "absolute_risk_reduction": arr,
        "arr_ci_95": arr_ci,
        "odds_ratio": odds_ratio,
        "baseline_prevalence": p_baseline,
        "treatment_prevalence": p_treatment,
        "relative_reduction": relative_reduction,
    }


def hodges_lehmann_median_difference(x: Sequence[float], y: Sequence[float]) -> float:
    """Compute Hodges-Lehmann estimator of median difference for paired samples (Walsh averages)."""
    diffs = np.array(x, dtype=float) - np.array(y, dtype=float)
    if len(diffs) == 0:
        return 0.0
    # Average of all pairs (i <= j)
    # If sample is large, sample up to 10,000 pairs for efficiency
    n = len(diffs)
    if n > 200:
        rng = np.random.default_rng(42)
        idx1 = rng.choice(n, size=5000, replace=True)
        idx2 = rng.choice(n, size=5000, replace=True)
        pairwise = (diffs[idx1] + diffs[idx2]) / 2.0
    else:
        pairwise = [(diffs[i] + diffs[j]) / 2.0 for i in range(n) for j in range(i, n)]
    return float(np.median(pairwise))


def wilcoxon_signed_rank_paired(
    baseline_counts: Sequence[float | int],
    treatment_counts: Sequence[float | int],
) -> dict[str, Any]:
    """Execute Wilcoxon signed-rank test on paired count outcomes and compute rank-biserial r."""
    diffs = np.array(baseline_counts, dtype=float) - np.array(treatment_counts, dtype=float)
    non_zero = diffs[diffs != 0]
    n_nonzero = len(non_zero)

    if n_nonzero == 0:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "rank_biserial_r": 0.0,
            "median_difference": 0.0,
            "n_nonzero": 0,
        }

    # SciPy Wilcoxon
    try:
        w_res = stats.wilcoxon(diffs, zero_method="pratt", alternative="two-sided")
        stat = float(w_res.statistic)
        p_val = float(w_res.pvalue)
    except Exception:
        stat, p_val = 0.0, 1.0

    # Rank-biserial correlation: r = (W+ - W-) / (W+ + W-)
    ranks = stats.rankdata(np.abs(non_zero))
    w_plus = np.sum(ranks[non_zero > 0])
    w_minus = np.sum(ranks[non_zero < 0])
    total_w = w_plus + w_minus
    r_biserial = float((w_plus - w_minus) / total_w) if total_w > 0 else 0.0

    hl_median = hodges_lehmann_median_difference(baseline_counts, treatment_counts)

    return {
        "statistic": stat,
        "p_value": p_val,
        "rank_biserial_r": r_biserial,
        "median_difference": hl_median,
        "n_nonzero": n_nonzero,
    }


def holm_bonferroni_correction(p_values: list[float]) -> list[float]:
    """Apply family-wise Holm-Bonferroni correction to a list of p-values."""
    m = len(p_values)
    if m == 0:
        return []

    indexed_p = sorted(enumerate(p_values), key=lambda x: x[1])
    adjusted = [0.0] * m

    cum_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed_p):
        multiplier = m - rank
        p_adj = min(1.0, p * multiplier)
        cum_max = max(cum_max, p_adj)
        adjusted[orig_idx] = min(1.0, cum_max)

    return adjusted


class CountermeasureComparator:
    """Evaluates countermeasure efficacy through paired before/after domain comparison."""

    def __init__(self, store: DataStore):
        self.store = store

    def compare_runs(
        self,
        baseline_run_id: str,
        treatment_run_id: str,
    ) -> dict[str, Any]:
        """Perform full paired comparison across binary site flags and script counts."""
        base_visits = {v["domain"]: v for v in self.store.get_visits(baseline_run_id)}
        treat_visits = {v["domain"]: v for v in self.store.get_visits(treatment_run_id)}

        # Only pair domains that successfully returned 'ok' in BOTH conditions
        paired_domains = sorted(
            [
                d
                for d in base_visits
                if d in treat_visits
                and base_visits[d]["status"] == "ok"
                and treat_visits[d]["status"] == "ok"
            ]
        )

        base_class = self.store.get_classifications_for_run(baseline_run_id)
        treat_class = self.store.get_classifications_for_run(treatment_run_id)

        # Build domain vector lookup
        def build_domain_map(class_rows: list[dict[str, Any]]) -> dict[str, dict[str, bool]]:
            d_map: dict[str, dict[str, bool]] = {
                d: dict.fromkeys(["any", "canvas", "webgl", "audio", "fonts"], False)
                for d in paired_domains
            }
            for row in class_rows:
                dom = row["domain"]
                if dom in d_map and row["flagged"]:
                    vec = row["vector"]
                    d_map[dom][vec] = True
                    d_map[dom]["any"] = True
            return d_map

        base_map = build_domain_map(base_class)
        treat_map = build_domain_map(treat_class)

        vectors = ["any", "canvas", "webgl", "audio", "fonts"]
        vector_results = {}
        raw_p_values = []

        for vec in vectors:
            b_flags = [base_map[d][vec] for d in paired_domains]
            t_flags = [treat_map[d][vec] for d in paired_domains]
            mcn = mcnemar_test_paired(b_flags, t_flags)
            vector_results[vec] = mcn
            raw_p_values.append(mcn["p_value"])

        # Multiple testing correction
        adj_p = holm_bonferroni_correction(raw_p_values)
        for idx, vec in enumerate(vectors):
            vector_results[vec]["p_value_holm_adjusted"] = adj_p[idx]

        # Script count outcomes
        def count_flagged_scripts(class_rows: list[dict[str, Any]]) -> dict[str, int]:
            c_map: dict[str, int] = dict.fromkeys(paired_domains, 0)
            for row in class_rows:
                dom = row["domain"]
                if dom in c_map and row["flagged"]:
                    c_map[dom] += 1
            return c_map

        base_counts = count_flagged_scripts(base_class)
        treat_counts = count_flagged_scripts(treat_class)
        b_cnt_list = [base_counts[d] for d in paired_domains]
        t_cnt_list = [treat_counts[d] for d in paired_domains]

        wilcoxon_res = wilcoxon_signed_rank_paired(b_cnt_list, t_cnt_list)

        return {
            "baseline_run_id": baseline_run_id,
            "treatment_run_id": treatment_run_id,
            "n_paired_domains": len(paired_domains),
            "binary_outcomes_mcnemar": vector_results,
            "script_counts_wilcoxon": wilcoxon_res,
        }
