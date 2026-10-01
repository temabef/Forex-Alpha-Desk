@echo off
SET "ROOT_DIR=%~dp0"
echo ========================================================
echo Synchronizing Nautilus Engine code to Desk-5k and Desk-10k...
echo ========================================================

copy /Y "%ROOT_DIR%*.py" "%ROOT_DIR%Desk-5k\" >nul
copy /Y "%ROOT_DIR%*.py" "%ROOT_DIR%Desk-10k\" >nul

echo.
echo [SUCCESS] Both Desk-5k and Desk-10k updated with latest engine code!
echo (.env configurations and logs were safely preserved)
echo ========================================================
pause
