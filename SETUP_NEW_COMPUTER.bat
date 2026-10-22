@echo off
REM ==========================================================================
REM  J26-IT-430 EV framework : SETUP ON A NEW COMPUTER  (run once, safe to run again)
REM  Sets up ALL three parts and starts their apps:
REM   1. installs Python 3.11 and Node.js if missing (asks first)
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
echo [1/3] Checking Python 3.11, Node.js and the project folder ...
call "%~dp0shared\setup_prereqs.bat" || goto fail
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