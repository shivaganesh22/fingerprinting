@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul || (echo Python 3.11 or newer was not found on PATH.& exit /b 1)
  set "PYTHON=py -3"
)
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" || (echo Python 3.11 or newer is required.& exit /b 1)
if not exist ".venv\Scripts\python.exe" %PYTHON% -m venv .venv || exit /b 1
set "VENV_PY=%CD%\.venv\Scripts\python.exe"
"%VENV_PY%" -m pip install --upgrade pip || exit /b 1
"%VENV_PY%" -m pip install -e ".[dev]" || exit /b 1
"%VENV_PY%" -m playwright install chromium || exit /b 1
if not exist data\raw mkdir data\raw
if not exist data\processed mkdir data\processed
if not exist data\tranco mkdir data\tranco
if not exist data\extensions\ubol mkdir data\extensions\ubol
"%VENV_PY%" -m fpstudy.install_ubol || exit /b 1
"%VENV_PY%" -m fpstudy.cli sample --top-n 1000 || exit /b 1
"%VENV_PY%" manage.py migrate || exit /b 1
"%VENV_PY%" manage.py init_researcher || exit /b 1
"%VENV_PY%" -m fpstudy.cli selfcheck || exit /b 1
echo Setup complete.
echo Start web app: .venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
echo CLI help: .venv\Scripts\fpstudy.exe --help
echo Login: researcher / researcher123
endlocal
