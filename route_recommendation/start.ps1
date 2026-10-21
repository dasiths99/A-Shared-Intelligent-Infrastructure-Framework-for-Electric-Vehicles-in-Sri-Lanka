# C3 TerrainRoute - starts backend (:8003) and frontend (:5183) in two windows.
# First time only: seed road graph + database with the geo environment (see README):
#   <geo-python> -m route_recommendation.database.seed
# Usage (PowerShell):  .\route_recommendation\start.ps1      then open http://localhost:5183
$root = Split-Path $PSScriptRoot -Parent
if (-not (Test-Path "$PSScriptRoot\database\c3.db")) { Write-Warning "c3.db missing - run the seed first (README)"; exit 1 }
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; python -m uvicorn route_recommendation.backend.app.main:app --port 8003 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; if (-not (Test-Path node_modules)) { npm install }; npm run dev"
Start-Sleep -Seconds 10
Start-Process "http://localhost:5183"
