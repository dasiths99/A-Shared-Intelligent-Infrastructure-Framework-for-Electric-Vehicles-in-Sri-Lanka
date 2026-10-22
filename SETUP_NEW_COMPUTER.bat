@echo off
REM ==========================================================================
REM  J26-IT-430 EV framework : SETUP ON A NEW COMPUTER  (run once, safe to run again)
REM  1. Checks Python 3.11 and Node.js (offers to install them with winget)
REM  2. If the project folder path is long (e.g. unzipped "...-main\...-main"),
REM     copies the project to a short folder C:\J26 - long paths break Python
REM     DLL loading and the frontend tools (esbuild / Vite)
REM  3. Creates a separate Python environment for each part (C1, C2, C3) and
REM     installs everything by running setup_c1.bat, setup_c2.bat, setup_c3.bat
REM ==========================================================================
setlocal
title J26 - setup on a new computer
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
echo.
echo  === J26-IT-430 EV framework - setup on a new computer ===
echo  Project folder: %SRC%
echo.

echo [1/4] Checking Python 3.11 ...
set "J26_BASE_PY="
for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "J26_BASE_PY=%%P"
if not defined J26_BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "J26_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined J26_BASE_PY if exist "%ProgramFiles%\Python311\python.exe" set "J26_BASE_PY=%ProgramFiles%\Python311\python.exe"
if not defined J26_BASE_PY (
  echo       Python 3.11 not found. The project is built and tested with Python 3.11.
  where winget >nul 2>nul || (echo [ERROR] Install Python 3.11 from https://www.python.org/downloads/ and run this file again. & goto fail)
  choice /C YN /M "      Install Python 3.11 now with winget"
  if errorlevel 2 (echo [ERROR] Python 3.11 is needed. & goto fail)
  winget install -e --id Python.Python.3.11 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "J26_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined J26_BASE_PY (echo [ERROR] Python 3.11 install failed - install it from python.org and run this file again. & goto fail)
echo       Python 3.11: %J26_BASE_PY%

echo [2/4] Checking Node.js ...
where npm >nul 2>nul && goto node_ok
echo       Node.js not found.
where winget >nul 2>nul || (echo [ERROR] Install Node.js LTS from https://nodejs.org and run this file again. & goto fail)
choice /C YN /M "      Install Node.js LTS now with winget"
if errorlevel 2 (echo [ERROR] Node.js is needed for the web apps. & goto fail)
winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
set "PATH=%ProgramFiles%\nodejs;%PATH%"
where npm >nul 2>nul || (echo [ERROR] Node.js install failed - install it from nodejs.org and run this file again. & goto fail)
:node_ok
echo       Node.js: OK

echo [3/4] Checking the project folder path ...
set "DEST=%SRC%"
set "PLEN=0"
for /f %%L in ('powershell -NoProfile -Command "$env:SRC.Length"') do set "PLEN=%%L"
if %PLEN% LEQ 100 (
  echo       OK ^(%PLEN% characters^)
  goto setup
)
echo       The path is long ^(%PLEN% characters^) - Windows cannot run Python and frontend files from it.
set "DEST=C:\J26"
if exist "%DEST%\" if not exist "%DEST%\station_siting\setup_c2.bat" set "DEST=%USERPROFILE%\J26"
if not exist "%DEST%\" mkdir "%DEST%" 2>nul || set "DEST=%USERPROFILE%\J26"
if not exist "%DEST%\" mkdir "%DEST%" || (echo [ERROR] could not create %DEST% & goto fail)
echo       Copying the project to %DEST% ...
REM /XO keeps newer files already in the copy; c1.db (user accounts) is never overwritten
robocopy "%SRC%" "%DEST%" /E /XO /XD .venv node_modules __pycache__ .pytest_cache .ipynb_checkpoints /XF c1.db /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (echo [ERROR] copying to %DEST% failed & goto fail)
echo       Copied. Use the project in %DEST% from now on.

:setup
echo [4/4] Creating a separate Python environment for each part ...
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
echo  ==========================================================================
if defined FAILED (
  echo  Setup finished with problems in:%FAILED%  - scroll up to read the messages.
  goto fail
)
echo  ALL DONE. C1, C2 and C3 each have their own Python environment.
echo  Project folder: %DEST%
echo  Start a part with run_c1.bat / run_c2.bat / run_c3.bat inside its folder.
if /I not "%DEST%"=="%SRC%" (
  echo  IMPORTANT: use the copy in %DEST% from now on - the old folder can be deleted.
  start "" explorer "%DEST%"
)
echo  ==========================================================================
pause
exit /b 0

:fail
echo.
echo  Setup did NOT finish - read the message above.
pause
exit /b 1
