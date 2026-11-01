# Complete 500-domain study report

**Report date:** 31 October 2026  
**Sample:** Tranco list `GQ3LK`, ranks 1–500  
**Conditions:** stock Chromium baseline, EasyPrivacy blocklist, genuine uBlock Origin Lite (uBOL)  
**Main outcome:** whether the detector recorded at least one configured fingerprinting-related browser API pattern during a successful site visit.

## Executive summary

The project visited the same ranked sample with a normal browser, with EasyPrivacy filtering, and with uBlock Origin Lite. It recorded browser-feature activity such as Canvas drawing and readback, WebGL queries, offline audio processing, and font checks. A rules-based detector marked patterns that match the study's configured definitions.

Across the sites that loaded in both conditions, the detector marked fewer sites with at least one pattern when either protection was enabled:

| Comparison | Same sites loaded in both | Baseline with a signal | With protection | Estimated reduction | Adjusted p-value |
|---|---:|---:|---:|---:|---:|
| EasyPrivacy blocklist | 237 | 74/237 (31.2%) | 61/237 (25.7%) | 5.5 percentage points (95% CI 2.1 to 8.8) | 0.0117 |
| uBlock Origin Lite | 240 | 77/240 (32.1%) | 54/240 (22.5%) | 9.6 percentage points (95% CI 4.9 to 14.3) | 0.0010 |

These results support a reduction in the **API patterns measured by this detector** for this sample and these browser settings. They do not show that a person could no longer be recognized from a browser fingerprint, or that a site stopped tracking a person. The project did not test cross-visit identification, fingerprint uniqueness, or actual tracking outcomes.

![Paired successful-site signal prevalence for the two protections](figures/figure_pooled_signal_reduction_500_20261031.png)

All 500 Tranco domains have records under the two protections. The baseline has 499 records because its final 300-domain run ended without saving a visit for rank 423, `firetvcaptiveportal.com`; that domain timed out under both protections. It could not enter either paired analysis. The crawl logs, exclusions, and failures are retained in the database and the domain appendix.

## Plain-language explanation

A website's code can ask a browser questions about its graphics, sound, installed fonts, and other features. A combination of answers can help distinguish one browser from another. This is called browser fingerprinting.

This project watches for selected browser-feature calls while pages load. It then checks whether those calls match specific rules. The same ranked domains are opened in three browser setups: normal Chromium, Chromium with EasyPrivacy request filtering, and Chromium with uBlock Origin Lite.

For a fair comparison, a domain is counted only when it loaded successfully in both versions being compared. A site that fails, times out, triggers a bot challenge, or is excluded by `robots.txt` is not counted as a site with “no fingerprinting.” Such visits are recorded as unavailable for that paired comparison.

**Simple conclusion:** among the matched pages, both protections were associated with fewer detected browser-feature patterns. The result is meaningful for this detector. It is not yet evidence that the browser became anonymous or impossible to fingerprint.

## Research question and scope

The operational question this study answers is:

> On the same popular domains, does the detector record fewer configured fingerprinting-related browser API patterns with a request-blocking protection enabled than with the baseline browser?

The study uses the top 500 entries from the pinned Tranco list `GQ3LK`. The sample is a list of **domains**, which includes service and infrastructure domains as well as ordinary websites. It is not 500 people, 500 browser identities, or 500 successful page loads.

The measured outcome is a rule match in recorded browser API activity. The study does not inspect a site's intent and does not observe whether a site used those values to identify a browser or person.

## How the pipeline works

1. **Choose the sample.** The project reads ranks 1–500 from the pinned Tranco file and keeps each rank and domain for reproducibility.
2. **Check robots rules.** The crawler checks each domain's `robots.txt`. Disallowed sites are saved as `skipped_robots`; they are not opened and are not treated as negative detections.
3. **Open the page.** Playwright launches headless Chromium. The crawler waits for the page's `load` event, keeps it open for the configured dwell time, and makes a small scroll interaction.
4. **Record browser activity.** Instrumentation hooks observe selected API calls and store method/property names, compact argument and return summaries, script URLs, stack excerpts, frame URLs, top-level URLs, and whether a script appears third-party. The visits table also stores status, HTTP result, load and dwell times, console errors, request counts, failed requests, blocked requests, event counts, and truncation indicators.
5. **Classify patterns.** Rules group observed calls into Canvas, WebGL, Audio, and Fonts. A domain is “any signal” if at least one of those vectors is flagged in at least one script.
6. **Compare matched domains.** For each protection, the analysis keeps only domains with `status=ok` in both the baseline and protected run. It compares each domain with itself, rather than comparing unrelated site totals.

