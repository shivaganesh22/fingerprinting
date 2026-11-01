# Research completion assessment — 500-domain analysis

**Assessment date:** 31 October 2026  
**Primary results report:** [Complete 500-domain study report](complete_500_domain_report_20261031.md)  
**Overall status:** The 500-domain countermeasure comparison is complete for the project's measured API-pattern outcome. Detector validation and any claim about actual fingerprintability or tracking remain unfinished.

## What the project tested

The pipeline visited the top 500 domains in pinned Tranco list `GQ3LK` under three conditions: stock Chromium, EasyPrivacy request filtering, and genuine uBlock Origin Lite. It recorded selected browser-feature API calls, classified Canvas, WebGL, Audio, and Fonts patterns, and compared only the same domains that loaded successfully under both conditions.

The final runs produced 499 baseline visit records, 500 EasyPrivacy records, and 500 uBOL records. The baseline record for rank 423 (`firetvcaptiveportal.com`) is missing; that domain timed out in both protected conditions. It is therefore excluded from paired comparisons. The failure and a targeted retry that saved no visit are documented in the detailed report and raw database.

## Main result

Among 237 sites that loaded in both baseline and EasyPrivacy conditions, the detector found at least one configured signal on 74 baseline visits (31.2%) and 61 protected visits (25.7%). The estimated reduction was 5.5 percentage points (95% CI 2.1 to 8.8; Holm-adjusted p=0.0117).

Among 240 sites that loaded in both baseline and uBOL conditions, the detector found at least one configured signal on 77 baseline visits (32.1%) and 54 protected visits (22.5%). The estimated reduction was 9.6 percentage points (95% CI 4.9 to 14.3; Holm-adjusted p=0.0010).

These results support a reduction in the **browser API patterns this detector records**, for this sample, browser, and setup. They do not prove that a browser became less unique, that separate visits became harder to link, or that a person was no longer tracked.

The protections passed their canaries. EasyPrivacy blocked 2,934 requests as counted by the crawler. The uBOL canary verified that the extension handled a known analytics script; the project's ordinary blocked-request counter does not give a valid uBOL total.

## Remaining research work

1. The reviewed 100-example workbook is reported by the user as accurate. The checked-in CSV still has blank `ground_truth_label` cells. Save the reviewed labels there, then run `fpstudy validate` to calculate reproducible precision, recall, F1, and a confusion matrix.
2. The installed Chromium reported version 156 while the configured user-agent identifies as Chrome 124. Correct this mismatch in a future confirmatory run.
3. The three ranked batches were crawled on different dates, without interleaving conditions. A randomized or interleaved repeat would strengthen causal attribution.
4. If the research claim needs to say a protection makes people harder to fingerprint, add a repeated-visit linkability or fingerprint uniqueness measurement. The current pipeline measures API behavior only.
5. Finish source-verified literature review, dissertation discussion, and supervisor review of scope, methods, and ethics requirements.

A larger crawl of the same design is not the immediate next step. The most useful next work is to enter the already-reviewed labels, verify detector performance, and decide whether the final research question is about API behavior or cross-visit linkability.

## Final answer in simple English

The project has real results. In the websites that could be compared fairly, both protections were linked to fewer browser-feature patterns being recorded by the project. That supports “the protections reduced the signals this tool measured.” It does not yet support “they stopped fingerprinting” or “they stopped tracking,” because the study did not test whether a browser could still be recognized or linked across visits.
