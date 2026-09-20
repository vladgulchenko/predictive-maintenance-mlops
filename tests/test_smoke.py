def test_predict_smoke(client, good_row):
    r = client.post("/v1/predict", json=good_row)
    assert r.status_code == 200

    body = r.json()
    assert 0.0 <= body["score"] <= 1.0
    assert isinstance(body["machine_failure"], bool)
    assert body["latency_ms"] >= 0
    assert body["model_version"]
    assert body["request_id"]


def test_predict_handles_zero_tool_wear(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "tool_wear_min": 0})
    assert r.status_code == 200


def test_repeated_predictions_are_stable(client, good_row):
    s1 = client.post("/v1/predict", json=good_row).json()["score"]
    s2 = client.post("/v1/predict", json=good_row).json()["score"]
    assert abs(s1 - s2) < 1e-12
