# Browser Fingerprinting Measurement Pipeline (fpstudy)

An empirical measurement pipeline for quantifying browser fingerprinting prevalence on the web and evaluating the effectiveness of privacy countermeasures (tracker blocklists, browser extensions, browser anti-fingerprinting protections).

Built for an MSc dissertation project with academic rigor, full testability, reproducibility, and oral viva defensibility.

For a non-technical overview and a short explanation you can share with friends, see [`docs/project_explained_simply.md`](docs/project_explained_simply.md).

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
   - `extension_ubol`: uBlock Origin Lite loaded into persistent contexts.
   - `canvas_defender`: Simulated controlled pixel-perturbation anti-fingerprinting defense.
   - `brave_shields`: Brave browser with native fingerprint protection (optional/flagged).
   - `firefox_rfp`: Firefox with `privacy.resistFingerprinting` (optional stretch goal).

---

## 2. Quickstart

### 2.1 Prerequisites
- Linux (Ubuntu 22.04+, Debian 12+, Fedora 38+, Arch), macOS 13+, or Windows WSL2.
- Python 3.11 or newer.
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
python -m playwright install chromium
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
  ✓ Condition canary passed: extension_ubol
All environment checks and canaries PASSED.
```

### 2.4 Web Application (Django)
The project includes a Django research interface connected to the crawl database:

```bash
# Apply database migrations
python manage.py migrate

# Start the web application server
python manage.py runserver 127.0.0.1:8000
```
Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.

**Web Application Capabilities:**
- **Home / Dashboard:** Crawl totals, load rate, robots exclusions, API events, EasyPrivacy blocks, detector coverage, and recent runs. Condition summaries are descriptive; paired analysis compares treatments.
- **Run Manager:** Domain sample size selection (up to 5,000 domains from Tranco), verified condition selector, dynamic workload estimation, and non-blocking background crawler with live progress polling, cancel, and resume.
- **Reports & Telemetry:** Per-run outcomes, detector signals, requests, Tranco rank, filterable domain table, and CSV export. A blocked-request count shows as unavailable when the browser cannot measure it reliably.
- **Live Crawl Monitor:** Finished/target count (`x/x`), Tranco rank, visit outcomes, elapsed time, and ETA.
- **Runs list:** Search by run ID and filter by condition or run state; see site outcomes, detector results, request counters, and canary status together.
- **Cross-Condition Paired Comparison:** Statistical testing (McNemar test with Holm-Bonferroni correction, Absolute Risk Reduction with 95% CIs, Odds Ratio, Wilcoxon signed-rank test) on identically paired domains ($N_{paired}$).
- **Docs & Methodology:** Full scientific methodology, RFC 9309 robots.txt handling, vector heuristics, and replication instructions.
- **Authentication:** Researcher user registration, login, and session-secured crawl controls.

### 2.5 Run Offline Tests & Code Coverage
The entire test suite runs offline without making network calls to external sites:
```bash
# Run all tests with coverage report
pytest --cov=fpstudy --cov-report=term-missing tests

# Verify linter and type-checker
ruff check fpstudy tests
ruff format --check fpstudy tests
mypy fpstudy
```

### 2.5 Run the Local Fixture Tests
```bash
# These tests crawl local fixture pages only; they do not visit the live web.
pytest tests/integration/test_fixtures.py
```

### 2.6 Install and Run the Real Privacy Extension Condition
The study uses a pinned uBlock Origin Lite (uBOL) Chromium release. Download and verify it before crawling:
```bash
python -m fpstudy.install_ubol
fpstudy crawl --condition extension_ubol --limit 200 --no-resume
```
The crawl fails before collecting data unless the extension's service worker loads and its canary analytics request is redirected into an extension resource. The project does not silently substitute a mock or the built-in blocklist.

### 2.7 Run Live Web Smoke Crawl (Optional)
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
  - `crawler.concurrency`: Maximum concurrent browser contexts (default: 4).
  - `crawler.min_domain_delay_seconds`: Minimum delay between visits to the same domain (default: 5.0s), increased when `robots.txt` specifies a longer crawl delay.
  - `crawler.contact_email`: Mandatory research contact email included in the crawler User-Agent.
  - `sample.tranco_list_id`: Pinned Tranco list identifier.
- **`config/conditions.yaml`**:
  - Toggles and parameters for `baseline`, `blocklist`, `extension_ubol`, `canvas_defender`, `brave_shields`, and `firefox_rfp`.
- **`config/detection_rules.yaml`**:
  - Thresholds for Canvas (min dimensions >= 16px, min text length >= 10, min colors >= 2, exclude if save/restore).
  - Thresholds for WebGL (vendor unmasking flag, min parameters >= 10).
  - Thresholds for Audio (OfflineAudioContext + dynamics compressor + analyser check).
  - Thresholds for Fonts (distinct font families measured >= 30).
  - Thresholds for Supporting Signals (high breadth score >= 5).

---

## 5. Adding New Conditions & Detectors

### 5.1 How to Add a New Countermeasure Condition
1. Create a new module in `fpstudy/crawler/conditions/my_condition.py`.
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
1. Create a detector class in `fpstudy/detection/` implementing `analyze_events(script_url, events) -> DetectionResult`.
2. Instantiate the detector in `fpstudy/detection/classify.py` inside `ScriptClassifier.__init__`.
3. Add corresponding thresholds into `config/detection_rules.yaml`.
4. Add unit and integration tests with positive and negative fixture HTML pages in `tests/fixtures/`.

---

## 6. Repository Layout

The active project is compact and keeps its Python package at the root:

```text
fingerprinting-study/
├── fpstudy/          Crawler, instrumentation, detectors, analysis and CLI
├── webapp/           Django website, templates, static assets and commands
├── data/             Crawl database, domain lists, blocklists and extension assets
├── config/           Crawl, condition and detector configuration
├── reports/          Generated analysis tables and figures
├── docs/             Current research method and replication notes
├── tests/            Unit and integration tests
├── archive/          Historical documents and retired implementation
├── requirements.txt  Runtime Python dependencies
├── pyproject.toml    Package metadata and development-tool settings
├── setup.sh / .bat   New-machine setup scripts
└── manage.py         Django command entry point
```

`data/`, `config/`, and `reports/` have separate roles: data are crawler inputs and stored observations; config controls how a crawl runs and how signals are classified; reports are the reproducible CLI outputs. The web dashboard reads the SQLite database in `data/raw/`.

`pyproject.toml` is used by pip to install the `fpstudy` package and by the development tools. `requirements.txt` lists runtime libraries and is also read by `pyproject.toml`, so there is one dependency list. The optional `Makefile` provides shortcuts for developer and CI tasks; setup and normal operation do not require it.

## 7. Troubleshooting

- **Playwright Host Dependencies:** If Playwright complains about missing libraries on Linux, run `playwright install-deps` or install system packages (`libnss3`, `libatk1.0-0`, `libasound2`).
- **Research Contact Validation:** If `fpstudy crawl` exits with `ValueError: Crawler contact email must be configured`, update `crawler.user_agent_contact` in `config/default.yaml` with your institutional email.
- **SQLite Database Locks:** SQLite uses Write-Ahead Logging (`WAL` mode). If a crash leaves a lock, remove `.sqlite-wal` and `.sqlite-shm` files or ensure previous processes have terminated.
