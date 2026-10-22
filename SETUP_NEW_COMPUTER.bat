@echo off
REM ==========================================================================
REM  J26-IT-430 EV framework : SETUP ON A NEW COMPUTER  (run once, safe to run again)
REM  Sets up ALL three parts and starts their apps:
REM   1. installs Python and Node.js only if missing (any Python 3.10+ works) (asks first)
REM   2. long project folder path (e.g. unzipped "...-main\...-main"): copies the
REM      project to C:\J26 - Windows cannot run Python DLLs / esbuild from long paths
REM   3. runs setup_c1.bat, setup_c2.bat, setup_c3.bat - each part gets its own
REM      Python environment, libraries, frontend packages, data check and tests
REM   4. starts the C1, C2 and C3 apps (run_c1/c2/c3.bat)
REM  To set up only one part, run that part's setup_cX.bat instead.
REM ==========================================================================
setlocal
title J26 - setup on a new computer
echo.
echo  === J26-IT-430 EV framework - setup on a new computer ===
echo.
echo [1/3] Checking Python, Node.js and the project folder ...
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
call :prereqs || goto fail
set "DEST=%J26_DEST%"

echo [2/3] Setting up each part with its own Python environment ...
set "FAILED="
echo.
echo  ----- C1 charging scheduling -----
call "%DEST%\charging_scheduling\setup_c1.bat" nopause || set "FAILED=%FAILED% C1"
echo.
echo  ----- C2 station siting -----
call "%DEST%\station_siting\setup_c2.bat" nopause || set "FAILED=%FAILED% C2"
echo.
echo  ----- C3 route recommendation -----
call "%DEST%\route_recommendation\setup_c3.bat" nopause || set "FAILED=%FAILED% C3"
title J26 - setup on a new computer
echo.
if defined FAILED (
  echo  Setup finished with problems in:%FAILED%  - scroll up to read the messages.
  goto fail
)
echo  All three parts are READY.  Project folder: %DEST%

echo [3/3] Starting the apps ...
call "%DEST%\charging_scheduling\run_c1.bat" %1
call "%DEST%\station_siting\run_c2.bat" %1
call "%DEST%\route_recommendation\run_c3.bat" %1
title J26 - setup on a new computer
echo.
echo  ==========================================================================
echo  C1 Smart Charge LK   http://localhost:5181
echo  C2 GridSite Planner  http://localhost:5182
echo  C3 TerrainRoute      http://localhost:5183
echo  Stop them with stop_c1.bat / stop_c2.bat / stop_c3.bat inside each part's folder.
echo  Next time just use run_c1.bat / run_c2.bat / run_c3.bat.
echo  Project folder: %DEST%
echo  ==========================================================================
pause
exit /b 0

:fail
echo.
echo  Setup did NOT finish - read the message above.
pause
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
