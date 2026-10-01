@echo off
SET "BASE_DIR=%~dp0"
SET "BAT_5K=%BASE_DIR%run_desk_5k.bat"
SET "BAT_10K=%BASE_DIR%run_desk_10k.bat"
SET "BAT_JPY=%BASE_DIR%run_desk_jpy.bat"
SET "VBS_HIDDEN=%BASE_DIR%run_hidden.vbs"

:: Create the VBS wrapper script to run tasks invisibly
echo Set WshShell = CreateObject("WScript.Shell") > "%VBS_HIDDEN%"
echo WshShell.Run chr(34) ^& WScript.Arguments(0) ^& chr(34), 0, False >> "%VBS_HIDDEN%"

echo ========================================================
echo --- Tri-Desk Forex Bot Task Scheduler Setup ---
echo ========================================================
echo Base Directory: %BASE_DIR%
echo 5k Runner: %BAT_5K%
echo 10k Runner: %BAT_10K%
echo JPY Runner: %BAT_JPY%
echo Hidden Wrapper: %VBS_HIDDEN%
echo.

:: Delete existing tasks if they exist
schtasks /delete /tn "Forex-Bot-5k" /f >nul 2>&1
schtasks /delete /tn "Forex-Bot-10k" /f >nul 2>&1
schtasks /delete /tn "Forex-Bot-JPY" /f >nul 2>&1
schtasks /delete /tn "Nautilus SMC Telegram Alerts" /f >nul 2>&1

:: Create tasks: 5k at XX:01, 10k at XX:02, JPY at XX:03, using wscript to run completely hidden
schtasks /create /tn "Forex-Bot-5k" /tr "wscript.exe \"%VBS_HIDDEN%\" \"%BAT_5K%\"" /sc hourly /st 00:01 /f
schtasks /create /tn "Forex-Bot-10k" /tr "wscript.exe \"%VBS_HIDDEN%\" \"%BAT_10K%\"" /sc hourly /st 00:02 /f
schtasks /create /tn "Forex-Bot-JPY" /tr "wscript.exe \"%VBS_HIDDEN%\" \"%BAT_JPY%\"" /sc hourly /st 00:03 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] All three Forex Bots have been scheduled!
    echo - Forex-Bot-5k  runs invisibly hourly at :01 - evaluating closed Bar 1
    echo - Forex-Bot-10k runs invisibly hourly at :02 - evaluating closed Bar 1
    echo - Forex-Bot-JPY runs invisibly hourly at :03 - evaluating closed Bar 1 (AquaFunded JPY Alpha)
) else (
    echo.
    echo [FAILED] Please right-click setup_automation.bat and select "Run as administrator".
)
echo ========================================================
pause
