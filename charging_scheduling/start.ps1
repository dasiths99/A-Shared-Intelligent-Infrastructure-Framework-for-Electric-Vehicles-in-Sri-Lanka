# C1 Smart Charge LK - starts backend (:8001) and frontend (:5181) in two windows.
# Usage (PowerShell):  .\charging_scheduling\start.ps1      then open http://localhost:5181
$root = Split-Path $PSScriptRoot -Parent
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; python -m uvicorn charging_scheduling.backend.app.main:app --port 8001 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
Start-Sleep -Seconds 6
Start-Process "http://localhost:5181"
