#!/usr/bin/env bash
# Complete first-time setup for Linux/macOS with Python 3.11+ installed.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if command -v python3 >/dev/null 2>&1; then PYTHON=python3; else PYTHON=python; fi
fi
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3.11 or newer is required (looked for: $PYTHON)." >&2
  exit 1
fi
"$PYTHON" - <<'PYVER'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required; found " + sys.version.split()[0])
print("Using Python", sys.version.split()[0])
PYVER

if [ ! -d .venv ]; then "$PYTHON" -m venv .venv; fi
VENV_PY="$PWD/.venv/bin/python"
"$VENV_PY" -m pip install --upgrade pip
"$VENV_PY" -m pip install -e ".[dev]"
"$VENV_PY" -m playwright install chromium

mkdir -p data/raw data/processed data/tranco
mkdir -p data/extensions/ubol
"$VENV_PY" -m fpstudy.install_ubol
"$VENV_PY" -m fpstudy.cli sample --top-n 1000
"$VENV_PY" manage.py migrate
"$VENV_PY" manage.py init_researcher
"$VENV_PY" -m fpstudy.cli selfcheck

cat <<'DONE'
Setup complete.
Start the web app: .venv/bin/python manage.py runserver 127.0.0.1:8000
CLI help:          .venv/bin/fpstudy --help
Researcher login:  researcher / researcher123
DONE
