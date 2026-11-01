"""Unit tests verifying statistical calculations against scipy and statsmodels references."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.contingency_tables import mcnemar as sm_mcnemar
from statsmodels.stats.proportion import proportion_confint

from fpstudy.analysis.compare import (
    hodges_lehmann_median_difference,
    holm_bonferroni_correction,
    mcnemar_test_paired,
    wilcoxon_signed_rank_paired,
)
from fpstudy.analysis.prevalence import wilson_score_interval


def test_wilson_score_interval_against_statsmodels() -> None:
    test_cases = [
        (0, 10),
        (10, 10),
        (50, 100),
        (12, 1000),
        (850, 1000),
    ]

    for k, n in test_cases:
        p, low, high = wilson_score_interval(k, n, confidence=0.95)
        sm_low, sm_high = proportion_confint(k, n, alpha=0.05, method="wilson")

        assert pytest.approx(p, abs=1e-5) == k / n
        assert pytest.approx(low, abs=1e-4) == sm_low
        assert pytest.approx(high, abs=1e-4) == sm_high


def test_mcnemar_paired_against_reference() -> None:
    # 1. Exact binomial test case: b=15, c=2, discordant < 25
    base_flags = [1] * 15 + [0] * 2 + [1] * 10 + [0] * 50
    treat_flags = [0] * 15 + [1] * 2 + [1] * 10 + [0] * 50

    res_exact = mcnemar_test_paired(base_flags, treat_flags)
    assert res_exact["test_type"] == "exact_binomial"
    # Scipy binomtest for k=2, n=17, p=0.5
    expected_p = float(stats.binomtest(2, 17, 0.5, alternative="two-sided").pvalue)
    assert pytest.approx(res_exact["p_value"], abs=1e-4) == expected_p
    assert res_exact["absolute_risk_reduction"] > 0

    no_discordance = mcnemar_test_paired([1, 0, 1], [1, 0, 1])
    assert no_discordance["absolute_risk_reduction"] == 0
    assert no_discordance["arr_ci_95"] is None
    assert no_discordance["arr_ci_method"] is None

    # 2. Asymptotic / continuity corrected case: b=40, c=10 (discordant = 50 >= 25)
    base_large = [1] * 40 + [0] * 10 + [1] * 20 + [0] * 20
    treat_large = [0] * 40 + [1] * 10 + [1] * 20 + [0] * 20

    res_asymp = mcnemar_test_paired(base_large, treat_large)
    assert res_asymp["test_type"] == "continuity_corrected_chi2"
    # Contingency table [[20, 40], [10, 20]]
    table = [[20, 40], [10, 20]]
    sm_res = sm_mcnemar(table, exact=False, correction=True)
    assert pytest.approx(res_asymp["statistic"], abs=1e-4) == float(sm_res.statistic)
    assert pytest.approx(res_asymp["p_value"], abs=1e-4) == float(sm_res.pvalue)


def test_wilcoxon_paired_against_scipy() -> None:
    rng = np.random.default_rng(42)
    base_counts = rng.poisson(lam=5, size=50)
    treat_counts = rng.poisson(lam=2, size=50)

    res = wilcoxon_signed_rank_paired(base_counts, treat_counts)

    diffs = base_counts - treat_counts
    scipy_w = stats.wilcoxon(diffs, zero_method="pratt")
    assert pytest.approx(res["statistic"], abs=1e-3) == float(scipy_w.statistic)
    assert pytest.approx(res["p_value"], abs=1e-3) == float(scipy_w.pvalue)
    assert res["rank_biserial_r"] > 0  # Treatment reduces counts


def test_hodges_lehmann_median() -> None:
    x = [5.0, 6.0, 7.0]
    y = [1.0, 2.0, 3.0]
    # diffs are all 4.0
    hl = hodges_lehmann_median_difference(x, y)
    assert hl == 4.0


def test_holm_bonferroni_correction() -> None:
    raw_p = [0.01, 0.04, 0.03]
    # Sorted: p1=0.01 (m=3 -> 0.03), p2=0.03 (m=2 -> 0.06), p3=0.04 (m=1 -> 0.06)
    adj = holm_bonferroni_correction(raw_p)
    assert pytest.approx(adj[0], abs=1e-4) == 0.03
    assert pytest.approx(adj[1], abs=1e-4) == 0.06
    assert pytest.approx(adj[2], abs=1e-4) == 0.06
