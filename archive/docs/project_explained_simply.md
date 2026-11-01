# The project, explained simply

This guide is for explaining the project to a friend who has not read the code.

## The short version

This project is a research tool. It visits a list of popular websites, records certain browser-feature calls made by their JavaScript, and looks for patterns that may be used to identify a browser. It then compares the same websites with a privacy protection turned on, such as a tracker blocklist.

The tool does **not** prove that a website is tracking a person. It detects technical behaviours that can be used for browser fingerprinting. The results need checking and should be described carefully.

## What is browser fingerprinting?

A browser reveals many small details while displaying a page: how it draws graphics, which fonts it has, and which browser or graphics features it supports. One detail may be ordinary and harmless. A combination of details can help a site recognize a browser without storing a traditional cookie. That technique is called browser fingerprinting.

This project looks at four groups of signals:

- **Canvas:** drawing and reading back an image from a web page.
- **WebGL:** asking the browser or graphics card about supported 3D graphics features.
- **Audio:** generating and measuring sound inside the browser.
- **Fonts:** checking which fonts are installed by measuring text.

The project also records some browser and screen properties as context. Those properties alone are not counted as fingerprinting.

## How one measurement works

1. **Choose the websites.** The project uses a dated, identifiable Tranco ranking list, so the sample can be described and reproduced.
2. **Check the site’s crawl rules.** Before opening a page, the crawler checks `robots.txt`. If the site disallows the page, the crawler records a robots skip and does not visit it.
3. **Open the page in Chromium.** The crawler uses a fresh browser context and a short, fixed observation period.
4. **Record browser-feature activity.** Small JavaScript hooks record selected API calls and their script locations. The project stores event summaries, not full page recordings.
5. **Apply detection rules.** The classifier groups calls by script and checks whether they match configured patterns. For example, one WebGL call is not enough; a combination of hardware queries may be flagged.
6. **Summarize the data.** Successful visits are used to calculate prevalence. Failed or disallowed visits are listed separately.
7. **Compare conditions.** For a countermeasure comparison, each site should be visited in both conditions. The comparison uses only sites that loaded successfully in both.

## What the main terms mean

| Term | Plain-language meaning |
|---|---|
| **Condition** | A browser setup being studied, such as baseline or blocklist. |
| **Baseline** | Chromium without the study’s blocking protection. |
| **Blocklist** | A condition that checks page requests against EasyPrivacy rules and blocks matching subresources. |
| **Canary** | A controlled test that checks that a condition is active before a crawl begins. |
| **Successful visit (`ok`)** | The page loaded well enough for the study’s main prevalence calculation. |
| **Robots skip** | The site’s published crawl rules did not allow the requested page, so it was not visited. |
| **Denominator** | The number of eligible successful visits used in a percentage. |
| **Paired comparison** | Comparing the same domain under two different conditions. |
| **Confidence interval** | A range that shows uncertainty around an estimated percentage. Small samples produce wide ranges. |
| **Validation** | A person reviews examples and supplies ground-truth labels so classifier accuracy can be measured. |

## What the current results say

### The 10-site pilot

The baseline and blocklist runs attempted the same ten domains. Five loaded successfully in both conditions. The detector flagged at least one configured signal on four of those five, mainly WebGL. The five paired sites had identical classifications under baseline and blocklist.

That result is too small to show whether the blocklist works. It only says that this small pilot did not detect a difference on the five usable pairs.

### The newer 100-site baseline

The baseline run attempted 100 domains from Tranco list `GQ3LK`. Fifty-two loaded successfully. Eighteen of those 52 had at least one configured signal, mostly WebGL. The other 48 were skipped or failed and were not counted as fingerprinting-negative sites.

The matching blocklist run is now complete. Of the first 100 domains, 50 loaded successfully in both conditions: 18/50 had a signal in baseline and 15/50 under blocklist (36.0% vs 30.0%). The estimated reduction was not statistically significant (Holm-adjusted p=1.0). The blocklist did actively block requests: 797 across 48 visits.

A second, separately reported batch tested Tranco ranks 101–200. Forty-eight domains loaded in both conditions; 10/48 baseline sites and 7/48 blocklist sites had a signal (20.8% vs 14.6%). This difference also was not statistically significant (Holm-adjusted p=1.0). In that batch, the blocklist counter recorded 575 blocked requests across 45 visits. The two batches should remain separate in reporting because they were crawled at different times and may contain different types of domains.

So far, the blocklist was active and blocked requests, but the measurements have not shown a reliable change in the signals detected by this project. The rules still need a completed human-labelled validation set before we can claim how accurately they identify fingerprinting.

These results are from one Chromium version, one computer/network location, and short passive visits. They are pilot measurements, not conclusions about the whole web.

### Real extension test: uBlock Origin Lite

The project then tested the same 200 ranked domains with the genuine uBlock Origin Lite browser extension turned on. A built-in check confirmed the extension was running and redirected a known Google Analytics script into an extension resource.

