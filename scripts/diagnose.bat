@echo off
setlocal enabledelayedexpansion
rem 1.41: "the app goes off sometimes" - collect what Fly.io knows, in one double-click, into diag\fly-diag.txt
rem (git-ignored, never committed). Nothing secret is written: no key, no token, no address of anyone.
cd /d "%~dp0.."
set "PATH=%USERPROFILE%\.fly\bin;%PATH%"
set APP=kyiv-air-watch-gb
if exist .flyapp set /p APP=<.flyapp
where fly >nul 2>&1 || (echo flyctl not found - run deploy-fly.bat once first. & pause & exit /b 1)
fly auth whoami >nul 2>&1 || fly auth login
if not exist diag mkdir diag
set OUT=diag\fly-diag.txt
echo === Heimdall - diagnostics ===
echo Collecting into %OUT% ...
> "%OUT%" echo Heimdall diagnostics, app %APP%, %date% %time%
>>"%OUT%" echo.
>>"%OUT%" echo ===== fly status =====
fly status -a %APP% >>"%OUT%" 2>&1
>>"%OUT%" echo.
>>"%OUT%" echo ===== machines =====
fly machine list -a %APP% >>"%OUT%" 2>&1
rem every machine's event log: starts, stops, exit codes, "oom_killed" when it ran out of memory
for /f "tokens=*" %%m in ('fly machine list -a %APP% -q 2^>nul') do (
  >>"%OUT%" echo.
  >>"%OUT%" echo ===== machine %%m =====
  fly machine status %%m -a %APP% >>"%OUT%" 2>&1
)
>>"%OUT%" echo.
>>"%OUT%" echo ===== recent logs =====
fly logs -a %APP% --no-tail >>"%OUT%" 2>&1
>>"%OUT%" echo.
>>"%OUT%" echo ===== 20 pings to /api/version (status, seconds) =====
for /l %%i in (1,1,20) do (
  curl -s -o NUL -m 20 -w "%%{http_code} %%{time_total}\n" https://%APP%.fly.dev/api/version >>"%OUT%" 2>&1
  timeout /t 2 /nobreak >nul
)
echo.
echo Done. Tell Claude: "diagnostic ready" - it reads diag\fly-diag.txt from this folder.
pause
