@echo off
SET "BASE_DIR=%~dp0"
SET "PYTHON_EXE=%BASE_DIR%venv\Scripts\python.exe"
SET "SCRIPT_PATH=%BASE_DIR%get_current_signal.py"

echo --- Robust Forex Bot Automation Setup ---
echo Folder: %BASE_DIR%
echo Python: %PYTHON_EXE%

:: Delete the old task if it exists
schtasks /delete /tn "ForexPairsSignal" /f >nul 2>&1

:: Create the new task with ABSOLUTE paths and EXPLICIT working directory
schtasks /create /tn "ForexPairsSignal" /tr "'%PYTHON_EXE%' '%SCRIPT_PATH%'" /sc hourly /mo 1 /rl highest /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ SUCCESS! The bot is now scheduled to run every hour.
    echo Windows will now look in the correct folder: %BASE_DIR%
) else (
    echo.
    echo ❌ FAILED! Please run this file as Administrator.
)
pause
