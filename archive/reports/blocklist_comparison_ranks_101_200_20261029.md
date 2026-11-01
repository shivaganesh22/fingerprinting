# Paired blocklist comparison: Tranco ranks 101–200

**Sample:** Tranco `GQ3LK`, ranks 101–200, pinned in `data/tranco/tranco_GQ3LK_ranks_101_200.csv`  
**Configuration:** `config/next_100.yaml`  
**Baseline run:** `run_baseline_20261029_081318_cbf723`  
**Blocklist run:** `run_blocklist_20261029_083049_a2a1f4`  
**Canaries:** both passed

## Crawl outcomes

Both conditions attempted the same 100 domains. Baseline had 48 successful visits, and blocklist had 49. Forty-eight domains succeeded in both and are included in the paired comparison. Skips and errors were recorded but are not treated as negative detections.

| Measure | Baseline | Blocklist |
|---|---:|---:|
| Attempted | 100 | 100 |
| Successful | 48 | 49 |
| Successful in both (paired N) | 48 | 48 |
| Any configured signal on paired sites | 10/48 (20.8%) | 7/48 (14.6%) |

The estimated absolute reduction was 6.2 percentage points (95% CI: -4.4 to 16.9 percentage points). The Holm-adjusted McNemar p-value was 1.000. The interval includes zero and the adjusted test is not statistically significant; this sample does not establish that the blocklist reduced fingerprinting.

## Request blocking

The blocklist canary passed. Its route-level counter recorded 575 blocked requests across 45 visits, with a maximum of 94 in one visit. The baseline counter was zero as expected. This confirms that the filter rules were active, but blocked request counts are not a measure of prevented fingerprinting: requests can be blocked for reasons beyond the four measured browser-feature signals.

## Manual review of changed outcomes

There were seven discordant paired domains: five baseline-positive/blocklist-negative (`kaspersky.com`, `mts.ru`, `samsung.com`, `windows.com`, `yandex.ru`) and two baseline-negative/blocklist-positive (`vk.com`, `vk.ru`). I inspected all seven stored classification evidence records.

- The baseline-positive cases mostly involved first-party inline scripts. Evidence included WebGL renderer/parameter queries, offline audio rendering, Canvas readback, or probing more than 30 fonts. These calls match the configured technical rules, but a rule match alone does not show that the site used the result to recognize or track users.
- `vk.com` and `vk.ru` resolved to the same `vk.ru` page and produced nearly identical Canvas and WebGL detections under blocklist. They should not be interpreted as independent examples; Tranco ranks can include related or redirecting domains.
- The changed outcomes do not consistently imply that the filter directly blocked the code performing the browser API calls. The pages still loaded, and some continued making many requests. Site content, page state, and network timing may also change between visits.

This review is a manual inspection of detector evidence, not a completed ground-truth labelling exercise. Do not use it to claim classifier precision or recall. The annotation worksheet for ranks 1–100 remains blank for a researcher to label.

## Interpretation

The raw detected-signal rate was lower under blocklist by about six percentage points in both the ranks 1–100 batch (50 pairs) and this ranks 101–200 batch (48 pairs). Neither paired comparison was statistically significant. These are separate batches collected at different times and should be reported separately unless an explicitly batch-stratified pooled analysis is conducted. The current evidence supports only: **the blocklist was active and blocked requests; the study has not yet shown a reliable change in the measured fingerprinting signals.**

## Reproduction

```bash
.venv/bin/fpstudy classify --run-id run_baseline_20261029_081318_cbf723
.venv/bin/fpstudy classify --run-id run_blocklist_20261029_083049_a2a1f4
.venv/bin/fpstudy analyse \
  --baseline run_baseline_20261029_081318_cbf723 \
  --compare run_blocklist_20261029_083049_a2a1f4
```

Figure: `reports/figures/figure_comparison_run_blocklist_20261029_083049_a2a1f4.pdf` (and PNG).
