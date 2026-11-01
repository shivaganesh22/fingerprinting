# Baseline crawl: first 100 Tranco domains

**Run ID:** `run_baseline_20261028_081315_49e14b`  
**Condition:** baseline Chromium  
**List:** Tranco `GQ3LK`, first 100 ranks  
**Run status:** completed; baseline canary passed

## Crawl outcome

The run created 100 visit records. The status breakdown was:

| Visit status | Count |
|---|---:|
| `ok` | 52 |
| `skipped_robots` | 7 |
| `dns_error` | 24 |
| `http_4xx` | 5 |
| `blocked_bot_suspected` | 2 |
| `other` | 3 |
| `timeout` | 7 |
| **Total** | **100** |

Only the 52 `ok` visits were used as the denominator for the prevalence estimates. Robots skips and other failed visits are missing observations, not negatives.

## Fingerprinting signals in successful visits

| Vector | Sites flagged | Prevalence | 95% Wilson CI |
|---|---:|---:|---:|
| Canvas | 4/52 | 7.69% | 3.03–18.17% |
| WebGL | 18/52 | 34.62% | 23.15–48.20% |
| Audio | 4/52 | 7.69% | 3.03–18.17% |
| Fonts | 3/52 | 5.77% | 1.98–15.64% |
| Any configured vector | 18/52 | 34.62% | 23.15–48.20% |

These are rule-based detections during a passive, roughly 12-second Chromium visit. They describe the observed sample and configuration; they do not establish tracking intent or prevalence across the web.

## Data-quality note

An earlier version of the classifier summary counted one flagged site whose visit did not finish with status `ok`, yielding 19/100. The summary logic has since been corrected to use successful visits only; the appropriate descriptive result is 18/52 (34.6%). The crawl itself and its stored events were not changed.

## Limitations

- The 48 non-`ok` records mean nearly half of the selected sample did not produce eligible observations. Any estimate may be biased if failures are associated with site type or defenses.
- The sample uses the first 100 ranks of one pinned Tranco list and one Chromium/Linux vantage point.
- Visits were passive and short. Interaction-triggered behavior may not have been observed.
- Rules have not yet been evaluated against a completed, human-labelled validation set. A 100-row review worksheet and supporting evidence file are available at `data/labelled/review_baseline_100_run_20261028.csv` and `data/labelled/review_baseline_100_run_20261028_evidence.json`; labels are still blank and require human review.
- The matching blocklist crawl and paired analysis are documented in `reports/blocklist_100_comparison_20261029.md`. That comparison includes only domains successful in both conditions (paired N=50).

## Reproducibility

- SQLite source: `data/raw/fpstudy.sqlite`
- Pinned list: `data/tranco/tranco_GQ3LK.csv`
- Manifest: `data/tranco/manifest.json`
- Prevalence table: `reports/tables/table_prevalence_run_baseline_20261028_081315_49e14b.csv`
- Failure taxonomy figure: `reports/figures/figure_failure_taxonomy_run_baseline_20261028_081315_49e14b.png` (and PDF)
- Prevalence figure: `reports/figures/figure_prevalence_run_baseline_20261028_081315_49e14b.png` (and PDF)
- To classify from stored events: `fpstudy classify --run-id run_baseline_20261028_081315_49e14b`

