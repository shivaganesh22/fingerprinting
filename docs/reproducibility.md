# Reproducibility Guide (`docs/reproducibility.md`)

This guide provides exhaustive instructions for fully replicating the experimental findings, benchmarks, and figures produced by the `fpstudy` pipeline.

---

## 1. Experimental Determinism & Environment Pinning

To ensure identical experimental execution across different machines and operating systems:

### 1.1 Fixed Runtime & Platform Constraints
- **Python Version:** Pinned to Python 3.11+ (tested on Python 3.11, 3.12, 3.13, and 3.14).
- **Playwright Chromium:** Pinned to the bundled Playwright browser engine release. System architecture, OS kernel, and browser version are recorded automatically into the immutable run manifest for every crawl.
- **Fixed Browser Context Attributes:**
  To eliminate baseline-to-baseline environmental entropy, all browser contexts across all conditions enforce identical configurations:
  - `viewport`: `{width: 1920, height: 1080}`
  - `locale`: `"en-US"`
  - `timezone_id`: `"Europe/London"`
  - `device_scale_factor`: `1`
  - `is_mobile`: `False`
  - `has_touch`: `False`

### 1.2 Pinned Datasets & Integrity Manifests
- **Tranco Top Sites:** The Tranco list is pinned by immutable List ID (e.g., `5JNN9` or current configured ID). Downloaded files are verified via SHA-256 checksums recorded in `data/tranco/manifest.json`.
- **EasyPrivacy Blocklist:** A static snapshot of EasyPrivacy rules is stored at `data/blocklists/easyprivacy.txt` to insulate against upstream filter removals.
- **Disconnect Tracking List:** A static snapshot is stored at `data/blocklists/disconnect_blacklist.json`.

---

## 2. Resource Requirements & Runtime Estimates

### 2.1 Disk Usage
- **Virtual Environment & Dependencies:** ~450 MB.
- **Playwright Chromium Binary:** ~280 MB.
- **Crawl Database (`data/raw/crawl_storage.sqlite`):**
  - Top 1,000 domains per condition: ~60–120 MB (WAL mode).
  - Top 5,000 domains per condition: ~300–600 MB.
- **Figures & Tables (`reports/`):** ~15–30 MB total (PNG, vector PDF, CSV, LaTeX).

### 2.2 Execution Runtime Benchmarks
Based on default settings (global concurrency: 4 workers, per-domain dwell time: 12.0s, navigation timeout: 30.0s):

| Sample Size | Condition | Concurrency | Estimated Duration |
| :---: | :---: | :---: | :---: |
| **Top 100 domains** | `baseline` | 4 workers | ~8–12 minutes |
| **Top 1,000 domains** | `baseline` | 4 workers | ~3.0–4.0 hours |
| **Top 1,000 domains** | `blocklist` | 4 workers | ~2.5–3.5 hours |
| **Top 1,000 domains** | `extension_ublock` | 4 workers | ~3.0–4.0 hours |
| **Top 5,000 domains** | `baseline` | 6 workers | ~14.0–18.0 hours |

---

## 3. Step-by-Step Replication Protocol

Follow these commands in sequence to replicate a complete study run:

### Step 1: Environment Setup
```bash
git clone https://github.com/example/fingerprinting-study.git
cd fingerprinting-study

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

### Step 2: System Self-Check
```bash
fpstudy selfcheck
```
*Ensure all browser launches and condition canaries output green checkmarks (`✓`).*

### Step 3: Sample Generation
```bash
# Pin and download the configured Tranco top 1,000 sample
fpstudy sample --top-n 1000
```

### Step 4: Execute Crawls
```bash
# 1. Baseline crawl
fpstudy crawl --condition baseline --limit 1000

# 2. Blocklist countermeasure crawl
fpstudy crawl --condition blocklist --limit 1000

# 3. uBlock Origin extension crawl
fpstudy crawl --condition extension_ublock --limit 1000
```
*(If interrupted, rerun with `--resume` to skip already completed domains without losing data).*

### Step 5: Derive Classifications
```bash
# Derive classifications from raw events for each run ID printed above
fpstudy classify --run-id run_baseline_xxxxx
fpstudy classify --run-id run_blocklist_xxxxx
fpstudy classify --run-id run_extension_ublock_xxxxx
```

### Step 6: Comparative Statistical Analysis
```bash
# Run paired McNemar, Wilcoxon, and breakage comparisons
fpstudy analyse --baseline run_baseline_xxxxx --compare run_blocklist_xxxxx run_extension_ublock_xxxxx
```

### Step 7: Regenerate All Figures and Tables
```bash
fpstudy report
```
All outputs will be populated directly into `reports/figures/` and `reports/tables/`.
