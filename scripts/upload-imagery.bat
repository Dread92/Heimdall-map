@echo off
rem Puts the satellite layer (imagery\sat-ua.mbtiles, built by scripts/build_imagery.py) on the server's volume.
rem Once, and again only after a rebuild. Nothing secret is typed here; the map picks the file up by itself.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
if not exist imagery\sat-ua.mbtiles (echo imagery\sat-ua.mbtiles not found - nothing to upload. & pause & exit /b 1)
echo.
echo === Heimdall - satellite layer ===
echo.
for %%F in (imagery\sat-ua.mbtiles) do echo File to upload: %%~zF bytes
echo Free space on the server's volume:
fly ssh console -a %APP% -C "df -h /data"
echo.
echo If "Avail" above is smaller than the file, stop here (Ctrl+C) and extend the volume first:
echo    fly volumes list -a %APP%
echo    fly volumes extend VOLUME_ID -s 2 -a %APP%      (2 GB; about 0.15 USD a month per GB)
echo.
echo Otherwise press a key to upload. It takes a few minutes; the map keeps running meanwhile.
pause >nul
fly ssh console -a %APP% -C "rm -f /data/sat-ua.upload"
fly ssh sftp put imagery\sat-ua.mbtiles /data/sat-ua.upload -a %APP% || (echo *** upload failed - nothing changed on the server. & pause & exit /b 1)
fly ssh console -a %APP% -C "mv -f /data/sat-ua.upload /data/sat-ua.mbtiles" || (echo *** could not put the file in place. & pause & exit /b 1)
echo.
echo Done. Within a minute the map offers "Satellite imagery" in Layers (on by default on a computer).
pause