The full stored browser events are in `data/raw/fpstudy.sqlite`. Two CSV appendices make the results easier to inspect: the 500-row domain summary and the row-level classification evidence.

## Technical setup

| Setting | Value |
|---|---|
| Ranked source | Tranco list `GQ3LK`, ranks 1–500 |
| Browser | Playwright Chromium, recorded version `156.0.8078.4` |
| Operating system | Linux Fedora 44 environment, kernel `7.2.11-200.fc44.x86_64` as recorded by the run |
| Viewport | 1920 × 1080 |
| Locale / timezone | `en-US` / `Europe/London` |
| Dwell / navigation timeout | 12 seconds / 30 seconds |
| Concurrency / retry policy | 4 visits concurrently / up to 2 retries after transient failures |
| Event cap | 5,000 events per visit |
| Baseline | Stock headless Chromium |
| Blocklist | EasyPrivacy through the project's adblock engine |
| Extension | Official uBlock Origin Lite `2026.1026.1812`, Manifest V3; package SHA-256 `d3788eac9f0a44c67f3745a43c3fd446ef33d56b1121f469b19e0fa0a836c2b5` |

The configured user-agent string identifies itself as Chrome 124, while the installed browser reported version 156. This mismatch may affect how some sites respond. It is recorded as a reproducibility limitation and should be corrected before a future confirmatory crawl.

### Detector rules

- **Canvas:** drawing and reading back sufficiently large or complex image/text output, subject to exclusions for ordinary save/restore and event-listener behavior.
- **WebGL:** querying unmasked vendor/renderer or many parameters, with extra evidence such as extension/precision probing or pixel readback.
- **Audio:** an offline audio context combined with oscillator, compressor, and output readback behavior.
- **Fonts:** checking many distinct fonts (threshold: 30) through text measurement, element dimensions, or font-face checks.

These thresholds make the analysis repeatable. They are still detector rules. They do not prove a site's purpose, and the detector has not yet had its precision and recall calculated from saved ground-truth labels.

### Protection checks

All final runs passed their condition canaries. The blocklist canary confirmed that a known test request matched the filtering engine and was blocked. The uBOL canary confirmed that the extension worker loaded and a known Google Analytics script was redirected to an extension resource. This establishes that the protections were active during the checks.

The browser's `blocked_requests_count` is useful for EasyPrivacy because the crawler observes browser requests that fail with a client-side block. EasyPrivacy recorded 2,934 such requests across 213 visits in these batches. This count includes blocked resources generally; it does not identify which blocked request would have produced a fingerprinting signal. uBOL uses declarative redirects, so the same counter stayed at zero and is not a valid uBOL block total.

## Crawl accounting

All three conditions ran against the same 500 ranked targets. Baseline produced 499 stored visits; blocklist and uBOL produced 500 each. Failures and robots exclusions remain in the denominator for crawl accounting, but not in the successful-page prevalence denominator.

| Final condition records | Baseline | EasyPrivacy | uBOL |
|---|---:|---:|---:|
| Visit records | 499 | 500 | 500 |
| Successful page loads (`ok`) | 242 | 243 | 255 |
| DNS errors | 127 | 127 | 125 |
| `robots.txt` exclusions | 39 | 40 | 40 |
| HTTP 4xx | 28 | 28 | 22 |
| Suspected bot challenges | 9 | 8 | 8 |
| Timeouts | 39 | 36 | 34 |
| Other errors | 12 | 15 | 13 |
| TLS errors | 3 | 3 | 3 |

Among successful visits, the raw number of sites with any detected signal was 77/242 (31.8%) for baseline, 63/243 (25.9%) for EasyPrivacy, and 60/255 (23.5%) for uBOL. These raw percentages have different site denominators. The paired tables below are the proper protection comparisons.

