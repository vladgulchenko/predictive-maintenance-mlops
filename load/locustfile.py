from locust import HttpUser, between, task


PAYLOAD = {
    "Type": "M",
    "air_temperature_k": 298.1,
    "process_temperature_k": 308.6,
    "rotational_speed_rpm": 1551,
    "torque_nm": 42.8,
    "tool_wear_min": 0,
}


class PredictUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def predict(self):
        self.client.post("/v1/predict", json=PAYLOAD)