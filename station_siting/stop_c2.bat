@echo off
REM  C2 - stop backend (8002) + frontend (5182) and close their windows.
title C2 GridSite Planner - stop
for %%P in (8002 5182) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do taskkill /PID %%I /T /F >nul 2>nul
)
taskkill /FI "WINDOWTITLE eq C2 backend*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq C2 frontend*" /T /F >nul 2>nul
echo C2 stopped (ports 8002 and 5182 free).
timeout /t 3 >nul
