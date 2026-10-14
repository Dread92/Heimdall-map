@echo off
rem One-time: turns on the written summaries of each night / week on the dashboard (Anthropic API key).
rem The key goes straight into Fly's secret store - never into a file, the repository or the chat.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
echo.
echo === Heimdall - AI summaries ===
echo Create a key at https://platform.claude.com (API keys), then paste it here (right-click pastes).
echo.
set "KEY="
set /p KEY=Anthropic API key (starts with sk-ant-): 
if "%KEY%"=="" (echo Nothing entered - nothing changed. & pause & exit /b 1)
echo ANTHROPIC_API_KEY=%KEY%| fly secrets import -a %APP%
set "KEY="
if errorlevel 1 (echo *** fly could not store the key. & pause & exit /b 1)
echo.
echo Done. Fly restarts the app; last night is written up within a few minutes (dashboard: Nights and weeks).
echo Close this window - the key was shown on screen.
pause
