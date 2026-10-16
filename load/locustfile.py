"""Трафик для Grafana и проверки rollout через Ingress.

Запуск UI: uv run locust -f load/locustfile.py --host http://pred-main.localhost
Перед запуском скачай датасет: uv run dvc pull -r laptop
"""

import random
from pathlib import Path

import pandas as pd
from locust import HttpUser, between, task

COLUMNS = {
    "Type": "Type",
    "Air temperature [K]": "air_temperature_k",
    "Process temperature [K]": "process_temperature_k",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_min",
}
DATA_PATH = Path(__file__).resolve().parents[1] / "data/raw/ai4i2020.csv"


def load_rows() -> list[dict]:
    if not DATA_PATH.is_file():
        raise FileNotFoundError("Нет CSV. Сначала выполни uv run dvc pull -r laptop")
    # Берем только входные признаки: без target, ID и причин отказа.
    features = pd.read_csv(DATA_PATH, usecols=list(COLUMNS)).rename(columns=COLUMNS)
    if features.empty or features.isna().any().any():
        raise ValueError("Для трафика нужны непустые строки без пропусков в признаках")
    return features.to_dict("records")


# Читаем CSV один раз при загрузке locustfile, а не при каждом запросе.
ROWS = load_rows()


class PredictUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def predict(self):
        with self.client.post(
            "/v1/predict", json=random.choice(ROWS), catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Ожидали HTTP 200, получили {response.status_code}")
                return
            try:
                body = response.json()
            except ValueError:
                response.failure("В ответе невалидный JSON")
                return
            score = body.get("score") if isinstance(body, dict) else None
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not 0 <= score <= 1
            ):
                response.failure("В ответе должен быть числовой score от 0 до 1")
