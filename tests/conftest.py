import pytest
from fastapi.testclient import TestClient

from app.service.app import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def good_row():
    return {
        "Type": "M",
        "air_temperature_k": 298.1,
        "process_temperature_k": 308.6,
        "rotational_speed_rpm": 1551,
        "torque_nm": 42.8,
        "tool_wear_min": 0,
    }
