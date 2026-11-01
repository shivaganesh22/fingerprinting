VENV ?= .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
RUFF = $(VENV)/bin/ruff
MYPY = $(VENV)/bin/mypy
PYTEST = $(VENV)/bin/pytest
PLAYWRIGHT = $(VENV)/bin/playwright
FPSTUDY = $(VENV)/bin/fpstudy

.PHONY: help setup install install-browsers lint format test test-unit test-integration coverage ci crawl analyse report selfcheck clean

help:
	@echo "Available targets:"
	@echo "  setup            - Create virtualenv and install dependencies"
	@echo "  install          - Install dependencies and editable package"
	@echo "  install-browsers - Install Playwright browser binaries (Chromium)"
	@echo "  lint             - Run ruff check and mypy type checking"
	@echo "  format           - Run ruff format and ruff check --fix"
	@echo "  test             - Run offline unit and integration tests"
	@echo "  coverage         - Run tests with code coverage report"
	@echo "  ci               - Run formatting check, linting, type check, and tests with coverage"
	@echo "  crawl            - Run crawler on baseline sample (configurable via CLI)"
	@echo "  analyse          - Run comparative statistical analysis"
	@echo "  report           - Regenerate all report figures and tables"
	@echo "  selfcheck        - Verify environment, hooks, and canaries"
	@echo "  clean            - Clean build, cache, and test artifacts"

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	$(PLAYWRIGHT) install chromium

install:
	$(PIP) install -e ".[dev]"

install-browsers:
	$(PLAYWRIGHT) install chromium

lint:
	$(RUFF) check fpstudy tests
	$(MYPY) fpstudy

format:
	$(RUFF) format fpstudy tests
	$(RUFF) check --fix fpstudy tests

format-check:
	$(RUFF) format --check fpstudy tests

test:
	$(PYTEST) tests

test-unit:
	$(PYTEST) tests/unit

test-integration:
	$(PYTEST) tests/integration

coverage:
	$(PYTEST) --cov=fpstudy --cov-report=term-missing --cov-report=html:htmlcov tests

ci: format-check lint coverage

selfcheck:
	$(PYTHON) -m fpstudy.cli selfcheck

migrate:
	$(PYTHON) manage.py migrate

runserver:
	$(PYTHON) manage.py runserver 127.0.0.1:8000

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/ .coverage*
