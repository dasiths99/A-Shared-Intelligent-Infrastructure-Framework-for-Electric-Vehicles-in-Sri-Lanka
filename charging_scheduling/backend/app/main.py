"""C1 backend - run from the project root:

    python -m uvicorn charging_scheduling.backend.app.main:app --port 8001 --reload

API docs: http://localhost:8001/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .db import Base, engine
from .routers import router
from .seed import seed_vehicle_models

Base.metadata.create_all(engine)
seed_vehicle_models()

app = FastAPI(title="J26-IT-430 · C1 Charging Scheduling API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
