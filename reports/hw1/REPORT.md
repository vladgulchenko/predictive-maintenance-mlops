# Predictive Maintenance MLOps Report

Отчет по ДЗ 1: FastAPI ML-сервис для предсказания отказа оборудования,
логирование предсказаний в PostgreSQL, запуск через Docker Compose и Kubernetes.

## Pytest

```text
uv run pytest tests -q
```

![pytest](pytest.jpg)

## PostgreSQL Logs

Prediction-запросы сохраняются в таблицу `predictions`. В лог пишутся
`request_id`, timestamp, версия модели, входные признаки, score, итоговое
решение модели, latency и HTTP status code успешного ответа.

```sql
SELECT
    request_id,
    ts,
    status_code,
    model_version,
    features,
    score,
    prediction,
    latency_ms
FROM predictions
ORDER BY ts DESC
LIMIT 5;
```

![postgres-select](database_select.jpg)

## Kubernetes Pods

```text
kubectl get pods
```

![k9s-with-2pods](k9s_with_2pods.jpg)

## Kubernetes API Logs

```text
POST /v1/predict HTTP/1.1 200 OK
```

![post-log-in-k9s](post-log_in_k9s.jpg)

## Port Forward Predict

```powershell
kubectl port-forward service/predictive-maintenance-api 8000:80
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

![predict-from-port-forward](predict_from_port-forward.jpg)

## Исправления После Ревью

1. Входной Pydantic-контракт использовал API-имена полей, а обученный pipeline
   ожидал оригинальные названия колонок из датасета AI4I: `Air temperature [K]`,
   `Torque [Nm]` и так далее. Из-за этого числовые признаки после `reindex`
   превращались в `NaN`, и модель фактически предсказывала только по `Type`.
   Фикс: в `app.py` добавлен явный mapping из API-полей в признаки модели.

2. Раньше модель сохранялась через `joblib` отдельно от паспорта модели
   `metadata.json`. При переобучении можно было обновить модель и забыть
   обновить metadata, из-за чего версия, threshold или список признаков могли
   разъехаться. Фикс: теперь `.joblib` хранит bundle с `pipeline` и `metadata`.
   Отдельный `metadata.json` оставлен как читаемый паспорт модели для человека.

3. В `/ready` была опечатка: `getattr(app.state, "pipeline", "None")`.
   Из-за строкового дефолта `"None"` ручка могла вернуть `200`, даже если
   pipeline не был загружен. Фикс: дефолт заменен на настоящий `None`.

4. Границы в Pydantic-схеме были слишком широкими, поэтому сервис принимал
   сильно out-of-distribution значения, например температуру `5000K`.
   Фикс: добавлены доменные ограничения с небольшим запасом, чтобы отсекать
   явный мусор, но не отклонять редкие допустимые аномалии слишком агрессивно.

5. В таблице `predictions` не было `status_code`. Фикс: переписан DDL таблицы
   и `INSERT` в `db.py`, при успешном predict сохраняется `200`. Все коды
   ответа не логируются в этой таблице, потому что `predictions` предназначена
   для успешных ML-предсказаний; ошибки валидации и системные ошибки требуют
   отдельной таблицы request logs или middleware.

6. В Dockerfile добавлен `uv sync --frozen`, чтобы Docker-сборка использовала
   зафиксированный `uv.lock` и не пересчитывала зависимости.

7. Добавлены `.dockerignore` и `.python-version`. После изменения Dockerfile
   образ нужно пересобрать; если у проверяющего остался старый volume Postgres,
   его нужно удалить командой `docker compose down -v`, чтобы таблица создалась
   заново по актуальному DDL.

## Журнал Проблем

- VS Code долго подключался к Jupyter kernel. Решение: выбран интерпретатор проекта `.venv`.
- Notebook сохранял outputs и execution counts. Решение: добавлен pre-commit hook для очистки `.ipynb`.
- FastAPI падал на старте из-за lifespan context manager. Решение: lifespan переведен на async context manager.
- PostgreSQL не сохранял prediction logs из-за ошибки `cannot adapt type 'dict'`. Решение: `features` сохраняются в `jsonb` через `Json(features)`.
