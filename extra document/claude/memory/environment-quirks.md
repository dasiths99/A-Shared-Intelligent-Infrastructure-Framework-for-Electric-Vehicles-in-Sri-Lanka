---
name: environment-quirks
description: "Windows machine quirks for this project - Controlled Folder Access, port 5173 taken, per-component Python 3.11 envs, Python 3.14 default"
metadata:
  node_type: memory
  type: project
  originSessionId: c82d2d2f-1b2e-48d7-a347-0674f73a2809
  modified: 2026-10-20T06:37:23.944Z
---

- **Controlled Folder Access is ON** (Documents is protected): Git Bash cannot write into the project folder; PowerShell, python.exe, node/npm and the Write/Edit tools can. Use PowerShell for file moves.
- **Port 5173 is used by another project** (CSP 001 SmartTea Vite dev server). Project frontends use 5181/5182/5183 with `strictPort: true`; backends 8001/8002/8003.
- Default `python` is **3.14** (no TensorFlow; pandas 3). **Python 3.11 is also installed** (`py -3.11`).
- Each component has its **own Python 3.11 venv inside its folder**: `charging_scheduling\.venv`, `station_siting\.venv`, `route_recommendation\.venv`, created by `<component>/setup_cX.bat` (user's wish, 2026-10-20). Some DLL paths reach ~260 chars but Python 3.11 + LongPathsEnabled=1 loads them fine (tested sklearn, rasterio, osmium). Python 3.14 venvs at long paths did NOT load rasterio. Jupyter kernels `j26-c1/j26-c2/j26-c3`; `run_cX.bat` prefers `.venv`. Paths with spaces: start backend with `cmd /k ""%PY%" -m uvicorn ..."`. The old temp geo venv (`AppData\Local\Temp\geo430`, kernel `j26-geo`) is superseded.
- No Docker / PostgreSQL / Flutter installed.

**Why:** discovered/decided 2026-10-19 while building the apps; each cost debugging time.
**How to apply:** use the component's env python for its code/tests (e.g. `%LOCALAPPDATA%\J26-IT-430\c2-env\Scripts\python.exe`); check these before shell writes or starting dev servers. Related: [[develop-components-separately]]
