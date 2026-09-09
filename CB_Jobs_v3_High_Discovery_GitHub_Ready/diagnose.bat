@echo off
cd /d "%~dp0"
echo === SYSTEM ===
ver
echo.
echo === PY LAUNCHER ===
where py
py --version
echo.
echo === PYTHON ===
where python
python --version
echo.
echo === FILES ===
dir
echo.
echo === DIST ===
dir dist 2>nul
echo.
echo Send a screenshot of this window and any build error.
pause
