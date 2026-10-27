# Browser Fingerprinting Measurement Pipeline (fpstudy)

An empirical measurement pipeline for quantifying browser fingerprinting prevalence on the web and evaluating the effectiveness of privacy countermeasures (tracker blocklists, browser extensions, browser anti-fingerprinting protections).

Built for an MSc dissertation project with academic rigor, full testability, reproducibility, and oral viva defensibility.

---

## 1. Overview & Architecture

Browser fingerprinting tracks users across the web without relying on persistent client-side state (such as HTTP cookies or LocalStorage) by interrogating hardware, driver, OS, and browser runtime capabilities.

This repository provides an automated, instrumented Playwright-based crawler that:
1. **Instruments browser APIs** using stealth client-side JavaScript hooks injected via `add_init_script` into every window, frame, and iframe.
2. **Collects and attributes API calls** across five distinct vector categories:
   - **Canvas:** 2D canvas text rendering, complex multi-color drawing, and image readback (`toDataURL`, `getImageData`).
   - **WebGL:** Parameter extraction (`getParameter`), hardware debugging constants (`WEBGL_debug_renderer_info`), shader precision inspection, and pixel readbacks.
   - **AudioContext:** Audio oscillator and dynamics compressor graph synthesis with buffer analysis (`OfflineAudioContext`, `getFloatFrequencyData`).
   - **Font Probing:** Font enumeration through measuring text and DOM element bounding metrics against fallback fonts (`offsetWidth`, `measureText`, `document.fonts.check`).
   - **Supporting Signals:** Reading high-entropy navigator and screen characteristics (`userAgent`, `platform`, `hardwareConcurrency`, `deviceMemory`, `screen.width/height`, `devicePixelRatio`, `Intl` timezone).
