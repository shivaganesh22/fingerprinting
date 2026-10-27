# Measurement and Detection Methodology (`docs/methodology.md`)

This document formally specifies the detection rules, literature grounding, parameter thresholds, statistical tests, and denominator accounting used across the `fpstudy` pipeline.

---

## 1. Detection Heuristics & Grounding

Fingerprinting detection operates on an **event-stream model**: client-side API calls are grouped by `(visit_id, script_url)` and evaluated against vector-specific deterministic criteria.

### 1.1 Canvas Fingerprinting Heuristic
- **Theoretical Basis:** Mowery & Shacham (2012) showed that subtle differences in font rasterization, 2D graphics libraries, anti-aliasing algorithms, and GPU drivers cause distinct pixel outputs when rendering text to an HTML5 `<canvas>`.
- **Reference Specification:** Englehardt & Narayanan, *"Online Tracking: A 1-million-site Measurement and Analysis"*, ACM CCS 2016 (OpenWPM).
- **Rule Criteria:** A script is flagged as conducting canvas fingerprinting if and only if **all** of the following conditions hold within a single visit:
  1. **Minimum Dimensions:** The canvas element has both `width >= 16px` and `height >= 16px`. (Filters out 1x1 tracking pixels or favicon generators).
  2. **Complex Text or Multi-Color Rendering:** The script draws text with `length >= 10` characters (using `fillText` or `strokeText`), **or** draws with `>= 2` distinct fill/stroke colors. (Distinguishes biometric or device probing from simple icon rendering).
  3. **Readback Operation:** The script executes a readback method (`toDataURL`, `toBlob`, or `getImageData` covering `>= 16x16` pixels).
  4. **Benign Exclusions:** The canvas does **not** invoke `save()`, `restore()`, or register UI event listeners (`addEventListener("click"|"mousemove"|...)`). Interactive drawing widgets, image editors, and games routinely use save/restore and event listeners; fingerprinting scripts execute statically and throw away the canvas.

### 1.2 WebGL Fingerprinting Heuristic
- **Theoretical Basis:** WebGL provides low-level graphics pipeline access. Implementations leak underlying GPU hardware, driver versions, and floating-point precision capabilities.
- **Reference Specification:** Englehardt & Narayanan (2016); Acar et al., *"The Web Never Forgets: Persistent Tracking Mechanisms in the Wild"*, ACM CCS 2014.
- **Rule Criteria:** A script is flagged if it meets either of:
  - **Criterion A (Hardware Vendor Unmasking):** Queries the `WEBGL_debug_renderer_info` extension and extracts `UNMASKED_VENDOR_WEBGL` (0x9245) or `UNMASKED_RENDERER_WEBGL` (0x9246). Benign WebGL applications rarely query raw hardware strings; they rely on feature detection.
  - **Criterion B (Systematic Parameter Probing):** Calls `getParameter()` for `>= 10` distinct parameters, combined with querying `getSupportedExtensions()` or `getShaderPrecisionFormat()`.

### 1.3 AudioContext Fingerprinting Heuristic
- **Theoretical Basis:** Englehardt & Narayanan (2016); Cao et al., *"Cross-(Cross-)Browser Fingerprinting via OS and Hardware Level Features"*, NDSS 2017.
- **Rule Criteria:** A script is flagged if:
  - It creates an `OfflineAudioContext` (or `AudioContext`),
  - Connects an `OscillatorNode` through a `DynamicsCompressorNode`, and
  - Extracts the resulting synthesized buffer via `startRendering() -> oncomplete / getChannelData()`, or queries `analyser.getFloatFrequencyData()`.
- *Note:* General audio playback (`HTMLAudioElement`, simple background sound) is tracked separately under benign API usage and excluded from fingerprinting flags.

### 1.4 Font Probing Heuristic
- **Theoretical Basis:** Fifield & Egelman, *"Fingerprinting Web Users Through Font Metrics"*, Financial Cryptography 2015.
- **Rule Criteria:** A script is flagged if it tests for the presence of installed system fonts using either:
  - Calling `measureText()` or reading DOM layout dimensions (`offsetWidth`, `offsetHeight`, `getBoundingClientRect()`) for `>= 30` distinct font families within one visit, or
  - Calling `document.fonts.check()` across `>= 30` distinct font family queries.
  - Tracking fallback comparisons: measuring text width in test fonts against generic fallback fonts (`monospace`, `sans-serif`, `serif`).

