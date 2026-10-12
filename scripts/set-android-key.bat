@echo off
rem One-time, after heimdall-android\scripts\2-make-key.bat: tells Android that the Heimdall app is this site's own, so it
rem opens full screen without an address bar (/.well-known/assetlinks.json). The fingerprint of the signing key is public
rem (anyone can read it from the APK); it goes into Fly's secrets like the other settings. The key itself never leaves your PC.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
echo.
echo === Heimdall - the Android app's key fingerprint ===
echo Paste the SHA256 line that 2-make-key.bat printed (AB:CD:...:EF, 32 pairs; right-click pastes).
echo.
set "FP="
set /p FP=SHA-256 fingerprint: 
if "%FP%"=="" (echo Nothing entered - nothing changed. & pause & exit /b 1)
(echo ANDROID_CERT_SHA256=%FP%)| fly secrets import -a %APP%
if errorlevel 1 (echo *** fly could not store it. & pause & exit /b 1)
echo.
echo Done. Fly restarts the app; check https://%APP%.fly.dev/.well-known/assetlinks.json - it names the app and this key.
pause