3. **Applies transparent, literature-grounded detection heuristics** (Englehardt & Narayanan, OpenWPM 2016) per script and per site.
4. **Evaluates Countermeasures** using paired within-subject statistical tests (**McNemar's test**, **Wilcoxon signed-rank test**, **Hodges-Lehmann estimator**, and **Holm-Bonferroni correction**) comparing baseline crawls against defensive conditions:
   - `baseline`: Vanilla Chromium.
   - `blocklist`: Network-level request cancellation against EasyPrivacy and Disconnect filter rules via Brave Rust `adblock` engine.
   - `extension_ublock`: uBlock Origin loaded into persistent contexts.
   - `canvas_defender`: Simulated controlled pixel-perturbation anti-fingerprinting defense.
   - `brave_shields`: Brave browser with native fingerprint protection (optional/flagged).
   - `firefox_rfp`: Firefox with `privacy.resistFingerprinting` (optional stretch goal).

---

## 2. Quickstart

### 2.1 Prerequisites
- Linux (Ubuntu 22.04+, Debian 12+, Fedora 38+, Arch), macOS 13+, or Windows WSL2.
- Python 3.11, 3.12, 3.13, or 3.14.
- Git.

### 2.2 Installation
```bash
# Clone repository
git clone https://github.com/example/fingerprinting-study.git
cd fingerprinting-study

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies and package in editable mode
pip install --upgrade pip
pip install -e ".[dev]"

# Install Playwright Chromium browser binary
playwright install chromium
```

### 2.3 Verify Installation & Environment Canaries
Verify that browsers launch, stealth hooks execute cleanly, and all countermeasure canaries pass:
```bash
fpstudy selfcheck
```
*Expected output:*
```text
Running system self-check and canary verifications...
  ✓ Playwright Chromium launched successfully.
  ✓ Condition canary passed: baseline
  ✓ Condition canary passed: blocklist
  ✓ Condition canary passed: canvas_defender
  ✓ Condition canary passed: extension_ublock
All environment checks and canaries PASSED.
```

### 2.4 Run Offline Tests & Code Coverage
The entire test suite runs offline without making network calls to external sites:
```bash
# Run all tests with coverage report
pytest --cov=src/fpstudy --cov-report=term-missing tests

# Verify linter and type-checker
ruff check src tests
ruff format --check src tests
mypy src
```

### 2.5 Run a Miniature Test Crawl on Local Fixtures
```bash
# Sample top 5 domains from bundled test list
fpstudy sample --top-n 5

# Crawl baseline condition
fpstudy crawl --condition baseline --limit 5

# Derive classifications directly from raw database events
fpstudy classify --run-id <RUN_ID_PRINTED_ABOVE>

# Generate reports and tables
fpstudy report
```

### 2.6 Run Live Web Smoke Crawl (Optional)
To verify real-world web functionality against live domains (marked with `@pytest.mark.live` and excluded by default):
```bash
pytest -m live tests/integration/test_live.py
```

---

## 3. CLI Command Reference

The command line interface is powered by Typer (`fpstudy`):

| Command | Arguments / Flags | Description |
| :--- | :--- | :--- |
| `fpstudy selfcheck` | `[--config-file PATH]` | Verifies host environment, browser binaries, stealth hooks, and condition canaries. |
| `fpstudy sample` | `--list-id ID --top-n N [--sector-file CSV]` | Downloads or pins a Tranco list, verifies SHA-256, and generates deterministic domain sample. |
| `fpstudy crawl` | `--condition NAME [--limit N] [--resume]` | Orchestrates automated crawl over sample with rate limits, robots.txt compliance, and failure logging. |
| `fpstudy classify` | `--run-id ID` | Derives rule-based classifications from immutable raw SQLite events without re-crawling. |
| `fpstudy validate` | `--labels CSV [--sample] [--run-id ID]` | Evaluates classifier precision/recall against ground-truth labels, or generates a stratified annotation sample. |
| `fpstudy analyse` | `--baseline ID --compare ID1 [ID2...]` | Computes paired McNemar odds ratios, Wilcoxon signed-rank tests, ARR CIs, and breakage comparisons. |
| `fpstudy report` | `[--config-file PATH]` | Regenerates all matplotlib publication-ready figures (PNG/PDF) and LaTeX tables in `reports/`. |

---

## 4. Configuration Reference

All experimental parameters are defined in YAML configuration files under `config/`:

- **`config/default.yaml`**:
  - `crawler.dwell_time_seconds`: Dwell time per page (default: 12.0s).
  - `crawler.navigation_timeout_seconds`: Page load timeout (default: 30.0s).
  - `crawler.global_concurrency`: Max concurrent browser contexts (default: 4).
  - `crawler.per_domain_delay_seconds`: Politeness delay between requests to same domain (default: 5.0s).
  - `crawler.user_agent_contact`: Mandatory research contact email (crawler aborts if left as default placeholder).
  - `sample.tranco_list_id`: Pinned Tranco list identifier.
- **`config/conditions.yaml`**:
  - Toggles and parameters for `baseline`, `blocklist`, `extension_ublock`, `canvas_defender`, `brave_shields`, and `firefox_rfp`.
- **`config/detection_rules.yaml`**:
  - Thresholds for Canvas (min dimensions >= 16px, min text length >= 10, min colors >= 2, exclude if save/restore).
  - Thresholds for WebGL (vendor unmasking flag, min parameters >= 10).
  - Thresholds for Audio (OfflineAudioContext + dynamics compressor + analyser check).
  - Thresholds for Fonts (distinct font families measured >= 30).
  - Thresholds for Supporting Signals (high breadth score >= 5).

---

## 5. Adding New Conditions & Detectors

### 5.1 How to Add a New Countermeasure Condition
1. Create a new module in `src/fpstudy/crawler/conditions/my_condition.py`.
2. Subclass `BaseCondition` and decorate with `@register_condition("my_condition")`:
```python
from fpstudy.crawler.conditions.base import BaseCondition, register_condition
from playwright.async_api import Browser, BrowserContext

@register_condition("my_condition")
class MyCondition(BaseCondition):
    async def prepare(self) -> None:
        pass

    async def launch_context(self, browser: Browser, context_options: dict) -> BrowserContext:
        ctx = await browser.new_context(**context_options)
        # Apply custom routing, extensions, or init_scripts here
        return ctx

    async def self_check(self, browser: Browser) -> dict:
        return {"passed": True, "details": "Canary verified"}
```
3. Add an entry to `config/conditions.yaml`:
```yaml
conditions:
  my_condition:
    name: "my_condition"
    description: "Custom privacy defense"
    browser_type: "chromium"
    enabled: true
```

### 5.2 How to Add a New Detector
1. Create a detector class in `src/fpstudy/detection/` implementing `analyze_events(script_url, events) -> DetectionResult`.
2. Instantiate the detector in `src/fpstudy/detection/classify.py` inside `ScriptClassifier.__init__`.
3. Add corresponding thresholds into `config/detection_rules.yaml`.
4. Add unit and integration tests with positive and negative fixture HTML pages in `tests/fixtures/`.

---

## 6. Repository Layout

```
fingerprinting-study/
├── pyproject.toml                # Pinned dependencies and tool configurations
├── Makefile                      # Standard build, lint, test, and CI targets
├── .gitignore                    # Git exclusions (data/raw, data/processed, cache)
├── .pre-commit-config.yaml       # Pre-commit hook definitions
├── .github/workflows/ci.yml      # GitHub Actions CI workflow
├── config/                       # Configuration definitions
│   ├── default.yaml              # Crawl, sample, storage, and politeness settings
│   ├── conditions.yaml           # Countermeasure condition definitions
│   └── detection_rules.yaml      # Literature-grounded classification thresholds
├── data/                         # Datasets and manifests
│   ├── tranco/                   # Tranco lists and verification manifests
│   ├── blocklists/               # EasyPrivacy and Disconnect filter rules
│   ├── labelled/                 # Hand-labelled validation template
│   ├── raw/                      # SQLite crawl databases (gitignored)
│   └── processed/                # Derived tables and exports (gitignored)
├── src/fpstudy/                  # Core library source code
│   ├── config.py                 # Pydantic v2 configuration schema
│   ├── sample.py                 # Tranco list management and domain candidate generator
│   ├── robots.py                 # Robots.txt parser and per-origin cache
│   ├── ratelimit.py              # Per-domain rate limiter and concurrency semaphore
│   ├── instrumentation/          # Client-side hooks and loader
│   │   ├── hooks.js              # Native-wrapping JavaScript API proxy hooks
│   │   └── loader.py             # Script injection and eTLD+1 attribution
│   ├── crawler/                  # Crawl runner and condition plugins
│   │   ├── browser.py            # Playwright browser lifecycle manager
│   │   ├── visit.py              # Single site visit and failure taxonomy
│   │   ├── runner.py             # Multi-domain concurrent crawl orchestrator
│   │   └── conditions/           # Plugin conditions (baseline, blocklist, uBlock, etc.)
│   ├── storage/                  # Immutable storage engine
│   │   ├── schema.py             # Pydantic data records
│   │   └── store.py              # SQLite WAL store with JSONL export/import
│   ├── detection/                # Rule-based script classifiers
│   │   ├── canvas.py             # Englehardt & Narayanan canvas heuristics
│   │   ├── webgl.py              # WebGL parameter and renderer heuristics
│   │   ├── audio.py              # AudioContext synthesis heuristics
│   │   ├── fonts.py              # Font probing heuristics
│   │   ├── signals.py            # Supporting high-entropy signals
│   │   ├── blocklist_match.py    # EasyPrivacy/Disconnect cross-matching
│   │   └── classify.py           # Multi-vector script and site aggregation
│   ├── analysis/                 # Statistical evaluation and reporting
│   │   ├── prevalence.py         # Wilson 95% confidence intervals
│   │   ├── compare.py            # McNemar, Wilcoxon, and Holm-Bonferroni tests
│   │   ├── breakage.py           # Page health and breakage metrics
│   │   ├── validation.py         # Precision, recall, and F1 validation tooling
│   │   └── plots.py              # Matplotlib figures and LaTeX table generator
│   └── cli.py                    # Typer CLI application
├── tests/                        # Comprehensive test suite (>= 85% coverage)
│   ├── unit/                     # Fast offline unit tests
│   ├── integration/              # Local fixture integration tests
│   ├── fixtures/                 # Synthetic HTML test pages (positive and benign)
│   └── conftest.py               # Shared pytest fixtures and ephemeral test servers
├── docs/                         # Detailed methodology and architectural documentation
│   ├── design.md                 # System architecture and Mermaid data flow
│   ├── methodology.md            # Rule criteria, paper citations, and statistical proofs
│   ├── ethics.md                 # Crawl ethics, robots.txt compliance, and GDPR
│   ├── limitations.md            # Limitations and technical caveats
│   └── reproducibility.md        # Determinism and replication guide
└── reports/                      # Dissertation support deliverables
    ├── dissertation_outline.md   # Chapter-by-chapter mapping to deliverables
    ├── literature_review_leads.md# Candidate academic papers
    ├── contextual_analysis_prompts.md # Legal, social, economic discussion prompts
    └── supervision_report_template.md# Weekly supervisor update template
```

---

## 7. Troubleshooting

- **Playwright Host Dependencies:** If Playwright complains about missing libraries on Linux, run `playwright install-deps` or install system packages (`libnss3`, `libatk1.0-0`, `libasound2`).
- **Research Contact Validation:** If `fpstudy crawl` exits with `ValueError: Crawler contact email must be configured`, update `crawler.user_agent_contact` in `config/default.yaml` with your institutional email.
- **SQLite Database Locks:** SQLite uses Write-Ahead Logging (`WAL` mode). If a crash leaves a lock, remove `.sqlite-wal` and `.sqlite-shm` files or ensure previous processes have terminated.
