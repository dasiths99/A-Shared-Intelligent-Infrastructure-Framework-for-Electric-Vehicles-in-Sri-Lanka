@echo off
REM ==========================================================================
REM  C3 - TerrainRoute : ENVIRONMENT SETUP (run once, safe to run again)
REM  Creates C3's own Python 3.11 environment (incl. geo libraries), installs
REM  libraries, registers the notebook kernel, installs frontend packages, prepares
REM  data, trained models, road graph and database if missing, runs the C3 tests.
REM  Then use run_c3.bat.
REM ==========================================================================
setlocal
title C3 TerrainRoute - environment setup
set "COMP=%~dp0"
pushd "%COMP%.."
set "ROOT=%CD%"
popd
set "ENV=%COMP%.venv"
set "PY=%ENV%\Scripts\python.exe"
echo.
echo  === C3 environment setup ===
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
  set "ENV=%LOCALAPPDATA%\J26\c3-env"
  set "PY=%LOCALAPPDATA%\J26\c3-env\Scripts\python.exe"
  echo       Project path too long for Windows DLL loading - using short environment path %LOCALAPPDATA%\J26\c3-env
)

echo [2/7] Creating C3 Python environment ...
if not exist "%PY%" (
  %BASE% -m venv "%ENV%" || (echo [ERROR] could not create the environment & goto fail)
) else (echo       already exists)

echo [3/7] Installing C3 libraries incl. geo stack (route_recommendation\requirements.txt) ...
"%PY%" -m pip install --upgrade pip -q || goto fail
"%PY%" -m pip install -r "%COMP%requirements.txt" -q || (echo [ERROR] pip install failed & goto fail)

echo [4/7] Registering notebook kernel "Python (J26 C3)" ...
"%PY%" -m ipykernel install --user --name j26-c3 --display-name "Python (J26 C3)" >nul || goto fail

echo [5/7] Installing frontend packages ...
pushd "%COMP%frontend"
call npm install --no-audit --no-fund --loglevel=error || (popd & echo [ERROR] npm install failed & goto fail)
popd

echo [6/7] Checking cleaned data, trained models, road graph and database ...
pushd "%ROOT%"
if not exist "%COMP%data\processed\bmw_segments_200m.parquet" (
  if exist "%COMP%data\raw\bmw_i3_tum" (
    echo       cleaned data missing - running data preparation (eVED step takes minutes^) ...
    "%PY%" -m route_recommendation.data_prep.run_all || (popd & goto fail)
  ) else (
    echo [WARN] raw data missing in route_recommendation\data\raw - see docs\MANUAL_DOWNLOADS.md
  )
) else (echo       cleaned data: OK)
dir /b "%COMP%results\c3_training_*.json" >nul 2>nul && (echo       trained models: OK) || (
  echo       trained models missing - running notebooks\c3_model_training.ipynb ...
  "%PY%" -c "import nbformat;from nbclient import NotebookClient as C;p=r'%COMP%notebooks\c3_model_training.ipynb';nb=nbformat.read(p,4);C(nb,timeout=3600,kernel_name='j26-c3',resources={'metadata':{'path':r'%COMP%notebooks'}}).execute();nbformat.write(nb,p)" || (popd & goto fail)
)
set "SEED="
if not exist "%COMP%database\c3.db" set "SEED=1"
if not exist "%COMP%data\processed\road_graph_edges.parquet" set "SEED=1"
if defined SEED (
  echo       road graph / database missing - building them ...
  "%PY%" -m route_recommendation.database.seed || (popd & goto fail)
) else (echo       road graph + database: OK)
popd

echo [7/7] Running C3 tests ...
pushd "%ROOT%"
"%PY%" -m pytest route_recommendation\tests -q -p no:cacheprovider -W ignore || (popd & echo [ERROR] tests failed & goto fail)
popd

echo.
echo  C3 environment is READY.  Start the app with run_c3.bat
echo.
pause
exit /b 0

:fail
echo.
echo  C3 setup did NOT finish - read the message above.
pause
exit /b 1
