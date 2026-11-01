# Blocklist comparison: first 100 Tranco domains

**Baseline run:** `run_baseline_20261028_081315_49e14b`  
**Blocklist run:** `run_blocklist_20261029_074923_7c8f7b`  
**Sample:** Tranco `GQ3LK`, ranks 1–100  
**Blocklist canary:** passed

## What was measured

Both conditions attempted the same 100 domains. The baseline had 52 successful visits; the blocklist run also had 52. The paired analysis includes only the 50 domains that were successful in both conditions. The two domains that succeeded in only one condition are excluded from the paired comparison.

| Measure | Baseline | Blocklist |
|---|---:|---:|
| Domains attempted | 100 | 100 |
| Successful visits | 52 | 52 |
| Successful in both (paired N) | 50 | 50 |
| Any configured signal among paired visits | 18/50 (36.0%) | 15/50 (30.0%) |

The observed absolute reduction was 6 percentage points (95% CI: -0.6 to 12.6 percentage points). The Holm-adjusted McNemar p-value was 1.000. This is **not statistically significant** and does not show that the blocklist reduced fingerprinting. It is a small sample with only three discordant pairs, all changing from detected in baseline to not detected under blocklist (dzen.ru, mail.ru, roblox.com).

## Did the blocklist actually block requests?

Yes. Its canary passed, and the new route-level counter recorded 797 blocked requests across 48 visits, with a maximum of 115 in one visit. This confirms the configured EasyPrivacy blocklist was active and cancelling matching requests. It does not by itself show that fingerprinting was prevented: many blocked requests may be unrelated to the four measured signals. The earlier 10-site run's all-zero blocked counter was collected before this counter fix and should not be used to assess blocking.

## Manual review of changed detections

I inspected the stored classification evidence for the three paired sites whose result changed.

- **dzen.ru and mail.ru:** both baseline flags are first-party inline-script detections. The WebGL rule saw access to `WEBGL_debug_renderer_info`; the audio rule saw an offline audio context, oscillator, compressor, analyser, rendering, and sample reads. These are the kinds of browser-feature combinations the configured rules are intended to catch. Under blocklist, the pages still loaded and emitted events, but those combinations were no longer flagged. This is evidence of a changed observed behavior, not proof of tracking intent or proof that the blocklist directly removed those calls.
- **roblox.com:** baseline flagged Canvas readback plus WebGL debug-renderer access from an inline script in an `about:srcdoc` frame. This is a candidate for closer frame-attribution review; the stored evidence alone does not establish whether it was an independent third-party tracker or normal embedded page code. The blocklist visit still loaded successfully.

This is a targeted review of the changed pairs, not a completed ground-truth validation set. The 100-row annotation worksheet remains available at `data/labelled/review_baseline_100_run_20261028.csv`; its labels should be filled by a human reviewer before reporting classifier precision or recall.

## Interpretation and next step

The pipeline ran both conditions successfully and the blocklist actively blocked requests. The measured signal rate was lower under blocklist in this sample, but the paired evidence is too sparse to support an effectiveness claim. The next batch should use the next 100 domains from the same pinned Tranco list and run both baseline and blocklist on exactly that batch. Results from the new batch should be reported alongside, and not silently mixed with, the original ranks 1–100 comparison.

Robots-disallowed pages remain recorded as skipped and are not treated as negatives. DNS errors, HTTP errors, timeouts, and bot challenges are also missing observations.

## Reproduction

```bash
.venv/bin/fpstudy classify --run-id run_blocklist_20261029_074923_7c8f7b
.venv/bin/fpstudy analyse \
  --baseline run_baseline_20261028_081315_49e14b \
  --compare run_blocklist_20261029_074923_7c8f7b
```

Figure: `reports/figures/figure_comparison_run_blocklist_20261029_074923_7c8f7b.pdf` (also PNG).
