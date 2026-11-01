# Preliminary 10-site fingerprinting study

**Status:** pilot results from the existing paired crawl runs; descriptive, not a final estimate of prevalence or countermeasure effectiveness.

## Research question

In the first ten domains of the pinned Tranco list `GQ3LK`, what fingerprinting signals did the pipeline detect during a 12-second, passive Chromium visit, and did the EasyPrivacy blocklist condition change those detections compared with baseline?

## Sample and procedure

The two runs used the first ten entries in `data/tranco/tranco_GQ3LK.csv` and the same pinned sample identifier (`GQ3LK`). `data/tranco/sample_test.csv` was not the input for these runs. The ten domains were:

| Tranco rank | Domain | Baseline status | Blocklist status |
|---:|---|---|---|
| 1 | google.com | ok | ok |
| 2 | cloudflare.com | ok | ok |
| 3 | amazonaws.com | ok | ok |
| 4 | facebook.com | skipped_robots | skipped_robots |
| 5 | ezviz7.com | dns_error | dns_error |
| 6 | gstatic.com | skipped_robots | skipped_robots |
| 7 | fbcdn.net | ok | ok |
| 8 | googleapis.com | http_4xx (404) | http_4xx (404) |
| 9 | akamai.net | dns_error | dns_error |
| 10 | microsoft.com | ok | ok |

The experiment ran Chromium 156 on Fedora Linux from one network vantage point. Each run records a successful-visit window of roughly 12 seconds. The blocklist run's canary passed, recording that the filter engine matched and blocked its configured canary URL. These details support the claim that the condition was configured, but do not by themselves establish how many requests were blocked on the study sites.

## Visit outcomes

Each condition completed 10 visit records: **5 `ok`**, **2 `skipped_robots`**, **2 `dns_error`**, and **1 `http_4xx`**. The two runs had the same visit status for each domain. Only the five domains with `ok` in both conditions entered the prevalence denominators and paired comparison. Skips and failures are missing observations, not fingerprinting-negative observations.

## Detected fingerprinting signals

| Vector | Baseline | EasyPrivacy blocklist |
|---|---:|---:|
| Canvas | 0/5 (0%; 95% Wilson CI 0–43.45%) | 0/5 (0%; 95% Wilson CI 0–43.45%) |
| WebGL | 4/5 (80%; 95% Wilson CI 37.55–96.38%) | 4/5 (80%; 95% Wilson CI 37.55–96.38%) |
| Audio | 0/5 (0%; 95% Wilson CI 0–43.45%) | 0/5 (0%; 95% Wilson CI 0–43.45%) |
| Fonts | 1/5 (20%; 95% Wilson CI 3.62–62.45%) | 1/5 (20%; 95% Wilson CI 3.62–62.45%) |
| Any detected vector | 4/5 (80%; 95% Wilson CI 37.55–96.38%) | 4/5 (80%; 95% Wilson CI 37.55–96.38%) |

In both runs, WebGL was flagged for `amazonaws.com`, `cloudflare.com`, `fbcdn.net`, and `microsoft.com`; fonts were flagged for `fbcdn.net`. The overall result is a count of sites that met the project's configured rules in this browser session, not proof of tracking intent or a claim about all scripts/sites.

## Paired comparison

For all five successfully paired domains, the binary site classifications were unchanged between baseline and blocklist. The analysis reports an absolute risk reduction of 0 percentage points for every vector, no discordant pairs, and exact McNemar p = 1.0000 (Holm-adjusted p = 1.0000). With no discordant pairs, an ARR confidence interval is unavailable; a 0–0 interval would falsely imply certainty.

This is an **inconclusive pilot comparison**. With only five paired sites and no discordant outcomes, there is little information to estimate the blocklist's effect. The result does not establish that blocklists have no effect. A site can retain a fingerprinting signal if its relevant script was not on the list, if the signal came from a first-party script, or if instrumentation/classification did not capture the affected behavior.

The visit records report zero `blocked_requests_count` in both runs, although the blocklist canary passed and the blocklist visits have higher `failed_requests_count` for some sites. The blocked-request counter therefore needs verification before using it to quantify request-level blocking. Do not interpret its current zero values as evidence that no requests were blocked.

## Interpretation and limitations

1. **Small pilot sample.** Five eligible sites cannot support a stable prevalence estimate or strong countermeasure claim. The Wilson intervals are wide.
2. **Selection and eligibility.** The sample is the first ten domains of a pinned list, but only five loaded successfully. Robots exclusions and failures reduce the analyzable set and may not be random.
3. **Short, passive visit.** The crawler waited about 12 seconds and did not interact with pages. Behaviors triggered by consent, clicks, scrolling, logins, or longer sessions may be missed.
4. **One browser and vantage point.** Results describe Chromium 156 on one Linux host/network and may differ by browser, region, time, or user state.
5. **Heuristic classifications.** Rules flag observed API patterns. They can produce false positives and false negatives; the current dataset has no completed human-labelled validation set.
6. **Request-blocking telemetry.** The request-level blocked counter appears inconsistent with the canary and failure counts and needs an instrumentation fix or independent check before a request-blocking effectiveness claim.

## Conclusion

In the five sites successfully visited in both conditions, the pipeline flagged at least one configured fingerprinting vector on four sites, primarily through WebGL signals. It detected no change in site-level classifications between baseline and the EasyPrivacy condition. Because five sites were excluded and the paired sample is only five, these results should be presented as a feasibility pilot, not as a conclusion about fingerprinting prevalence across popular websites or blocklist effectiveness.

## Reproducibility references

- Baseline run: `run_baseline_20261028_063108_c7fe7a`
- Blocklist run: `run_blocklist_20261028_064615_97799c`
- Source database: `data/raw/fpstudy.sqlite`
- Sample list and manifest: `data/tranco/tranco_GQ3LK.csv`, `data/tranco/manifest.json`
- Generated prevalence tables: `reports/tables/table_prevalence_run_baseline_20261028_063108_c7fe7a.csv`, `reports/tables/table_prevalence_run_blocklist_20261028_064615_97799c.csv`
- Paired analysis: `fpstudy analyse --baseline run_baseline_20261028_063108_c7fe7a --compare run_blocklist_20261028_064615_97799c`
