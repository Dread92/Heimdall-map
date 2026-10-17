@echo off
setlocal
rem Cloud deployment on Fly.io (24/7, no PC needed). Safe to re-run.
rem PREREQUISITE (once): add a payment method at https://fly.io/dashboard/personal/billing -- Fly refuses to create apps without it,
rem even though this single shared-cpu-1x VM + 1 GB disk stays inside the free allowance.
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
where fly >nul 2>&1 || (echo Installing flyctl... && powershell -Command "iwr https://fly.io/install.ps1 -useb | iex")
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
echo.
echo === 1/5 Log in ===
fly auth whoami >nul 2>&1 || fly auth login
if errorlevel 1 goto fail
echo.
echo === 2/5 App "%APP%" (region Amsterdam) ===
fly apps list 2>nul | findstr /i /c:"%APP%" >nul || fly apps create %APP% --org personal
if errorlevel 1 goto fail
echo %APP%>.flyapp
echo.
echo === 3/5 Persistent 1 GB disk for the history ===
fly volumes list -a %APP% 2>nul | findstr /i "data" >nul || fly volumes create data --size 1 --region ams --yes -a %APP%
if errorlevel 1 goto fail
echo.
echo === 4/5 Dashboard key ===
echo.
echo  ADMIN_KEY protects the private dashboard at /admin - the usage figures and the
echo  readings people flagged as wrong. THE MAP STAYS PUBLIC for everybody.
echo.
echo  (Never set ACCESS_KEY on a public app: that one puts a password box in front of
echo   the whole map, and nobody can read it without the key.)
echo.
echo  --- secrets currently set on this app ---
fly secrets list -a %APP% 2>nul
echo.
set KEY=
set /p KEY=Choose a dashboard key (12+ letters/digits, Enter to keep the current one): 
rem 1.58.35: through stdin, never on the command line (a process list or a shell history would show it)
if not "%KEY%"=="" (echo ADMIN_KEY=%KEY%| fly secrets import -a %APP% --stage)
if not "%KEY%"=="" set SHOWKEY=%KEY%
echo.
echo  Translation key (optional). The free Google translator refuses servers, so without a key the
echo  English feed uses the built-in glossary and there is no French. A DeepL API key makes EN and FR
echo  clear - free plan: 500,000 characters a month, https://www.deepl.com/pro-api . Posts are only
echo  translated while somebody is reading that language, so the allowance goes to what is read.
set DK=
set /p DK=DeepL API key (Enter to skip or keep the current one): 
if not "%DK%"=="" (echo DEEPL_KEY=%DK%| fly secrets import -a %APP% --stage)
echo.
echo === 5/5 Deploy ===
fly deploy -a %APP% --ha=false --depot=false
if errorlevel 1 goto fail
echo.
echo ======================================================
echo  The map, public - this is the link to share:
echo    https://%APP%.fly.dev
echo.
echo  Private dashboard - sign in there with your dashboard key (never put it in the address):
echo    https://%APP%.fly.dev/admin
echo.
echo  Update later: run this file again (or: fly deploy -a %APP%)
echo ======================================================
pause
exit /b 0
:fail
echo.
echo *** Stopped on an error (see above). Send the error text to Claude, or if it says "payment method required": add a card at
echo *** https://fly.io/dashboard/personal/billing then run this file again.
pause
exit /b 1
