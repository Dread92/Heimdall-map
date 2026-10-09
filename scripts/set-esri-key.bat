@echo off
rem One-time: turns on the closest zooms of the satellite layer (Esri World Imagery, ArcGIS Location Platform).
rem The key goes straight into Fly's secret store - never into a file, the repository or the chat.
rem The server asks Esri for the tiles, not the browser: the key needs the Basemaps privilege and NO referrer limit.
rem The server counts the tiles and stops under the free tier (esri_monthly_tiles in config.json, 1.8 M a month).
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
echo.
echo === Heimdall - close-zoom satellite imagery (Esri) ===
echo 1. Sign in at https://location.arcgis.com (ArcGIS Location Platform).
echo 2. Content - New item - Developer credentials - API key credentials.
echo    Privileges: Location services - Basemaps. Leave the referrer list empty.
echo 3. Copy the key and paste it here (right-click pastes).
echo.
set "KEY="
set /p KEY=Esri API key (starts with AAPT or AAPK): 
if "%KEY%"=="" (echo Nothing entered - nothing changed. & pause & exit /b 1)
(echo ESRI_KEY=%KEY%)| fly secrets import -a %APP%
set "KEY="
if errorlevel 1 (echo *** fly could not store the key. & pause & exit /b 1)
echo.
echo Done. Fly restarts the app; zoom in past a street on the satellite map to see it.
echo The month's count is on the dashboard (Satellite imagery).
echo Close this window - the key was shown on screen.
pause
