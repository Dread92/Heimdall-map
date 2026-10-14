@echo off
rem Heimdall on its own address (for example heimdall.com.ua). Buy the domain first, at any registrar.
rem Safe to run again: it skips what is already done. Nothing secret is typed here.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
echo.
echo === Heimdall - its own address ===
echo.
set "DOM="
set /p DOM=Domain you bought (e.g. heimdall.com.ua): 
if "%DOM%"=="" (echo Nothing entered - nothing changed. & pause & exit /b 1)
echo.
echo Step 1/3 - Fly: HTTPS certificates for %DOM% and www.%DOM% (free)
fly certs add %DOM% -a %APP% 2>nul
fly certs add www.%DOM% -a %APP% 2>nul
echo.
echo Step 2/3 - at your registrar, in the DNS settings of %DOM%, add:
echo    A      @     the v4 address below
echo    AAAA   @     the v6 address below
echo    CNAME  www   %APP%.fly.dev
echo.
fly ips list -a %APP%
echo.
echo (No v4 address in the list? Run:  fly ips allocate-v4 --shared -a %APP%   then run this script again.)
echo.
echo Save the records, then press a key. DNS takes a few minutes, sometimes up to an hour.
pause >nul
fly certs check %DOM% -a %APP%
echo.
choice /c YN /m "Does it say the certificate is Issued (or Ready)"
if errorlevel 2 (echo Not yet - run this script again in a few minutes. Nothing else was changed. & pause & exit /b 0)
echo.
echo Step 3/3 - the old address (%APP%.fly.dev) keeps working. Pages opened there will show
echo "Heimdall has moved to %DOM%" with a button that takes the reader there, places and settings included.
choice /c YN /m "Show that banner now"
if errorlevel 2 (echo OK - run this script again when you want it. & pause & exit /b 0)
echo CANONICAL_HOST=%DOM%| fly secrets import -a %APP%
if errorlevel 1 (echo *** fly could not store the setting. & pause & exit /b 1)
echo.
echo Done: https://%DOM%/m is Heimdall. Fly restarts the app; the banner appears on the old address within a minute.
pause
