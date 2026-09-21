# Predictive Maintenance MLOps

ML-сервис для предсказания риска отказа оборудования.

## Быстрый Запуск

```powershell
git clone https://github.com/vladgulchenko/predictive-maintenance-mlops.git
cd predictive-maintenance-mlops
docker compose up --build
```

Swagger:

```text
http://localhost:8000/docs
```

Health:

```text
http://localhost:8000/health
```

Ready:

```text
http://localhost:8000/ready
```

## Тестовый Predict

Endpoint:

```text
POST /v1/predict
```

Body:

```json
{
  "Type": "M",
  "air_temperature_k": 298.1,
  "process_temperature_k": 308.6,
  "rotational_speed_rpm": 1551,
  "torque_nm": 42.8,
  "tool_wear_min": 0
}
```

## Тесты

```powershell
uv sync
uv run pytest
```

## Kubernetes

Собрать image:

```powershell
docker build -t predictive-maintenance-service:1.0 .
```

Загрузить image в kind:

```powershell
kind load docker-image predictive-maintenance-service:1.0
```

Применить манифесты:

```powershell
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

Дождаться rollout:

```powershell
kubectl rollout status deployment/predictive-maintenance-api
```

Проверить pod'ы:

```powershell
kubectl get pods
```

Port-forward:

```powershell
kubectl port-forward service/predictive-maintenance-api 8000:80
```

После этого predict доступен локально:

```text
http://localhost:8000/v1/predict
```

## Отчёт

Отчёт и скриншоты находятся здесь:

```text
reports/hw1/REPORT.md
```

В папке отчёта лежат скриншоты:

- `pytest.jpg`
- `database_select.jpg`
- `k9s_with_2pods.jpg`
- `post-log_in_k9s.jpg`
- `predict_from_port-forward.jpg`
