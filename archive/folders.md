# Project folders

```text
fingerprinting-study/
├── fpstudy/       Crawler, instrumentation, detectors, analysis, CLI
├── webapp/        Django pages, API views, styles and management commands
├── data/          Crawl database, domain samples, filters and extension assets
├── config/        Crawl conditions, detector rules and study settings
├── reports/       Tables and figures produced by `fpstudy report`
├── docs/          Current methodology and reproducibility notes
├── tests/         Unit and integration coverage
├── archive/       Old drafts, superseded reports, and retired implementation
├── setup.sh       Linux/macOS first-time setup
├── setup.bat      Windows first-time setup
├── requirements.txt Runtime Python dependencies
├── pyproject.toml  Package metadata and developer-tool configuration
└── manage.py       Django command entry point
```

## Why the main folders remain

- `data/` contains the SQLite database used by the web app and the crawl inputs/assets. The large generated database and unpacked browser extension are local runtime data.
- `config/` is read by the crawler and detector pipeline; moving it would break the current commands unless every path were redesigned.
- `reports/` is the output target for CLI-generated analysis tables and figures. The web dashboard reads SQLite directly, while this folder supports reproducible exports and paper-ready output.
- `tests/` protects the crawl, analysis, and webapp behavior during future code changes.
- `docs/` contains current research method and reproducibility guidance.
- `archive/` preserves historical notes and retired code without mixing it into the active package.

`pyproject.toml` is needed by pip to install `fpstudy` as a package and to configure the development tools. `requirements.txt` is the single source for runtime libraries; `pyproject.toml` reads dependencies from it. The `Makefile` is optional shortcuts for developers and CI workflows. It is not required to run the crawler or website.

The active Python package now lives directly in `fpstudy/`; there is no `src/` wrapper. Generated files such as `.venv/`, Python caches, `.egg-info`, and coverage output are machine-specific and ignored by git.
