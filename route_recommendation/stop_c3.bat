@echo off
REM  C3 - stop backend (8003) + frontend (5183) and close their windows.
title C3 TerrainRoute - stop
for %%P in (8003 5183) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do taskkill /PID %%I /T /F >nul 2>nul
)
taskkill /FI "WINDOWTITLE eq C3 backend*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq C3 frontend*" /T /F >nul 2>nul
echo C3 stopped (ports 8003 and 5183 free).
timeout /t 3 >nul
