import os

import psycopg
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for database integration tests",
)


def fetch_prediction_log(request_id: str):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT request_id, features, score, prediction, status_code
            FROM predictions
            WHERE request_id = %s
            """,
            (request_id,),
        )
        return cur.fetchone()


def test_successful_predict_is_logged(client, good_row):
    r = client.post("/v1/predict", json=good_row)

    assert r.status_code == 200

    body = r.json()
    row = fetch_prediction_log(body["request_id"])

    assert row is not None

    request_id, features, score, prediction, status_code = row

    assert str(request_id) == body["request_id"]
    assert features["Type"] == good_row["Type"]
    assert 0.0 <= score <= 1.0
    assert isinstance(prediction, bool)
    assert status_code == 200


def test_invalid_predict_is_logged(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "air_temperature_k": 5000})

    assert r.status_code == 422

    body = r.json()
    row = fetch_prediction_log(body["request_id"])

    assert row is not None

    request_id, features, score, prediction, status_code = row

    assert str(request_id) == body["request_id"]
    assert features["air_temperature_k"] == 5000
    assert score is None
    assert prediction is None
    assert status_code == 422
