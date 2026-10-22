@echo off
REM ==========================================================================
REM  C2 - GridSite Planner : ENVIRONMENT SETUP (run once, safe to run again)
REM  Creates C2's own Python 3.11 environment (incl. map/geo libraries), installs
REM  libraries, registers the notebook kernel, installs frontend packages, prepares
REM  data + database if missing, and runs the C2 tests.  Then use run_c2.bat.
REM ==========================================================================
setlocal
title C2 GridSite Planner - environment setup
set "COMP=%~dp0"
pushd "%COMP%.."
set "ROOT=%CD%"
popd
set "ENV=%COMP%.venv"
set "PY=%ENV%\Scripts\python.exe"
echo.
echo  === C2 environment setup ===
echo  Project : %ROOT%
echo  Env     : %ENV%   ^(this part only^)
echo.

echo [1/7] Checking Python 3.11 and Node.js ...
set "BASE="
py -3.11 -c "import sys" >nul 2>nul && set "BASE=py -3.11"
if not defined BASE (python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>nul && set "BASE=python")
if not defined BASE (echo [ERROR] Python 3.11 not found. Install it from python.org. & goto fail)
where npm >nul 2>nul || (echo [ERROR] Node.js / npm not found. Install Node.js LTS. & goto fail)
echo       Python: %BASE%   Node: OK

REM Long project folder (e.g. unzipped "...-main\...-main") pushes DLL paths inside .venv over the
REM Windows 260-character limit ("DLL load failed ... filename too long"): path > 150 chars, or > 120 chars when
REM Windows long-path support is off. Then use a short path instead.
set "SHORTENV=0"
for /f %%L in ('powershell -NoProfile -Command "$l=$env:COMP.Length; $lp=(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -ErrorAction SilentlyContinue).LongPathsEnabled; if (($l -gt 150) -or (($l -gt 120) -and ($lp -ne 1))) {1} else {0}"') do set "SHORTENV=%%L"
if "%SHORTENV%"=="1" (
  set "ENV=%LOCALAPPDATA%\J26\c2-env"
  set "PY=%LOCALAPPDATA%\J26\c2-env\Scripts\python.exe"
  echo       Project path too long for Windows DLL loading - using short environment path %LOCALAPPDATA%\J26\c2-env
)

echo [2/7] Creating C2 Python environment ...
if not exist "%PY%" (
  %BASE% -m venv "%ENV%" || (echo [ERROR] could not create the environment & goto fail)
) else (echo       already exists)

echo [3/7] Installing C2 libraries incl. geo stack (station_siting\requirements.txt) ...
"%PY%" -m pip install --upgrade pip -q || goto fail
"%PY%" -m pip install -r "%COMP%requirements.txt" -q || (echo [ERROR] pip install failed & goto fail)

echo [4/7] Registering notebook kernel "Python (J26 C2)" ...
"%PY%" -m ipykernel install --user --name j26-c2 --display-name "Python (J26 C2)" >nul || goto fail

echo [5/7] Installing frontend packages ...
pushd "%COMP%frontend"
call npm install --no-audit --no-fund --loglevel=error || (popd & echo [ERROR] npm install failed & goto fail)
popd

echo [6/7] Checking cleaned layers and database ...
pushd "%ROOT%"
if not exist "%COMP%data\processed\osm_pois.parquet" (
  if exist "%ROOT%\shared\data\raw\osm\sri-lanka-latest.osm.pbf" (
    echo       cleaned layers missing - running data preparation ...
    "%PY%" -m station_siting.data_prep.run_all || (popd & goto fail)
  ) else (
    echo [WARN] OSM raw file missing in shared\data\raw\osm - see docs\MANUAL_DOWNLOADS.md
  )
) else (echo       cleaned layers: OK)
if not exist "%COMP%database\c2.db" (
  echo       database missing - building c2.db ...
  "%PY%" -m station_siting.database.seed || (popd & goto fail)
) else (echo       database: OK)
popd

echo [7/7] Running C2 tests ...
pushd "%ROOT%"
"%PY%" -m pytest station_siting\tests -q -p no:cacheprovider -W ignore || (popd & echo [ERROR] tests failed & goto fail)
popd

echo.
echo  C2 environment is READY.  Start the app with run_c2.bat
echo.
pause
exit /b 0

:fail
echo.
echo  C2 setup did NOT finish - read the message above.
pause
exit /b 1