The baseline gap is rank 423, `firetvcaptiveportal.com`. It timed out under EasyPrivacy and uBOL as well. A targeted baseline retry (`run_baseline_20261031_155626_ed8166`) was attempted and stopped after repeated timeouts; it saved no visit and returned a Playwright driver-connection error. Earlier partial baseline and extension attempts were excluded; only the final runs listed in this report are used for the results.

The instrumentation stored 317,654 browser API events across the final runs (136,794 baseline; 95,967 EasyPrivacy; 84,893 uBOL). Fifteen visit records reached the event cap and are marked as truncated (five per condition). Event counts are activity volume, not counts of unique fingerprinting actions or tracking events.

## Paired comparison results

### Any configured signal, by ranked batch

| Ranks | EasyPrivacy paired N | Baseline positive | EasyPrivacy positive | uBOL paired N | Baseline positive | uBOL positive |
|---|---:|---:|---:|---:|---:|---:|
| 1–100 | 50 | 18/50 (36.0%) | 15/50 (30.0%) | 50 | 18/50 (36.0%) | 13/50 (26.0%) |
| 101–200 | 48 | 10/48 (20.8%) | 7/48 (14.6%) | 48 | 10/48 (20.8%) | 6/48 (12.5%) |
| 201–500 | 139 | 46/139 (33.1%) | 39/139 (28.1%) | 142 | 49/142 (34.5%) | 35/142 (24.6%) |
| **Pooled matched sites** | **237** | **74/237 (31.2%)** | **61/237 (25.7%)** | **240** | **77/240 (32.1%)** | **54/240 (22.5%)** |

The rank 201–500 comparison for EasyPrivacy has 139 successful pairs because only 139 domains loaded in both runs. uBOL has 142 successful pairs in that batch. The paired samples differ because the two protections did not have identical visit outcomes.

### Pooled outcomes by vector

The estimated reduction is baseline prevalence minus protected prevalence. Confidence limits use the paired Wald approximation implemented by the project. Holm-adjusted p-values correct for the five listed outcomes within each protection comparison.

| Protection | Outcome | Baseline | Protected | Reduction (95% CI) | Holm p |
|---|---|---:|---:|---:|---:|
| EasyPrivacy | Any signal | 31.2% | 25.7% | 5.5 pp (2.1 to 8.8) | 0.0117 |
| EasyPrivacy | Canvas | 10.5% | 9.3% | 1.3 pp (-0.9 to 3.4) | 0.4531 |
| EasyPrivacy | WebGL | 30.8% | 25.3% | 5.5 pp (2.1 to 8.8) | 0.0117 |
| EasyPrivacy | Audio | 11.0% | 7.2% | 3.8 pp (1.4 to 6.2) | 0.0117 |
| EasyPrivacy | Fonts | 9.3% | 7.2% | 2.1 pp (0.3 to 3.9) | 0.1250 |
| uBOL | Any signal | 32.1% | 22.5% | 9.6 pp (4.9 to 14.3) | 0.0010 |
| uBOL | Canvas | 10.8% | 9.6% | 1.3 pp (-1.5 to 4.0) | 0.5488 |
| uBOL | WebGL | 31.2% | 21.7% | 9.6 pp (4.9 to 14.3) | 0.0010 |
| uBOL | Audio | 11.3% | 7.1% | 4.2 pp (1.4 to 6.9) | 0.0190 |
| uBOL | Fonts | 9.6% | 7.5% | 2.1 pp (-0.4 to 4.5) | 0.3594 |

For both protections, the pooled `any signal` result is statistically significant after the stated Holm correction. WebGL contributes most of the difference; the pooled Canvas and Fonts comparisons do not show a statistically reliable change. Each batch was collected at a different time, so the pooled value is a combined summary of the three paired batches. The batch-level counts are shown above to make that timing visible.

The McNemar tests use exact binomial probabilities when the number of discordant pairs is below 25 and a continuity-corrected chi-square test otherwise. The paired table for `any signal` is:

| Protection | Both positive | Baseline only positive | Protection only positive | Both negative |
|---|---:|---:|---:|---:|
| EasyPrivacy | 59 | 15 | 2 | 161 |
| uBOL | 48 | 29 | 6 | 157 |

