@echo off
REM ==========================================================================
REM  C1 - Smart Charge LK : SETUP (run once, safe to run again)
REM  Does everything for C1 on this computer and then starts the app:
REM   - installs Python and Node.js only if missing (any Python 3.10+ works) (asks first)
REM   - long project folder path: copies the project to C:\J26 and continues there
REM   - creates C1's own Python environment (.venv) and installs all libraries
REM   - registers the notebook kernel, installs the frontend packages
REM   - prepares data / models / database if missing, runs the C1 tests
REM   - starts backend + frontend (run_c1.bat) and opens the browser
REM  Arguments: nopause   = no pause and no app start (used by SETUP_NEW_COMPUTER.bat)
REM             nobrowser = start the app without opening the browser
REM ==========================================================================
setlocal
title C1 Smart Charge LK - environment setup
set "COMP=%~dp0"
pushd "%COMP%.."
set "ROOT=%CD%"
popd
set "ENV=%COMP%.venv"
set "PY=%ENV%\Scripts\python.exe"
echo.
echo  === C1 environment setup ===
echo  Project : %ROOT%
echo  Env     : %ENV%   ^(this part only^)
echo.

echo [1/7] Checking Python, Node.js and the project folder ...
if not defined J26_BASE_PY call "%ROOT%\shared\setup_prereqs.bat" || goto fail
if not defined J26_DEST set "J26_DEST=%ROOT%"
if /I not "%J26_DEST%"=="%ROOT%" (
  echo       Continuing in the short project folder %J26_DEST% ...
  call "%J26_DEST%\charging_scheduling\setup_c1.bat" %*
  exit /b
)
set BASE="%J26_BASE_PY%"

echo [2/7] Creating C1 Python environment ...
if not exist "%PY%" (
  %BASE% -m venv "%ENV%" || (echo [ERROR] could not create the environment & goto fail)
) else (echo       already exists)

echo [3/7] Installing C1 libraries (charging_scheduling\requirements.txt) ...
"%PY%" -m pip install --upgrade pip -q || goto fail
"%PY%" -m pip install -r "%COMP%requirements.txt" -q || (echo [ERROR] pip install failed & goto fail)

echo [4/7] Registering notebook kernel "Python (J26 C1)" ...
"%PY%" -m ipykernel install --user --name j26-c1 --display-name "Python (J26 C1)" >nul || goto fail

echo [5/7] Installing frontend packages ...
pushd "%COMP%frontend"
call npm install --no-audit --no-fund --loglevel=error || (popd & echo [ERROR] npm install failed & goto fail)
popd

echo [6/7] Checking data and trained models ...
pushd "%ROOT%"
if not exist "%COMP%data\processed\ev_sessions_clean.parquet" (
  if exist "%COMP%data\raw\acn_data" (
    echo       cleaned data missing - running data preparation (a few minutes^) ...
    "%PY%" -m charging_scheduling.data_prep.run_all || (popd & goto fail)
  ) else (
    echo [WARN] raw data missing in charging_scheduling\data\raw - see docs\MANUAL_DOWNLOADS.md
  )
) else (echo       cleaned data: OK)
dir /b "%COMP%results\baseload_xgb_*.json" >nul 2>nul && (echo       trained models: OK) || (
  echo       trained models missing - running notebooks\c1_model_training.ipynb ...
  "%PY%" -c "import nbformat;from nbclient import NotebookClient as C;p=r'%COMP%notebooks\c1_model_training.ipynb';nb=nbformat.read(p,4);C(nb,timeout=3600,kernel_name='j26-c1',resources={'metadata':{'path':r'%COMP%notebooks'}}).execute();nbformat.write(nb,p)" || (popd & goto fail)
)
popd

echo [7/7] Running C1 tests ...
pushd "%ROOT%"
"%PY%" -m pytest charging_scheduling\tests -q -p no:cacheprovider -W ignore --basetemp "%TEMP%\j26-pytest-c1" || (popd & echo [ERROR] tests failed & goto fail)
popd

echo.
echo  C1 environment is READY.
if /I "%~1"=="nopause" exit /b 0
echo  Starting the C1 Smart Charge LK app ...
echo.
call "%COMP%run_c1.bat" %*
exit /b 0

:fail
echo.
echo  C1 setup did NOT finish - read the message above.
if /I not "%~1"=="nopause" pause
exit /b 1
