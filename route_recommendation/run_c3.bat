@echo off
REM ==========================================================================
REM  C3 - TerrainRoute  (route and charging stop)
REM  Double-click to start backend (port 8003) + frontend (port 5183).
REM  Stop with stop_c3.bat.   Optional argument: nobrowser
REM ==========================================================================
title C3 TerrainRoute - launcher
set "COMP=%~dp0"
pushd "%COMP%.."
set "ROOT=%CD%"
popd
set "NAME=C3"
set "BPORT=8003"
set "FPORT=5183"
set "MODULE=route_recommendation.backend.app.main:app"
set "HEALTH=http://localhost:%FPORT%/api/c3/health"

echo.
echo  === C3 TerrainRoute ===
echo  Project: %ROOT%
echo.

set "PY=python"
if exist "%COMP%.venv\Scripts\python.exe" set "PY=%COMP%.venv\Scripts\python.exe"
set "SHORTENV=0"
for /f %%L in ('powershell -NoProfile -Command "$l=$env:COMP.Length; $lp=(Get-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -ErrorAction SilentlyContinue).LongPathsEnabled; if ($l -gt 200) {2} elseif (($l -gt 150) -or (($l -gt 120) -and ($lp -ne 1))) {1} else {0}"') do set "SHORTENV=%%L"
if "%SHORTENV%"=="2" (
  echo.
  echo [ERROR] The project folder path is too long for Windows ^(over 200 characters^).
  echo         The frontend tools ^(esbuild / Vite^) cannot start from such a long path.
  echo         Move the project folder to a short place, for example  C:\J26\  ,
  echo         without a doubled ...-main\...-main folder, then run this file again.
  pause & exit /b 1
)
if "%SHORTENV%"=="1" if exist "%LOCALAPPDATA%\J26\c3-env\Scripts\python.exe" set "PY=%LOCALAPPDATA%\J26\c3-env\Scripts\python.exe"

if "%PY%"=="python" (where python >nul 2>nul || (echo [ERROR] Python not found - run setup_c3.bat first. & pause & exit /b 1))
"%PY%" -c "import sys" >nul 2>nul || (echo [ERROR] The Python environment does not work on this computer ^(copied from another computer?^) - run setup_c3.bat first. & pause & exit /b 1)
where npm >nul 2>nul || (echo [ERROR] Node.js / npm not found. Install Node.js. & pause & exit /b 1)
"%PY%" -c "import fastapi, uvicorn, sqlalchemy, xgboost" >nul 2>nul || (
  echo Installing backend requirements...
  "%PY%" -m pip install -r "%ROOT%\backend-requirements.txt" || (echo [ERROR] pip install failed & pause & exit /b 1)
)

if not exist "%ROOT%\route_recommendation\database\c3.db" (
  echo [ERROR] Database missing: route_recommendation\database\c3.db
  echo Build it once with the geo Python environment:  python -m route_recommendation.database.seed
  pause & exit /b 1
)

netstat -ano | findstr /R /C:":%BPORT% .*LISTENING" >nul && (echo [WARN] Port %BPORT% already in use - is %NAME% already running? Run stop_c3.bat first. & pause & exit /b 1)
netstat -ano | findstr /R /C:":%FPORT% .*LISTENING" >nul && (echo [WARN] Port %FPORT% already in use - run stop_c3.bat first. & pause & exit /b 1)

if not exist "%COMP%frontend\node_modules" (
  echo Installing frontend packages ^(first time only^)...
  pushd "%COMP%frontend"
  call npm install --no-audit --no-fund || (popd & echo [ERROR] npm install failed & pause & exit /b 1)
  popd
)

echo Starting backend  on http://localhost:%BPORT%  (API docs: /docs) ...
start "%NAME% backend :%BPORT%" /D "%ROOT%" cmd /k ""%PY%" -m uvicorn %MODULE% --port %BPORT%"
echo Starting frontend on http://localhost:%FPORT% ...
start "%NAME% frontend :%FPORT%" /D "%COMP%frontend" cmd /k npm run dev

echo Waiting for the app to be ready...
set /a TRIES=0
:wait
set /a TRIES+=1
curl -s -o nul -f "%HEALTH%" && goto ready
if %TRIES% GEQ 180 (echo [WARN] Not ready after 180 s - check the two server windows. & pause & exit /b 1)
timeout /t 1 /nobreak >nul
goto wait

:ready
echo.
echo  %NAME% is running:  http://localhost:%FPORT%
echo  Close it with stop_c3.bat
if /I not "%~1"=="nobrowser" start "" "http://localhost:%FPORT%"
timeout /t 5 >nul
exit /b 0
