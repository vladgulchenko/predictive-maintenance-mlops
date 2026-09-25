def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "model_version" in r.json()


def test_ready(client):
    assert client.get("/ready").status_code == 200


def test_bad_rotational_speed_is_422(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "rotational_speed_rpm": -1})
    assert r.status_code == 422


def test_unrealistic_temperature_is_422(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "air_temperature_k": 5000})
    assert r.status_code == 422


def test_missing_field_is_422(client, good_row):
    row = dict(good_row)
    del row["torque_nm"]
    assert client.post("/v1/predict", json=row).status_code == 422


def test_extra_field_is_422(client, good_row):
    r = client.post("/v1/predict", json={**good_row, "hacker_field": 1})
    assert r.status_code == 422
