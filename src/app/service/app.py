from contextlib import contextmanager

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

@contextmanager
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