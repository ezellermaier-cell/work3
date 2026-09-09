@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo CB Jobs - Windows EXE Build
echo ============================================
echo.

set "PYEXE="
where py >nul 2>&1 && set "PYEXE=py"
if not defined PYEXE where python >nul 2>&1 && set "PYEXE=python"

if not defined PYEXE (
    echo ERROR: Python was not found.
    echo Use the included GitHub Actions workflow if you do not want Python installed locally.
    pause
    exit /b 1
)

if not exist ".venv" %PYEXE% -m venv .venv
call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
if errorlevel 1 goto :fail

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "CB Jobs" ^
  --icon "cb_jobs.ico" ^
  --add-data "cb_jobs.ico;." ^
  --add-data "cb_jobs.png;." ^
  --collect-all customtkinter ^
  --hidden-import zoneinfo ^
  desktop_app.py

if errorlevel 1 goto :fail

echo.
echo SUCCESS:
echo dist\CB Jobs.exe
explorer "%CD%\dist"
pause
exit /b 0

:fail
echo BUILD FAILED.
pause
exit /b 1
