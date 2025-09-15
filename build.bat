@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
echo ========================================
echo   yt2convert - Release Builder
echo ========================================
REM Activate virtual environment
if exist ".venv\" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Virtual environment not found! Run start.bat first.
    pause
    exit /b 1
)
REM Ensure PyInstaller is available in this venv
echo Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)
REM Clean previous builds
echo Cleaning previous builds...
if exist "build\" rmdir /s /q build
if exist "dist\" rmdir /s /q dist
if exist "yt2convert.spec" del yt2convert.spec
REM Check for required files
echo Checking requirements...
if not exist "main.py" (
    echo ❌ main.py not found!
    pause
    exit /b 1
)
if exist "ffmpeg.exe" (
    echo ✅ ffmpeg.exe found - will be bundled
    set INCLUDE_FFMPEG=1
) else (
    echo ⚠️  ffmpeg.exe not found - users will need it separately
    set INCLUDE_FFMPEG=0
)
echo.
echo Building standalone executable...
echo This will take a few minutes...
echo.
REM Use python -m PyInstaller to force using the venv’s PyInstaller
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "yt2convert" ^
    --distpath "./dist" ^
    --workpath "./build" ^
    --specpath "." ^
    --add-data "ffmpeg.exe;." ^
    --hidden-import "yt_dlp" ^
    --hidden-import "mutagen.easyid3" ^
    --hidden-import "mutagen.mp3" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "PySide6.QtNetwork" ^
    --exclude-module "tkinter" ^
    --exclude-module "matplotlib" ^
    --exclude-module "PyQt5" ^
    --upx-dir "upx" ^
    --version-file "version_info.txt" ^
    main.py
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   🎉 BUILD SUCCESSFUL! 🎉
    echo ========================================
    echo.
    for %%I in (dist\yt2convert.exe) do set SIZE=%%~zI
    set /a SIZE_MB=!SIZE!/1024/1024
    echo 📁 Release files:
    echo   • dist\yt2convert.exe ^(!SIZE_MB! MB^)
    if !INCLUDE_FFMPEG! equ 1 (
        echo   • FFmpeg is bundled inside the EXE
        echo   • Users just need the single EXE file!
    ) else (
        echo   • Users will need to download ffmpeg.exe separately
        echo   • Or install FFmpeg system-wide
    )
    echo.
    echo 🚀 Distribution instructions:
    echo   1. Share the dist\yt2convert.exe file
    echo   2. No installation required - just run it!
    echo   3. Windows will may show security warning initially
    echo   4. Users should click "More info" then "Run anyway"
    echo.
    (
        echo yt2convert - YouTube Audio Downloader
        echo =====================================
        echo.
        echo A free, simple YouTube audio downloader and converter.
        echo.
        echo FEATURES:
        echo - Download audio from YouTube videos
        echo - Convert to MP3 ^(multiple bitrates^) or WAV ^(multiple qualities^)
        echo - Modern, easy-to-use interface
        echo - No installation required
        echo.
        echo HOW TO USE:
        echo 1. Run yt2convert.exe
        echo 2. Paste a YouTube URL
        echo 3. Choose format and quality
        echo 4. Click Download
        echo.
        echo REQUIREMENTS:
        if !INCLUDE_FFMPEG! equ 1 (
            echo - None! Everything is included.
        ) else (
            echo - FFmpeg must be installed or ffmpeg.exe in same folder
        )
        echo - Internet connection
        echo.
        echo.
        echo Enjoy! 🎵
    ) > "dist\README.txt"
    set /p open="Open dist folder to see the release? (y/n): "
    if /i "!open!"=="y" explorer dist
) else (
    echo.
    echo ========================================
    echo   ❌ BUILD FAILED!
    echo ========================================
    echo.
    echo Common issues:
    echo - Missing dependencies (run start.bat first)
    echo - Antivirus blocking PyInstaller
    echo - Not enough disk space
    echo - File permissions issues
    echo.
    echo Check the error messages above for details.
)
echo.
echo Press any key to exit...
pause >nul