Only 50 sites from ranks 1–100 and 48 sites from ranks 101–200 loaded successfully in both the matching baseline and extension visits. In the first group, the detector found a signal on 18/50 baseline visits and 13/50 extension visits (36% vs 26%). In the second group, it found a signal on 10/48 baseline visits and 6/48 extension visits (20.8% vs 12.5%). Both differences could be due to ordinary variation in this small sample; the statistical uncertainty includes no change. So the honest answer is: **the numbers went down in these runs, but we have not shown that uBOL reliably reduced the measured fingerprinting behaviour.**

uBOL handles tracker requests by redirecting them into the extension. The crawler’s ordinary failed-request counter does not count those redirects, so its zero does not mean the extension blocked nothing. The canary confirms one known tracker request was handled; this project does not have a complete extension block total.

The tool measures browser-feature calls. It does not prove that a site used the data to track a person, and it does not measure whether a browser became harder to recognize or link across visits.

### Expanded report: all 500 ranked domains

The study was expanded to ranks 1–500 of the same pinned Tranco list. Baseline has 499 stored visits because rank 423 (`firetvcaptiveportal.com`) did not produce a saved baseline visit; it also timed out under both protections. EasyPrivacy and uBOL each have 500 visit records. Failed pages and robots exclusions remain documented and are not counted as “no fingerprinting.”

Across 237 sites that loaded in both baseline and EasyPrivacy, the detector found a signal on 74 baseline visits and 61 protected visits (31.2% vs 25.7%). Across 240 sites that loaded in both baseline and uBOL, it found a signal on 77 baseline visits and 54 extension visits (32.1% vs 22.5%). The combined paired results support fewer recorded signals under both protections in these runs.

This updates the first-200-domain conclusion: the small batches alone were inconclusive, while the combined 500-domain paired analysis provides statistical evidence of a reduction in the API patterns measured by the detector. It still does not show that browsers became harder to recognize or that people were no longer tracked. The full results, technical details, failure counts, and 500-row appendix are in `reports/complete_500_domain_report_20261031.md`.

## Why robots skips stay in the study

The ranked sample still contains every selected domain. A robots-disallowed domain is recorded with status `skipped_robots`, but the crawler does not visit it. This is the responsible choice and avoids treating an unobserved site as a negative result.

If the research question requires a target number of successful sites, define an oversampling plan in advance (for example, attempt a larger consecutive section of the ranked list). Report both the number attempted and the number successfully observed. Do not silently replace skipped domains after seeing the results.

## The next research steps

1. The 500-domain baseline, blocklist, and uBOL results are recorded in the complete report. The paired analysis supports a reduction in the browser API patterns measured by this detector.
2. The user reports that the 100-example workbook was reviewed and is accurate. The saved CSV still has blank `ground_truth_label` cells. Enter the already-reviewed labels there and run `fpstudy validate` to calculate precision, recall, F1, and a confusion matrix.
3. Correct the browser/user-agent mismatch (Chromium 156 versus configured Chrome 124) before any confirmatory crawl.
4. If the intended claim is about being harder to fingerprint, run a separate repeated-visit linkability test. The current experiment measured API behavior, not whether sites could identify or link visitors.
5. Complete the literature review, dissertation discussion, and supervisor review of scope and ethics.

To reproduce a blocklist run over the same first 100 domains, the CLI can use an explicit limit so a larger `top_n` setting does not accidentally launch a larger study:

```bash
fpstudy crawl --condition blocklist --limit 100 --no-resume
```

Then classify and compare using the run IDs printed by the commands:

```bash
fpstudy classify --run-id <BLOCKLIST_RUN_ID>
fpstudy analyse --baseline run_baseline_20261028_081315_49e14b \
  --compare <BLOCKLIST_RUN_ID>
```

Before a broader crawl, confirm the university’s ethics process with the supervisor. Keep robots exclusions enabled.

## One-minute explanation for friends

> “My project studies browser fingerprinting. Websites can ask a browser about its graphics, audio, and fonts, and the combination may help tell browsers apart. I built a Python tool that visits 500 popular domains, records selected browser-feature calls, and compares the same sites with a normal browser, a tracker blocklist, and uBlock Origin Lite. Among sites that loaded in both versions, the tool found fewer fingerprinting-related patterns with both protections. This supports a reduction in the activity the tool measures. It does not yet prove that browsers became harder to recognize or that tracking stopped. I still need to save the labels from an already-reviewed set of examples so the detector’s accuracy can be calculated.”

## Where the files are

- Main pipeline instructions: `README.md`
- Technical design: `docs/design.md`
- Detection and analysis rules: `docs/methodology.md`
- Ethical and politeness policy: `docs/ethics.md`
- Full 500-domain results: `reports/complete_500_domain_report_20261031.md`
- Pilot findings: `reports/preliminary_10_site_research.md`
- 100-site baseline summary: `reports/baseline_100_site_run_20261028.md`
- Ranks 1–100 blocklist comparison: `reports/blocklist_100_comparison_20261029.md`
- Ranks 101–200 paired comparison: `reports/blocklist_comparison_ranks_101_200_20261029.md`
- Ranks 101–200 sample and settings: `data/tranco/tranco_GQ3LK_ranks_101_200.csv`, `config/next_100.yaml`
- Raw crawl data: `data/raw/fpstudy.sqlite`
