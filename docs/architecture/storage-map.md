# Где что хранится

Дополнение к [карте хранения](state-storage.svg). Пути и настройки соответствуют манифестам и коду репозитория; фактическое состояние развернутого кластера может отличаться при ручных изменениях.

| Сущность | Где находится | Идентификатор / восстановление |
| --- | --- | --- |
| Код, DAG, манифесты | Git; DAG после deploy также в ConfigMap `mlops/airflow-dags` | Commit SHA; повторный deploy восстанавливает конфигурацию из Git |
| Образ приложения | GHCR; копия загружается в узел kind | `sha-<commit>`; тот же образ используется для API и task pod |
| Версия датасета | DVC-указатель в Git; объекты в бакете RustFS `pred-main-dvc` | MD5; `dvc pull` работает, если объекты есть в доступном S3 |
| Физические данные RustFS | PVC `mlops/rustfs-data`, 2 Gi, mount `/data` | Сохраняются при подключении того же PVC; Git не содержит копию объектов S3 |
| Эксперименты и Registry MLflow | PVC `mlops/mlflow-data`, 2 Gi; SQLite `/mlflow/mlflow.db` | Runs, метрики, параметры, версии и aliases; переустановка сервера без БД их не восстанавливает |
| Модели и артефакты MLflow | Тот же PVC; `/mlflow/artifacts` | Модель, metadata, confusion matrix, validation failure cases; RustFS для этого не используется |
| Состояние Airflow | PVC `mlops/airflow-data`, 1 Gi; SQLite `/opt/airflow/data/airflow.db` | Метаданные запусков, задач, XCom и Variables; файловые логи этим PVC не защищены |
| Загруженная модель API | `app.state.pipeline` в памяти каждого процесса | При старте скачивается `models:/predictive-maintenance@champion`; нужна доступность MLflow |
| Журнал предсказаний | PostgreSQL, таблица `predictions` | Deployment не подключает PVC; пересоздание pod не гарантирует сохранность журнала |
| Локальные CSV и кеш DVC | Рабочая папка клона: `data/raw/ai4i2020.csv`, `.dvc/cache/` | Удаление кластера само по себе не удаляет папку клона. Локальный кеш не заменяет `dvc push` |
| Файлы validate/train | Файловая система task pod; данные и кеш после `dvc pull`, локальный bundle после обучения | Pod удаляется после выполнения; результаты для дальнейшего использования сохраняются в MLflow |
| Локальный model bundle | `artifacts/` в Git и образе; обновляется `app.train` | API использует его только при отключенном Registry-режиме. В текущем k8s config выбран MLflow |
| Dashboard и сбор метрик | YAML в Git; ConfigMap dashboard и ServiceMonitor после deploy | Конфигурация восстанавливается deploy. История метрик — отдельное runtime-состояние |
| История метрик Prometheus | Хранилище Prometheus, retention `2d` | В репозитории `storageSpec`/PVC явно не настроен. Retention не является гарантией сохранности при пересоздании; для точного поведения нужны defaults установленного Helm-чарта |
| Credentials | Локальные `.env`, `.dvc/config.local`; GitHub Secret `DB_PASSWORD`; Kubernetes Secrets | В Git не публикуются значения `.env`/локального DVC. Kubernetes Secrets пересоздаются из исходных настроек; PVC приложений не является их источником |

## Что важно не перепутать

- PVC — запрос на том. Данные лежат на подключенном хранилище, а не «в YAML PVC».
- Сохранение данных при пересоздании pod не означает сохранение при удалении самого kind-кластера или тома.
- Один commit SHA может использоваться для обучения нескольких моделей на разных версиях данных или с разными параметрами.
- `champion` — ссылка на версию в Registry. Загруженная модель в API меняется после перезагрузки процесса, не автоматически при смене alias.
- `git revert` возвращает код или указатель данных, но не SQLite MLflow, PostgreSQL и не объекты S3. `dvc checkout` восстанавливает рабочий CSV из кеша; без объекта в кеше нужен доступный remote и `dvc pull`.

## Файлы-источники

- [RustFS](../../platform/s3.yaml), [MLflow](../../platform/mlflow.yaml), [Airflow](../../platform/airflow.yaml).
- [PostgreSQL](../../k8s/postgres.yaml), [мониторинг](../../platform/monitoring-values.yaml), [kind](../../platform/kind-config.yaml).
- [Обучение](../../src/app/train.py), [загрузка модели API](../../src/app/service/app.py), [конфигурация API](../../k8s/configmap.yaml).
- [Dockerfile](../../Dockerfile), [.dockerignore](../../.dockerignore), [CI/CD](../../.github/workflows/ci.yaml).
