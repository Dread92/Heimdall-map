@echo off
setlocal enabledelayedexpansion
rem Ship a patch in one double-click: deploy what is committed here to Fly.io, then push it to GitHub.
rem The patch itself (code, tests, version, changelog, docs) is already committed in this folder.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp

echo.
echo === Heimdall - release ===
for /f "tokens=3" %%v in ('findstr /b /c:"APP_VERSION = " app\server.py') do set VER=%%~v
echo  version !VER!, app %APP%
git log -1 --format="  last commit: %%h %%s"
echo.

rem 1. Nothing half-done: everything must be committed, or the site and GitHub would not match.
set DIRTY=
for /f "delims=" %%i in ('git status --porcelain') do set DIRTY=1
if defined DIRTY (
  echo *** Some files are changed but not committed:
  git status --short
  echo *** Nothing was deployed. Ask Claude to commit them, or undo them, then run this again.
  pause & exit /b 1
)

rem 2. Deploy to Fly.io
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
fly auth whoami >nul 2>&1 || fly auth login
echo === 1/2 Deploying to Fly.io ===
rem Fly's own builder first. Its builder machine sometimes fails to answer ("failed to get status ... unable to
rem upgrade to h2c, received 500", 6 Oct 2026): then once more with Fly's other builder, Depot, before giving up.
fly deploy -a %APP% --ha=false --depot=false
if errorlevel 1 (
  echo.
  echo *** Fly's builder failed. Trying once more with the other builder - Depot...
  fly deploy -a %APP% --ha=false --depot=true
  if errorlevel 1 (echo *** Deploy failed twice - see above. GitHub was not touched. & pause & exit /b 1)
)

rem 3. Push to GitHub (the GitHub CLI sign-in is remembered; no password is asked)
echo.
echo === 2/2 Pushing to GitHub ===
git push
if errorlevel 1 (echo *** Push failed. Run scripts\github-push.bat, which repairs the sign-in, then this again. & pause & exit /b 1)

rem 4. What is running now
echo.
echo === Live version ===
curl -s https://%APP%.fly.dev/api/version
echo.
echo.
echo  Done: version !VER! is live on https://%APP%.fly.dev and on GitHub.
pause
exit /b 0
