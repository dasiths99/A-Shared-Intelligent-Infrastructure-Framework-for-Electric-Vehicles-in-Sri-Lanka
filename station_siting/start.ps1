# C2 GridSite Planner - starts backend (:8002) and frontend (:5182) in two windows.
# First time only: seed the database with the geo environment (see README):
#   <geo-python> -m station_siting.database.seed
# Usage (PowerShell):  .\station_siting\start.ps1      then open http://localhost:5182
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$PSScriptRoot\database\c2.db")) { Write-Warning "c2.db missing - run the seed first (README)"; exit 1 }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; python -m uvicorn station_siting.backend.app.main:app --port 8002 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
Start-Sleep -Seconds 6
Start-Process "http://localhost:5182"
