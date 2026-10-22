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
if not exist "%ROOT%\shared\config.py" (
  echo [ERROR] %ROOT%\shared\config.py is missing - C1 needs the shared folder.
  echo         Copy the WHOLE project folder ^(not only charging_scheduling^) and run this file again.
  goto fail
)
if not defined J26_BASE_PY call :prereqs || goto fail
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

REM ==========================================================================
REM  :prereqs - Python, Node.js and a short project folder. The same block is in every
REM  setup file, so each one works on its own. Sets J26_BASE_PY and J26_DEST.
REM  - uses any installed Python 3.10+ (3.11 preferred); installs Python / Node.js LTS
REM    with winget only if missing (asks first)
REM  - long project path (e.g. unzipped "...-main\...-main"): copies the project to C:\J26,
REM    because Windows cannot load Python DLLs or start the frontend tools (esbuild) from it
REM ==========================================================================
:prereqs
set "J26_SRC=%ROOT%"
REM ---- Python: any installed Python 3.10 or newer (3.11 preferred if present - the version the project was built with) ----
set "J26_BASE_PY="
set "J26_PYCHK=import sys; assert sys.version_info >= (3, 10); print(sys.executable)"
for /f "delims=" %%P in ('py -3.11 -c "%J26_PYCHK%" 2^>nul') do set "J26_BASE_PY=%%P"
if not defined J26_BASE_PY for /f "delims=" %%P in ('py -3 -c "%J26_PYCHK%" 2^>nul') do set "J26_BASE_PY=%%P"
if not defined J26_BASE_PY for /f "delims=" %%P in ('python -c "%J26_PYCHK%" 2^>nul') do set "J26_BASE_PY=%%P"
if defined J26_BASE_PY goto python_ok
echo       No Python found ^(3.10 or newer is needed^).
where winget >nul 2>nul || (echo [ERROR] Install Python from https://www.python.org/downloads/ and run this file again. & exit /b 1)
choice /C YN /M "      Install Python now"
if errorlevel 2 (echo [ERROR] Python is needed. & exit /b 1)
winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "J26_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined J26_BASE_PY (echo [ERROR] Python install failed - install it from python.org and run this file again. & exit /b 1)
:python_ok
"%J26_BASE_PY%" -c "import sys, platform; print('      Python ' + platform.python_version() + ': ' + sys.executable)"

REM ---- Node.js ----
where npm >nul 2>nul && goto node_ok
if exist "%ProgramFiles%\nodejs\npm.cmd" (set "PATH=%ProgramFiles%\nodejs;%PATH%" & goto node_ok)
echo       Node.js not found - needed for the web apps.
where winget >nul 2>nul || (echo [ERROR] Install Node.js LTS from https://nodejs.org and run this file again. & exit /b 1)
choice /C YN /M "      Install Node.js LTS now"
if errorlevel 2 (echo [ERROR] Node.js is needed. & exit /b 1)
winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
set "PATH=%ProgramFiles%\nodejs;%PATH%"
where npm >nul 2>nul || (echo [ERROR] Node.js install failed - install it from nodejs.org and run this file again. & exit /b 1)
:node_ok
echo       Node.js: OK

REM ---- project folder path ----
set "J26_DEST=%J26_SRC%"
set "J26_PLEN=0"
for /f %%L in ('powershell -NoProfile -Command "$env:J26_SRC.Length"') do set "J26_PLEN=%%L"
if %J26_PLEN% LEQ 130 (
  echo       Project folder: OK ^(%J26_PLEN% characters^)
  exit /b 0
)
echo       Project folder path is long ^(%J26_PLEN% characters^) - Windows cannot run Python and frontend files from it.
set "J26_DEST=C:\J26"
if exist "%J26_DEST%\" if not exist "%J26_DEST%\station_siting\setup_c2.bat" set "J26_DEST=%USERPROFILE%\J26"
if not exist "%J26_DEST%\" mkdir "%J26_DEST%" 2>nul || set "J26_DEST=%USERPROFILE%\J26"
if not exist "%J26_DEST%\" mkdir "%J26_DEST%" || (echo [ERROR] could not create %J26_DEST% & exit /b 1)
echo       Copying the project to %J26_DEST% ...
REM /XO keeps newer files already in the copy; c1.db (user accounts) is never overwritten
robocopy "%J26_SRC%" "%J26_DEST%" /E /XO /XD .venv node_modules __pycache__ .pytest_cache .ipynb_checkpoints /XF c1.db /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo [ERROR] copying to %J26_DEST% failed & exit /b 1)
echo       Copied. IMPORTANT: use the project in %J26_DEST% from now on.
exit /b 0
