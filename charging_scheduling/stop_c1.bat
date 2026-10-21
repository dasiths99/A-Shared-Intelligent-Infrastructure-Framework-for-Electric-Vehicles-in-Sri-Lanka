@echo off
REM  C1 - stop backend (8001) + frontend (5181) and close their windows.
title C1 Smart Charge LK - stop
for %%P in (8001 5181) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do taskkill /PID %%I /T /F >nul 2>nul
)
taskkill /FI "WINDOWTITLE eq C1 backend*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq C1 frontend*" /T /F >nul 2>nul
echo C1 stopped (ports 8001 and 5181 free).
timeout /t 3 >nul
