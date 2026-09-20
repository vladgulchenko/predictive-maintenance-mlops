import psycopg

from app.config import settings

DDL = """

CREATE TABLE IF NOT EXISTS predictions(

request_id      uuid PRIMARY KEY,
ts              timestamptz NOT NULL DEFAULT now(),
model_version   text NOT NULL,
features        jsonb NOT NULL,
score           double precision NOT NULL,
prediction      BOOLEAN NOT NULL,
latency_ms      real
)
"""

def init() -> None:
    if not settings.database_url:
        return
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(DDL)

# bg.add_task(db.save_prediction,request_id,payload,score,latency_ms,prediction)
def save_prediction(request_id:str, feature: dict, score: float, latency_ms: float, prediction: bool,model_version: str):
    if not settings.database_url:
        return
    with psycopg.connect(settings.database_url) as conn:
        conn.execute(
            "INSERT INTO predictions (request_id,model_version,features,score,prediction,latency_ms)"
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (request_id,model_version,feature,score,prediction,latency_ms)
        )