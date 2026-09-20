import time
import uuid
from contextlib import asynccontextmanager

import json
import joblib
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from typing import Literal
from pydantic import BaseModel, Field


from app.config import settings
from app import db


class Features(BaseModel):
    model_config = {"extra": "forbid"}

    Type: Literal["L", "M", "H"]
    air_temperature_k: float = Field(gt=0)
    process_temperature_k: float = Field(gt=0)
    rotational_speed_rpm: int = Field(gt=0)
    torque_nm: float = Field(ge=0)
    tool_wear_min: int = Field(ge=0)

class Prediction(BaseModel):
    model_config = {"protected_namespaces": ()}

    score: float = Field(ge=0, le=1)
    machine_failure: bool
    model_version: str
    request_id: str
    latency_ms: float = Field(ge=0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = joblib.load(settings.model_path)
    app.state.pipeline = bundle["pipeline"]

    with open(settings.metadata_path,"r",encoding="utf-8") as f:
        app.state.meta = json.load(f)

    app.state.version = app.state.meta["model_version"]

    db.init()
    yield
    app.state.pipeline = None

app = FastAPI(title="predictive-maintenance-service",version="1.0",lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok", "model_version": getattr(app.state,"version","unknown")}

@app.get("/ready")
def ready():
    if getattr(app.state,"pipeline","None") is None:
        raise HTTPException(status_code=503,detail="Model is not load")

    return {"status":"ready","model_version":getattr(app.state,"version","unknown")}

@app.post("/v1/predict")
def prediction(x: Features, bg: BackgroundTasks) -> Prediction:
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())
    payload = x.model_dump()
    frame = pd.DataFrame([payload]).reindex(columns=app.state.meta["features"])

    score = float(app.state.pipeline.predict_proba(frame)[0,1])
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    prediction = score >= app.state.meta["threshold"]

    bg.add_task(db.save_prediction,request_id,payload,score,latency_ms,prediction)

    return Prediction(score=score,machine_failure=prediction,model_version=app.state.version,request_id=request_id,latency_ms=latency_ms)