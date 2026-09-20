# Report

## Pytest

```text
uv run pytest
```

![pytest](pytest.jpg)

## PostgreSQL Logs

```sql
SELECT
    request_id,
    ts,
    model_version,
    score,
    prediction,
    latency_ms
FROM predictions
ORDER BY ts DESC
LIMIT 5;
```

![postgres-select](database_select.jpg)

## Docker Compose

```text
docker compose up --build
```

TODO: add screenshot.

## Swagger Predict

```text
POST /v1/predict
```

TODO: add screenshot.

## Kubernetes Pods

```text
kubectl get pods
```

TODO: add screenshot.

## K9s

TODO: add screenshot.

## Port Forward Predict

```powershell
kubectl port-forward service/<service-name> 8000:8000
```

```powershell
$body = @{
  Type = "M"
  air_temperature_k = 298.1
  process_temperature_k = 308.6
  rotational_speed_rpm = 1551
  torque_nm = 42.8
  tool_wear_min = 0
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8000/v1/predict" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

TODO: add screenshot.

## Problem Log

- VS Code Jupyter kernel did not connect: fixed by selecting the project `.venv`.
- Notebook outputs polluted Git diffs: added pre-commit output stripping.
- FastAPI lifespan startup failed: fixed by using an async context manager.
- PostgreSQL logging failed with `cannot adapt type 'dict'`: fixed by wrapping features with `Json(features)`.