A positive site is counted once for `any`, even if it has more than one flagged vector or script.

## What the request-blocking numbers mean

EasyPrivacy recorded 2,934 blocked requests across the three paired batches. This confirms that the request filter operated on real visits. Some blocked resources may be analytics or advertising requests, and some may have no relation to the four detector vectors. The count therefore cannot be described as “2,934 fingerprinting attempts prevented.”

The uBOL canary proves the extension handled a known tracker script. The project's generic blocked-request counter does not measure uBOL's internal declarative redirects, so it cannot be used to compare uBOL's total blocked requests with EasyPrivacy's total.

## What the project has established

**Established:** for the 237 sites that loaded in both baseline and EasyPrivacy and the 240 sites that loaded in both baseline and uBOL, the detector recorded fewer configured signals in the protected condition. The difference for the combined `any signal` outcome remains statistically significant after the project's five-outcome Holm correction.

**Not established:** that protections made browser fingerprints less unique, made visitors harder to link across separate visits, stopped actual tracking, or protected every site. Those questions require measurements this project does not collect.

The user's earlier statement that the 100-example workbook was reviewed as fully accurate is acknowledged. The saved project CSV still has blank `ground_truth_label` values, so the review cannot yet be reproduced as precision, recall, F1, or a confusion matrix. This is a detector-validation gap, separate from the paired protection result.

## Limitations and next steps

1. **Validate the detector.** Save the already-reviewed 0/1 decisions in `data/labelled/review_baseline_100_run_20261028.csv`, then run `fpstudy validate`. Do not copy the detector's prediction into the ground-truth column.
2. **Align browser and user-agent versions.** The recorded Chromium is version 156 while the configured user-agent says Chrome 124. Fix this before a confirmatory run.
3. **Repeat or interleave conditions.** The three rank batches were collected on different dates and conditions were not interleaved. A randomized or interleaved repeat would help separate protection effects from site changes, network changes, and crawl timing.
4. **If the intended claim is about fingerprintability, test linkability.** Run repeated visits in controlled sessions and measure whether the observed fingerprints can distinguish or link browsers. API call counts alone do not answer this.
5. **Finish the research write-up.** Verify literature sources, explain the sample failures and robots exclusions, and get supervisor approval for the final scope and conclusions.

More crawling of the same design is not the most useful immediate step. Detector validation and a direct linkability outcome would improve the research more.

## Reproduction and data files

The run IDs used in this report are:

| Ranks | Baseline | EasyPrivacy | uBOL |
|---|---|---|---|
| 1–100 | `run_baseline_20261028_081315_49e14b` | `run_blocklist_20261029_074923_7c8f7b` | `run_extension_ubol_20261030_053103_a3efc8` |
| 101–200 | `run_baseline_20261029_081318_cbf723` | `run_blocklist_20261029_083049_a2a1f4` | `run_extension_ubol_20261030_053103_a3efc8` |
| 201–500 | `run_baseline_20261030_065705_5a1a18` | `run_blocklist_20261030_075607_8335da` | `run_extension_ubol_20261031_142743_d59737` |

The baseline and blocklist 201–500 comparisons can be reproduced with:

```bash
.venv/bin/fpstudy analyse \
  --baseline run_baseline_20261030_065705_5a1a18 \
  --compare run_blocklist_20261030_075607_8335da

.venv/bin/fpstudy analyse \
  --baseline run_baseline_20261030_065705_5a1a18 \
  --compare run_extension_ubol_20261031_142743_d59737
```

The full 500-domain and evidence appendices are:

- `reports/tables/domain_level_results_tranco_GQ3LK_ranks_1_500_20261031.csv` — one row per rank, with each condition's status, requests, event counts, classification flags, and matched-success indicators.
- `reports/tables/classification_evidence_tranco_GQ3LK_ranks_1_500_20261031.csv` — all 6,028 classification rows, including script, vector, confidence, evidence, and first/third-party status.
- `reports/tables/paired_comparisons_tranco_GQ3LK_ranks_1_500_20261031.csv` — every vector result by rank batch and pooled result, including paired contingency counts, confidence intervals, raw and adjusted p-values.
- `data/raw/fpstudy.sqlite` — underlying visit, script, classification, and raw event records.
