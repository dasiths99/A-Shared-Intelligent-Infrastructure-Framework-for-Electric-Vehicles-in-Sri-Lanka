@echo off
REM ==========================================================================
REM  C2 - GridSite Planner : SETUP (run once, safe to run again)
REM  Does everything for C2 on this computer and then starts the app:
REM   - installs Python 3.11 and Node.js if missing (asks first)
REM   - long project folder path: copies the project to C:\J26 and continues there
REM   - creates C2's own Python environment (.venv) and installs all libraries
REM   - registers the notebook kernel, installs the frontend packages
REM   - prepares data / models / database if missing, runs the C2 tests
REM   - starts backend + frontend (run_c2.bat) and opens the browser
REM  Arguments: nopause   = no pause and no app start (used by SETUP_NEW_COMPUTER.bat)
REM             nobrowser = start the app without opening the browser
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

echo [1/7] Checking Python 3.11, Node.js and the project folder ...
if not defined J26_BASE_PY call "%ROOT%\shared\setup_prereqs.bat" || goto fail
if not defined J26_DEST set "J26_DEST=%ROOT%"
if /I not "%J26_DEST%"=="%ROOT%" (
  echo       Continuing in the short project folder %J26_DEST% ...
  call "%J26_DEST%\station_siting\setup_c2.bat" %*
  exit /b
)
set BASE="%J26_BASE_PY%"

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
"%PY%" -m pytest station_siting\tests -q -p no:cacheprovider -W ignore --basetemp "%TEMP%\j26-pytest-c2" || (popd & echo [ERROR] tests failed & goto fail)
popd

echo.
echo  C2 environment is READY.
if /I "%~1"=="nopause" exit /b 0
echo  Starting the C2 GridSite Planner app ...
echo.
call "%COMP%run_c2.bat" %*
exit /b 0

:fail
echo.
echo  C2 setup did NOT finish - read the message above.
if /I not "%~1"=="nopause" pause
exit /b 1
