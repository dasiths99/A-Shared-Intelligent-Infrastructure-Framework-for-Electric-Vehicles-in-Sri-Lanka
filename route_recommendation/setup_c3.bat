@echo off
REM ==========================================================================
REM  C3 - TerrainRoute : SETUP (run once, safe to run again)
REM  Does everything for C3 on this computer and then starts the app:
REM   - installs Python and Node.js only if missing (any Python 3.10+ works) (asks first)
REM   - long project folder path: copies the project to C:\J26 and continues there
REM   - creates C3's own Python environment (.venv) and installs all libraries
REM   - registers the notebook kernel, installs the frontend packages
REM   - prepares data / models / database if missing, runs the C3 tests
REM   - starts backend + frontend (run_c3.bat) and opens the browser
REM  Arguments: nopause   = no pause and no app start (used by SETUP_NEW_COMPUTER.bat)
REM             nobrowser = start the app without opening the browser
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

echo [1/7] Checking Python, Node.js and the project folder ...
if not defined J26_BASE_PY call :prereqs || goto fail
if not defined J26_DEST set "J26_DEST=%ROOT%"
if /I not "%J26_DEST%"=="%ROOT%" (
  echo       Continuing in the short project folder %J26_DEST% ...
  call "%J26_DEST%\route_recommendation\setup_c3.bat" %*
  exit /b
)
set BASE="%J26_BASE_PY%"

:make_env
echo [2/7] Creating C3 Python environment ...
REM An environment copied from another computer points to that computer's Python - make a new one
if exist "%PY%" (
  "%PY%" -c "import sys" >nul 2>nul || (
    echo       existing environment does not work on this computer ^(copied from another computer?^) - creating it again ...
    rmdir /s /q "%ENV%"
  )
)
if not exist "%PY%" (
  %BASE% -m venv "%ENV%" || (echo [ERROR] could not create the environment & goto fail)
) else (echo       already exists)

echo [3/7] Installing C3 libraries incl. geo stack (route_recommendation\requirements.txt) ...
"%PY%" -m pip install --upgrade pip -q || goto fail
"%PY%" -m pip install -r "%COMP%requirements.txt" -q || (echo       pip install failed & goto libs_bad)
REM Check the libraries really load with this Python (a very new Python can break them)
"%PY%" -c "import fastapi, pydantic, sqlalchemy, pandas, numpy, scipy" 2>"%TEMP%\j26_libcheck.txt" && goto libs_ok
:libs_bad
echo       The libraries do not work with this Python version:
"%PY%" --version
powershell -NoProfile -Command "Get-Content $env:TEMP\j26_libcheck.txt -Tail 1"
if defined J26_RETRIED goto fail
set "J26_RETRIED=1"
echo       Switching C3 to Python 3.11 ^(the version the project was built with^) ...
call :python311 || goto fail
rmdir /s /q "%ENV%"
goto make_env
:libs_ok

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
"%PY%" -m pytest route_recommendation\tests -q -p no:cacheprovider -W ignore --basetemp "%TEMP%\j26-pytest-c3" || (popd & echo [ERROR] tests failed & goto fail)
popd

echo.
echo  C3 environment is READY.
if /I "%~1"=="nopause" exit /b 0
echo  Starting the C3 TerrainRoute app ...
echo.
call "%COMP%run_c3.bat" %*
exit /b 0

:fail
echo.
echo  C3 setup did NOT finish - read the message above.
if /I not "%~1"=="nopause" pause
exit /b 1

REM ==========================================================================
REM  :prereqs - Python, Node.js and a short project folder. The same block is in every
REM  setup file, so each one works on its own. Sets J26_BASE_PY and J26_DEST.
REM  - uses any installed Python 3.10+ (3.11 preferred); installs Python / Node.js LTS /
REM    Visual C++ runtime (for XGBoost)
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

REM ---- Microsoft Visual C++ runtime: XGBoost needs vcomp140.dll, which a new Windows may not have ----
if exist "%WINDIR%\System32\vcomp140.dll" goto vcrt_ok
echo       Microsoft Visual C++ runtime not found - needed by the XGBoost models.
choice /C YN /M "      Install it now"
if errorlevel 2 (echo [ERROR] Install it from https://aka.ms/vs/17/release/vc_redist.x64.exe and run this file again. & exit /b 1)
where winget >nul 2>nul && winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-package-agreements --accept-source-agreements
if exist "%WINDIR%\System32\vcomp140.dll" goto vcrt_ok
echo       Downloading the installer from Microsoft ...
curl -L -s -o "%TEMP%\vc_redist.x64.exe" https://aka.ms/vs/17/release/vc_redist.x64.exe && "%TEMP%\vc_redist.x64.exe" /install /passive /norestart
if not exist "%WINDIR%\System32\vcomp140.dll" (echo [ERROR] Install it from https://aka.ms/vs/17/release/vc_redist.x64.exe and run this file again. & exit /b 1)
:vcrt_ok
echo       Visual C++ runtime: OK

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

REM ==========================================================================
REM  :python311 - used when the libraries do not work with the installed Python version
REM  (e.g. a very new or early release). Finds or installs Python 3.11, the version the
REM  project was built and tested with.
REM ==========================================================================
:python311
set "J26_BASE_PY="
for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "J26_BASE_PY=%%P"
if not defined J26_BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "J26_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if defined J26_BASE_PY goto py311_ok
where winget >nul 2>nul || (echo [ERROR] Install Python 3.11 from https://www.python.org/downloads/release/python-3119/ and run this file again. & exit /b 1)
choice /C YN /M "      Install Python 3.11 now"
if errorlevel 2 (echo [ERROR] Python 3.11 is needed on this computer. & exit /b 1)
winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "J26_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined J26_BASE_PY (echo [ERROR] Python 3.11 install failed - install it from python.org and run this file again. & exit /b 1)
:py311_ok
set BASE="%J26_BASE_PY%"
echo       Python 3.11: %J26_BASE_PY%
exit /b 0
