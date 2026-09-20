# Predictive Maintenance MLOps

## Run

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

## Test Request

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

## Tests

```powershell
uv sync
uv run pytest
```

## Report

See `reports/hw1/REPORT.md`.
