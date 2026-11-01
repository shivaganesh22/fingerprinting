# Quick Setup & Execution Guide

This document describes how to set up and run the **Browser Fingerprinting Measurement Pipeline** and its **Django Web Application** on Linux, macOS, and Windows.

---

## 1. Automated Setup (Recommended)

### Linux & macOS
Run the automated bash script from the project root:
```bash
chmod +x setup.sh
./setup.sh
```

### Windows
Double-click `setup.bat` or run it from Command Prompt / PowerShell:
```cmd
setup.bat
```

The script automatically:
1. Creates the Python virtual environment (`.venv`).
2. Installs the project and developer tools. Runtime packages come from `requirements.txt`.
3. Installs the Playwright Chromium browser.
4. Downloads and verifies the pinned uBlock Origin Lite package and Tranco sample.
5. Runs database migrations and creates the researcher account.
6. Verifies the available condition canaries.

---

## 2. Manual Step-by-Step Setup

If you prefer to perform each step manually:

### Step 1: Create Virtual Environment
```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (Command Prompt)
python -m venv .venv
.venv\Scripts\activate.bat

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 2: Install Dependencies & Playwright
```bash
pip install --upgrade pip
pip install -e ".[dev]"
python -m playwright install chromium
python -m fpstudy.install_ubol
fpstudy sample --top-n 1000
```

### Step 3: Run Database Migrations
```bash
python manage.py migrate
```

### Step 4: Initialize Researcher Account
```bash
python manage.py init_researcher
```
*Default Credentials:*
- **Username:** `researcher`
- **Password:** `researcher123`

### Step 5: Verify System Health
```bash
fpstudy selfcheck
```

---

## 3. Running the Django Web Application

Start the local development server:
```bash
python manage.py runserver 0.0.0.0:8000
```
Open your browser at **http://localhost:8000/**.

### Main Navigation & Views:
- **Dashboard (`/`)**: Crawl totals, success rate, robots exclusions, API events, EasyPrivacy blocks, detector vectors, and recent runs. Condition summaries are descriptive across saved data.
- **Crawl Manager (`/run/`)**: Configure the sample, protection condition, dwell time, timeout, concurrency, and launch a crawl.
- **Live Monitor (`/run/<run_id>/`)**: View finished/target progress (`x/x`), Tranco ranks, counters, elapsed time, ETA, and recent visit results.
- **Reports (`/reports/`)**: Search by run ID and filter by condition or finished/in-progress state. The table separates page outcomes, detector results, and network counters.
- **Report Detail (`/reports/<run_id>/`)**: Review page outcomes, observed signals, request telemetry, vector prevalence, and a paginated domain table with Tranco ranks. Filter by visit status or detector result; export CSV. Block counts show as unavailable where Chromium does not expose reliable totals.
- **Paired Comparison (`/reports/compare/`)**: McNemar's test, 2×2 contingency matrix, odds ratio, absolute risk reduction with 95% confidence intervals, and Wilcoxon signed-rank test.
- **Documentation & Methodology (`/docs/`)**: Replication guide, RFC 9309 compliance rules, and failure taxonomy.

---

## 4. Running the Command-Line Crawler (`fpstudy`)

All crawl and analysis logic is also directly available via the `fpstudy` CLI:

```bash
# View all available CLI commands
fpstudy --help

# Deterministically sample top 100 domains from the pinned Tranco list
fpstudy sample --top-n 100

# Run a baseline crawl on the top 10 domains
fpstudy crawl --condition baseline --limit 10

# Run a crawl under the EasyPrivacy blocklist condition
fpstudy crawl --condition blocklist --limit 10

# Classify captured events
fpstudy classify --run-id <run_id>

# Run paired comparative statistical analysis
fpstudy report --baseline <baseline_run_id> --treatment <treatment_run_id>
```

---

## 5. Running the Test Suite

```bash
# Run all unit tests
pytest tests/unit/

# Run webapp tests
pytest tests/unit/test_webapp.py
```