### 1.5 Supporting Signals (High-Entropy Probing)
- **Role in Study:** In accordance with OpenWPM methodology, reading properties like `navigator.userAgent`, `navigator.hardwareConcurrency`, or `screen.width` does not constitute fingerprinting on its own (as these are used for responsive layouts).
- **Metric:** We compute a **Breadth Score** (number of distinct high-entropy properties accessed by a single script). A score `>= 5` indicates high-entropy system interrogation and is reported as contextual telemetry alongside verified vectors.

---

## 2. Statistical Analysis & Hypothesis Testing

All statistical comparisons in `fpstudy analyse` adhere to established biostatistical and empirical privacy measurement standards.

### 2.1 Binomial Proportions & Wilson Confidence Intervals
For site-level and vector-specific prevalence proportions $\hat{p} = \frac{x}{n}$, standard normal approximation (Wald interval) fails near 0 or 1. We compute the two-sided **Wilson score interval**:

$$w = \frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1-\hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

where $z = 1.96$ for a 95% confidence level.

### 2.2 Paired Countermeasure Evaluation: McNemar's Test
When assessing whether a countermeasure (e.g. `blocklist` or `extension_ublock`) reduces fingerprinting relative to `baseline`, each site is tested under **both** conditions. This constitutes paired binary data:

| | Condition B: Not Flagged | Condition B: Flagged |
| :--- | :---: | :---: |
| **Baseline: Not Flagged** | $a$ | $b$ (False negative of defense / drift) |
| **Baseline: Flagged** | $c$ (Successfully mitigated) | $d$ |

- **Null Hypothesis ($H_0$):** The countermeasure has no effect on fingerprinting prevalence ($p_b = p_c$).
- **Test Statistic:**
  - If discordant pairs $(b + c) < 25$, we compute the **Exact Binomial McNemar Test**:
    $$p = 2 \sum_{k=0}^{\min(b,c)} \binom{b+c}{k} \left(\frac{1}{2}\right)^{b+c}$$
  - If $(b + c) \ge 25$, we use the continuity-corrected Chi-Square statistic:
    $$\chi^2 = \frac{(|b - c| - 1)^2}{b + c}$$
- **Effect Size:**
  - **Odds Ratio (OR):** $\text{OR} = \frac{b}{c}$ (with Woolf's logit 95% CI).
  - **Absolute Risk Reduction (ARR):** $\text{ARR} = \frac{c - b}{n}$, with Newcombe paired 95% CI.

### 2.3 Continuous & Count Outcomes: Wilcoxon Signed-Rank Test
For count-based outcomes (e.g., number of fingerprinting scripts per site, or total tracking API invocations per site), data is heavily non-normal and right-skewed.
- We apply the **Wilcoxon signed-rank test** on paired non-zero differences.
- **Effect Size:**
  - **Rank-Biserial Correlation ($r$):** $r = \frac{W_+ - W_-}{W_+ + W_-}$.
  - **Hodges-Lehmann Estimator:** The median of all pairwise Walsh averages $(d_i + d_j) / 2$, providing a robust estimate of the median reduction.

### 2.4 Multiple Comparison Corrections
When testing multiple vectors simultaneously across several countermeasure conditions, the Family-Wise Error Rate (FWER) inflates.
- We apply the **Holm-Bonferroni step-down procedure**:
  $$p_{(i)} \le \frac{\alpha}{k - i + 1}$$
- Holm-Bonferroni is uniformly more powerful than standard Bonferroni while preserving strict FWER control at $\alpha = 0.05$.

---

## 3. Denominator Definitions & Failure Accounting

To prevent survivorship bias or skewed prevalence claims:
1. **Valid Comparison Cohort:** Countermeasure comparisons consider **only** domains that succeeded (`status == 'ok'`) in **both** paired runs.
2. **Prevalence Denominator:**
   - Primary prevalence is reported over successfully loaded sites ($N_{\text{ok}}$).
   - Beside every prevalence table, the pipeline exports the complete **Failure Taxonomy Table** detailing DNS errors, timeouts, HTTP 4xx/5xx errors, suspected bot blocks, and robots.txt disallows.
3. **Natural Variation Baseline:** The pipeline supports noise estimation by crawling a random sub-sample of baseline twice to establish the baseline-to-baseline natural discordance threshold.
