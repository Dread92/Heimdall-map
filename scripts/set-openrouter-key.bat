@echo off
rem One-time: turns on the AI reader, in shadow mode (1.50) - a language model reads the channels' posts beside the
rem rules, through OpenRouter. Nothing it says reaches the map; the dashboard's "AI reader" tab shows where it and the
rem rules disagree. The key goes straight into Fly's secret store - never into a file, the repository or the chat.
rem The server stops for the month at ai_reader_monthly_usd (config.json, 10 dollars); set a credit limit on the key
rem at OpenRouter as well.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
echo.
echo === Heimdall - AI reader (shadow mode, OpenRouter) ===
echo 1. Sign in at https://openrouter.ai and add a few dollars of credit (Settings - Credits).
echo 2. Settings - API Keys - Create Key. Name: heimdall-reader. Credit limit: 10 (dollars).
echo 3. Copy the key and paste it here (right-click pastes).
echo.
set "KEY="
set /p KEY=OpenRouter API key (starts with sk-or-): 
if "%KEY%"=="" (echo Nothing entered - nothing changed. & pause & exit /b 1)
echo OPENROUTER_API_KEY=%KEY%| fly secrets import -a %APP%
set "KEY="
if errorlevel 1 (echo *** fly could not store the key. & pause & exit /b 1)
echo.
echo Done. Fly restarts the app; the dashboard's AI reader tab fills as the channels post.
echo Close this window - the key was shown on screen.
pause
