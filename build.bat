@echo off
REM VinylRipper — Windows Build Script
REM Double-click this to produce a single VinylRipper.exe in dist/
REM No terminal knowledge required.

echo === VinylRipper Windows Build ===
echo.

cd /d "%~dp0"

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

REM Build the executable (--onefile is auto-enabled on Windows)
python scripts/build.py

echo.
echo === Build Complete! ===
echo Find VinylRipper.exe in the dist\VinylRipper folder
echo.
pause
