> **Update:** This report covers only the first 200 ranks. The full 500-domain pooled results and final interpretation are in [the complete report](complete_500_domain_report_20261031.md).

# uBlock Origin Lite comparison on 200 ranked domains

**Run date:** 2026-10-30  
**Condition:** genuine uBlock Origin Lite (uBOL), release `2026.1026.1812`, Chromium Manifest V3  
**Extension asset SHA-256:** `d3788eac9f0a44c67f3745a43c3fd446ef33d56b1121f469b19e0fa0a836c2b5`  
**Extension run:** `run_extension_ubol_20261030_053103_a3efc8`  
**Baseline runs:** ranks 1–100 `run_baseline_20261028_081315_49e14b`; ranks 101–200 `run_baseline_20261029_081318_cbf723`

## Question

When the same ranked websites are visited with uBOL enabled, does this study’s detector record fewer configured fingerprinting-related browser API patterns than it records in the corresponding baseline visits?

This comparison measures **recorded API patterns**, not whether a browser became anonymous or unrecognizable. It does not establish that a site used the information to track a person.

## Method and extension check

The crawler visited the first 200 domains in Tranco list `GQ3LK` with the project’s extension condition. The configured official Chromium package was pinned by version and SHA-256; the unpacked extension was not a mock. The pre-crawl canary passed: Chromium reported the extension service worker running, and a request for Google Analytics’ `analytics.js` was redirected to a `chrome-extension://` resource. This confirms that the extension was active and that this particular test request was handled by it.

The run contains 200 visit records: 104 `ok`, 52 DNS errors, 10 HTTP 4xx, 9 timeouts, 6 other errors, 17 robots exclusions, and 2 suspected bot challenges. Classification found at least one configured signal on 22 of the 104 successful visits (21.2%). Only `ok` visits were eligible for prevalence. Two separate paired comparisons were run, one per 100-domain batch, so results from the batches are not pooled.

## Results

| Ranked batch | Same domains successful in both conditions | Baseline with ≥1 signal | With uBOL with ≥1 signal | Estimated reduction (95% CI) | Holm adjusted p |
|---|---:|---:|---:|---:|---:|
| 1–100 | 50 | 18/50 (36.0%) | 13/50 (26.0%) | 10.0 percentage points (0.0 to 20.0) | 0.6250 |
| 101–200 | 48 | 10/48 (20.8%) | 6/48 (12.5%) | 8.3 percentage points (-4.4 to 21.0) | 1.0000 |

The first batch has a numerical decrease, but its adjusted p-value is not statistically significant and the interval reaches no change. The second batch also has a numerical decrease, with an interval that includes both no change and a possible increase. These results do **not** establish that uBOL reduced fingerprinting-related API use. They also do not show that uBOL was inactive: the canary confirmed that it handled a known tracker request.

The crawler’s `blocked_requests_count` is zero in this extension run. That counter counts browser-level failed requests, and does not count uBOL’s redirect of a tracker script to an extension resource. Therefore zero in this field must not be reported as “uBOL blocked nothing.” The canary provides the evidence of extension activity; this study did not collect a complete uBOL-specific blocked-request total.

## What this means in plain English

Among websites that loaded in both versions of the experiment, fewer showed the browser-feature activity we measure when uBOL was on. The study is too uncertain to tell whether that difference reflects a real, repeatable reduction. The extension’s tracker test worked, but blocking a tracker script and preventing fingerprinting are different outcomes.

## Limits and remaining work

- The detector identifies configured API behaviours. It cannot infer a site’s intent or prove that the information was used to identify a visitor.
- The 98 paired sites are the analysis sample; the other attempted domains are not negative observations.
- There are only two separate batches and one crawl per condition and domain. Time, network changes, dynamic pages, and robots exclusions can affect results.
- The user reports reviewing the 100 examples and considers the workbook 100% accurate. In the saved CSV, however, all 100 `ground_truth_label` values remain blank. The review is acknowledged, but the row-level decisions are not yet available to calculate reproducible precision, recall, F1, or a confusion matrix. Do not substitute detector predictions for the reviewed labels.
- The configured API-event outcome is not a browser-uniqueness test. The project does not yet show whether two visits become harder to link or whether a fingerprint’s identifying power changed.
- The extension’s request-block total needs a measurement method appropriate to uBOL’s declarative redirects if that count is to be reported.

## Current conclusion

The software completed a real uBOL crawl and the canary verified extension activity. In the paired data, the detector’s signal prevalence was lower under uBOL in both batches, but uncertainty is large and neither comparison establishes a reliable reduction. The user's review is reported as complete; the saved row-level labels still need to be entered before detector accuracy can be calculated. The research also needs supervisor approval of its sample scope and final interpretation.
