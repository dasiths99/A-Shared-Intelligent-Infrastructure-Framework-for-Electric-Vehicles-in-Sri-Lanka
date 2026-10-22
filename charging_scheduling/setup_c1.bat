@echo off
REM ==========================================================================
REM  C1 - Smart Charge LK : ENVIRONMENT SETUP (run once, safe to run again)
REM  Creates C1's own Python 3.11 environment, installs libraries, registers the
REM  notebook kernel, installs frontend packages, prepares data/models if missing,
REM  and runs the C1 tests.  Afterwards start the app with run_c1.bat.
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
  set "ENV=%LOCALAPPDATA%\J26\c1-env"
  set "PY=%LOCALAPPDATA%\J26\c1-env\Scripts\python.exe"
  echo       Project path too long for Windows DLL loading - using short environment path %LOCALAPPDATA%\J26\c1-env
)

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
"%PY%" -m pytest charging_scheduling\tests -q -p no:cacheprovider -W ignore || (popd & echo [ERROR] tests failed & goto fail)
popd

echo.
echo  C1 environment is READY.  Start the app with run_c1.bat
echo.
pause
exit /b 0

:fail
echo.
echo  C1 setup did NOT finish - read the message above.
pause
exit /b 1
