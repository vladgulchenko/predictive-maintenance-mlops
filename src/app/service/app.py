import time
import uuid
from contextlib import asynccontextmanager
from json import JSONDecodeError, loads
from pathlib import Path
from typing import Literal

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mlflow import MlflowClient
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app import db
from app.config import settings

PREDICTIONS = Counter(
    "predictive_maintenance_predictions_total",
    "Predictions by predicted machine failure class",
    ["machine_failure"],
)
SCORE = Histogram(
    "predictive_maintenance_score",
    "Predicted machine failure probability",
    buckets=[i / 10 for i in range(11)],
)
MODEL_INFO = Gauge(
    "predictive_maintenance_model_info",
    "Model loaded by this pod",
    ["version"],
)
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1)


class Features(BaseModel):
    model_config = {"extra": "forbid"}

    Type: Literal["L", "M", "H"]
    air_temperature_k: float = Field(ge=295.0, le=315.0)
    process_temperature_k: float = Field(ge=305.0, le=325.0)
    rotational_speed_rpm: int = Field(ge=1000, le=3300)
    torque_nm: float = Field(ge=0.0, le=100.0)
    tool_wear_min: int = Field(ge=0, le=300)

class Prediction(BaseModel):
    model_config = {"protected_namespaces": ()}

    score: float = Field(ge=0, le=1)
    machine_failure: bool
    model_version: str
    request_id: str
    latency_ms: float = Field(ge=0)


def load_local_bundle():
    bundle = joblib.load(settings.model_path)
    return bundle["pipeline"], bundle["metadata"]


def load_registry_bundle():
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_registry_uri(settings.mlflow_tracking_uri)

    model_uri = f"models:/{settings.model_name}@{settings.model_alias}"
    pipeline = mlflow.sklearn.load_model(model_uri)

    client = MlflowClient(
        tracking_uri=settings.mlflow_tracking_uri,
        registry_uri=settings.mlflow_tracking_uri,
    )
    model_version = client.get_model_version_by_alias(settings.model_name, settings.model_alias)
    metadata_path = Path(client.download_artifacts(model_version.run_id, "metadata.json"))
    metadata = loads(metadata_path.read_text(encoding="utf-8"))
    metadata["model_version"] = f"{settings.model_name}:v{model_version.version}@{settings.model_alias}"
    return pipeline, metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.model_name:
        pipeline, metadata = load_registry_bundle()
    else:
        pipeline, metadata = load_local_bundle()

    app.state.pipeline = pipeline
    app.state.meta = metadata
    app.state.version = app.state.meta["model_version"]
    MODEL_INFO.labels(app.state.version).set(1)

    db.init()
    yield
    app.state.pipeline = None

app = FastAPI(title="predictive-maintenance-service",version="1.0",lifespan=lifespan)
Instrumentator().instrument(app, latency_lowr_buckets=LATENCY_BUCKETS).expose(app)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request,exc):
    request_id = str(uuid.uuid4())

    try:
        payload = await request.json()
    except JSONDecodeError:
        payload = {}

    db.save_prediction(
        request_id=request_id,
        feature=payload,
        score=None,
        latency_ms=None,
        prediction=None,
        model_version=getattr(app.state, "version", "unknown"),
        status_code=422,
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "request_id": request_id,
        },
    )

@app.get("/health")
def health():
    return {"status": "ok", "model_version": getattr(app.state,"version","unknown")}

@app.get("/ready")
def ready():
    if getattr(app.state,"pipeline",None) is None:
        raise HTTPException(status_code=503,detail="Model is not load")

    return {"status":"ready","model_version":getattr(app.state,"version","unknown")}

@app.post("/v1/predict")
def prediction(x: Features, bg: BackgroundTasks) -> Prediction:
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())
    payload = x.model_dump()

    feature_row = {
    "Type": payload["Type"],
    "Air temperature [K]": payload["air_temperature_k"],
    "Process temperature [K]": payload["process_temperature_k"],
    "Rotational speed [rpm]": payload["rotational_speed_rpm"],
    "Torque [Nm]": payload["torque_nm"],
    "Tool wear [min]": payload["tool_wear_min"],
}

    frame = pd.DataFrame([feature_row]).reindex(columns=app.state.meta["features"])

    score = float(app.state.pipeline.predict_proba(frame)[0,1])
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    prediction = score >= app.state.meta["threshold"]
    PREDICTIONS.labels(str(prediction).lower()).inc()
    SCORE.observe(score)

    bg.add_task(db.save_prediction,request_id,payload,score,latency_ms,prediction,app.state.version,200)

    return Prediction(score=score,machine_failure=prediction,model_version=app.state.version,request_id=request_id,latency_ms=latency_ms)
