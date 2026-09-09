@echo off
setlocal
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE where python >nul 2>&1 && set "PYEXE=python"

if not defined PYEXE (
    echo Python not found. Install Python 3.11 or 3.12 and add it to PATH.
    pause
    exit /b 1
)

if not exist ".venv" (
    %PYEXE% -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Starting app...
python desktop_app.py
pause
