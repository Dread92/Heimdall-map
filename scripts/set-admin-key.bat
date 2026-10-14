@echo off
rem 1.58.22: a new dashboard key (ADMIN_KEY). Made on this PC by Windows' own random generator, shown here ONCE so you
rem can save it in your password manager, and stored straight into Fly's secret store - never in a file, the
rem repository, a link or the chat. Fly keeps it write-only: nobody can read it back, not even with your Fly account.
rem Every dashboard session opened with the old key ends. The map stays public.
setlocal
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
echo.
echo === Heimdall - a new dashboard key ===
echo.
set "NEWKEY="
for /f "delims=" %%k in ('powershell -NoProfile -Command "$b=New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b).Replace('+','-').Replace('/','_').TrimEnd('=')"') do set "NEWKEY=%%k"
if "%NEWKEY%"=="" (echo Could not make a key - nothing changed. & pause & exit /b 1)
echo  Your new key - save it NOW in your password manager (or let the browser save it at the sign-in):
echo.
echo     %NEWKEY%
echo.
choice /c YN /m "Use this key (N: type your own, 16 characters or more)"
if errorlevel 2 (
  set "NEWKEY="
  set /p NEWKEY=Your own key: 
)
if "%NEWKEY%"=="" (echo Nothing entered - nothing changed. & pause & exit /b 1)
(echo ADMIN_KEY=%NEWKEY%)| fly secrets import -a %APP%
if errorlevel 1 (set "NEWKEY=" & echo *** fly could not store the key - nothing changed. & pause & exit /b 1)
set "NEWKEY="
echo.
echo Done. Fly restarts the app (about a minute). Then open
echo    https://%APP%.fly.dev/admin
echo and sign in with the new key. Everyone signed in with the old key is signed out.
echo Close this window - the key was shown on screen.
pause
