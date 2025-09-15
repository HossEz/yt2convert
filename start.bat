@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ==============================
echo   yt2convert - Setup and Launch
echo ==============================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install/upgrade required packages
echo Installing/updating required packages...
python -m pip install --upgrade pip

REM Install packages with SSL bypass
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org yt-dlp PySide6 mutagen requests packaging

REM Update yt-dlp to latest version (helps with SSL issues)
echo Updating yt-dlp to latest version...
pip install --upgrade --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org yt-dlp

REM Set environment variables for SSL (helps with certificate issues)
set PYTHONHTTPSVERIFY=0
set SSL_VERIFY=false

REM Check if FFmpeg is available
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: FFmpeg is not found in PATH.
    echo The application will look for ffmpeg.exe in the current folder.
    echo If conversion fails, please:
    echo   1. Download FFmpeg from: https://ffmpeg.org/download.html
    echo   2. Place ffmpeg.exe in this folder, or
    echo   3. Install FFmpeg system-wide and add to PATH
    echo.
)

REM Run the application
echo.
echo Starting yt2convert...

python main.py

REM Keep the window open after the app closes
echo.
echo Application closed.
pause