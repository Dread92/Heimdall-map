@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0.."
REM Publishes this folder to GitHub as <you>/Heimdall-map (private), or pushes the changes if it is already there.
REM (The repository was called clear-sky until October 2026; GitHub sends the old address to the new one.)
set "REPO=Heimdall-map"
REM Needs GitHub CLI: winget install GitHub.cli   (then run this script; it logs you in via the browser)
where gh >nul 2>nul || (echo GitHub CLI not found. Run:  winget install GitHub.cli  and re-run this script. & pause & exit /b 1)
gh auth status >nul 2>nul || gh auth login --web
if errorlevel 1 (echo Sign-in did not complete. & pause & exit /b 1)

if not exist .git (
  git init -b main
  git add -A
  git commit -m "Heimdall - air-raid tracker for Kyiv and Ukraine"
)

REM Anything not yet committed goes in now. An empty commit is not an error.
git add -A
git diff --cached --quiet || git commit -m "update %date% %time%"

REM The folder can have commits but no remote - that is the state this script used to fall over on.
git remote get-url origin >nul 2>nul
if errorlevel 1 (
  for /f "delims=" %%u in ('gh api user --jq .login') do set "GHUSER=%%u"
  if "!GHUSER!"=="" (echo Could not read your GitHub username. Run:  gh auth login --web  & pause & exit /b 1)
  gh repo view "!GHUSER!/!REPO!" >nul 2>nul
  if errorlevel 1 (
    echo Creating private repo !GHUSER!/!REPO! ...
    gh repo create !REPO! --private --source . --remote origin --description "Heimdall: unofficial air-raid / drone tracker for Kyiv and Ukraine (Python stdlib + one HTML page)" || (echo Could not create the repo. & pause & exit /b 1)
  ) else (
    echo Linking this folder to the existing !GHUSER!/!REPO! ...
    git remote add origin "https://github.com/!GHUSER!/!REPO!.git"
  )
)

REM gh installs a credential helper, so this does not ask for a password or a token.
git push -u origin main
if errorlevel 1 (
  echo.
  echo Push failed. If it asked about a token, run:  gh auth setup-git
  pause & exit /b 1
)
echo.
echo Pushed. Nothing was printed that should stay secret.
pause
