> **Update:** This assessment reflects data available on 30 October. The 500-domain analysis is now complete; see [the updated assessment](research_completion_assessment_20261031.md) and [the full report](complete_500_domain_report_20261031.md). The pooled paired results support a reduction in this detector’s measured API patterns for both protections.

# Research completion assessment

**Assessment date:** 2026-10-30  
**Project brief:** *Measuring Browser Fingerprinting Prevalence and the Effectiveness of Privacy Countermeasures*  
**Overall status:** Substantial pilot work is complete; the research is not yet ready to claim that privacy protections reduce fingerprinting or tracking.

## The project’s end goal

The brief asks the project to measure fingerprinting-related behaviour on a defined sample of popular websites and evaluate privacy protections. Its expected outputs include a working measurement pipeline, literature review, empirical dataset and statistical analysis, countermeasure evaluation, contextual discussion, dissertation, and viva preparation.

The implemented outcome is narrower: the crawler detects configured browser API patterns that *may be used* for fingerprinting. It does not test whether a site actually identifies a browser across visits or uses the data to track a person. Any final title, research questions, and conclusion must state this narrower outcome unless a separate identity-linking experiment is designed.

## What is complete

| Work | Status | What the evidence supports |
|---|---|---|
| Crawler and event-recording pipeline | Built and used on live sites | It saves visit outcomes and browser API events, respects robots exclusions, and records reproducible run details. |
| 200-domain baseline and blocklist work | Two 100-domain batches compared | Among 50 and 48 matched successful visits, respectively, signal prevalence was lower under the blocklist, but results were statistically inconclusive. See the two blocklist reports. |
| Real extension comparison | Completed for 200 attempts using uBlock Origin Lite | The canary verified that the extension handled a known tracker request. The signal rate fell from 36% to 26% in batch 1 and from 20.8% to 12.5% in batch 2; both comparisons remain inconclusive. See the uBOL report. |
| Review of the 100 examples | User reports reviewing the workbook and finding it 100% accurate | The checked-in CSV has 100 rows, but all 100 `ground_truth_label` cells are blank. The review is acknowledged, but it is not yet machine-readable for reproducible precision/recall calculations. |
| Plain-language and methods documentation | Present | These explain what was measured and the main limitations. The literature leads and dissertation outline are scaffolds, not a verified literature review or completed dissertation. |

## Has the end goal been achieved?

**Not fully.** The pipeline and initial empirical comparison are complete. The existing evidence supports a cautious descriptive statement: this detector found fewer fingerprinting-related API patterns in the protected visits in these samples, but the uncertainty is too large to conclude the reduction is reliable.

That is a legitimate research result; the project does not need a protection to “win.” The missing part is enough validated and agreed evidence to answer the research question with confidence. In particular:

1. The brief names a top-1,000 or top-5,000 sample, or an agreed narrower sample. The current data covers 200 ranked domains. A 200-domain study can be presented as a pilot or a deliberately narrowed study if the supervisor accepts that scope; it should not silently be described as a completed top-1,000 study.
2. The numeric validation step needs the reviewed labels in the CSV. A statement that the workbook is accurate does not identify the 0/1 ground-truth value for each row, so the analysis cannot produce an auditable confusion matrix, precision, recall, or F1 yet. Do not fill those values by copying `predicted_flag` unless the reviewer explicitly confirms each example’s ground-truth value.
3. The brief calls for baseline repeat crawls to estimate natural variation. No baseline-versus-baseline noise estimate is reported.
4. The current studies do not measure cross-visit browser recognition or tracking outcomes. Do not claim “bypassing fingerprinting” or “preventing tracking” from API-call counts alone.
5. The full MSc deliverables still require a verified literature review, completed results/discussion chapters, and supervisor approval of the final scope and interpretation. Ethics requirements should be confirmed with the supervisor/university before further live crawling.

## What should happen next

### Fastest defensible completion path

1. **Use the existing review; do not re-review the examples.** Transfer the reviewed 0/1 decisions into the `ground_truth_label` column of `data/labelled/review_baseline_100_run_20261028.csv`, or save the completed workbook as CSV and place it there. This is the only data needed to calculate the validation metrics. The label value must be present for each reviewed row.
2. **Run the existing validation command** against that completed CSV and preserve its confusion matrix, precision, recall, and F1 output in the results report.
3. **Ask the supervisor to approve the 200-domain scope as a pilot/narrowed study**, or approve a specific larger target. If 200 is accepted, no additional crawl is needed merely to make the project look complete.
4. **Write the final results and discussion around the measured outcome.** State that results are inconclusive and cover API behaviour, describe excluded/failed visits, explain the single-machine/Chromium limits, and avoid claiming tracking prevention.
5. **Complete citation checking and the university ethics/supervisor review**, then finalize the dissertation and presentation/viva preparation.

### If the supervisor requires a stronger countermeasure claim

Before crawling more sites, agree a revised experiment that measures cross-visit linkability or another direct outcome of interest, includes repeat baseline crawls, and defines the sample and protections in advance. That would be a new experiment, not a missing calculation from the current data.

## What not to conclude

- “The extension bypassed fingerprinting” — not measured.
- “The extension prevented tracking” — not measured.
- “The blocklist/extension has no effect” — the sample is too uncertain to establish that either.
- “The detector is 100% accurate” — cannot be calculated until the row-level reviewed labels are present and the validation is run. The user’s review is acknowledged; the current CSV cannot reproduce it yet.

## Plain-English answer

The tool works and the project has real results. Those results hint that the protections may reduce some browser-feature probing, but they do not prove it. The fastest remaining path is to save the decisions from the review already completed, run the accuracy calculation, get the supervisor to accept the 200-domain scope, and finish the written research with the limits stated clearly.
