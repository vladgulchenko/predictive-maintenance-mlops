def test_predict_smoke(client, good_row):
    r = client.post("/v1/predict", json=good_row)
    assert r.status_code == 200

    body = r.json()
    assert 0.0 <= body["score"] <= 1.0
    assert isinstance(body["machine_failure"], bool)
    assert body["latency_ms"] >= 0
    assert body["model_version"]
    assert body["request_id"]


def test_numeric_sensor_values_affect_score(client, good_row):
    risky_row = {
        **good_row,
        "air_temperature_k": 304.2,
        "process_temperature_k": 313.2,
        "rotational_speed_rpm": 1200,
        "torque_nm": 65.0,
        "tool_wear_min": 220,
    }

    base_score = client.post("/v1/predict", json=good_row).json()["score"]
    risky_score = client.post("/v1/predict", json=risky_row).json()["score"]

    assert abs(base_score - risky_score) > 1e-12


def test_repeated_predictions_are_stable(client, good_row):
    s1 = client.post("/v1/predict", json=good_row).json()["score"]
    s2 = client.post("/v1/predict", json=good_row).json()["score"]
    assert abs(s1 - s2) < 1e-12
