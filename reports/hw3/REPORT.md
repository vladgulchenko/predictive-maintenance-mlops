# Predictive Maintenance MLOps HW3 Report

Отчет по ДЗ 3: модель из MLflow Registry в своем kind-кластере, деплой через
self-hosted runner, версии данных в DVC и автомасштабирование HPA.

Рабочая модель:

- сервис: `predictive-maintenance-api`;
- host сервиса: `pred-main.localhost`;
- MLflow UI: `mlflow.localhost`;
- модель в реестре: `predictive-maintenance`;
- production alias: `champion`.

## Скриншоты

Скриншоты лежат рядом с отчетом в `reports/hw3/`. В отчете подключены следующие файлы:

| Файл | Куда вставляется | Что должно быть видно |
| --- | --- | --- |
| `2.1-platform.png` | 2.1 Platform | `kubectl get pods,ingress -A`, pod'ы `Running`, Ingress hosts `pred-main.localhost` и `mlflow.localhost`. |
| `mlflow-model-registry.png` | 2.2 Training | Registry model `predictive-maintenance`, версии 1-3, aliases `challenger` и `champion`. |
| `2.3-before.png` | 2.3 Rollback | `/health` до отката: `predictive-maintenance:v3@champion`. |
| `2.3-time-measuring.png` | 2.3 Rollback | Команда `Measure-Command` и `Rollback seconds: 29.2054069`. |
| `2.3-after.png` | 2.3 Rollback | `/health` после отката: `predictive-maintenance:v2@champion`. |
| `deploy-jobe.png` | 2.4 CI/CD | Зеленый GitHub Actions run `tests -> build -> deploy`, runner name в логах deploy. |
| `github-runner.png` | 2.4 CI/CD | GitHub Settings -> Actions -> Runners, self-hosted runner с labels `kind`. |
| `dvc-push.png` | 2.5 DVC | `uv run dvc push data/raw/ai4i2020.csv.dvc`, результат `1 file pushed`. |
| `dvc-diff.png` | 2.5 DVC | `uv run dvc diff HEAD~1 HEAD`, `Modified: data/raw/ai4i2020.csv`. |
| `dvc_pull.png` | 2.5 DVC | Чистый клон, `dvc pull`, `1 file fetched and 1 file added`. |
| `model_first_md5.png` | 2.5 DVC | MLflow run на первой версии данных, `data_md5=f0adaa...`. |
| `model_second_md5.png` | 2.5 DVC | MLflow run на второй версии данных, `data_md5=5d9ee...`. |
| `hpa-w.png` | 2.6 HPA | `kubectl get hpa ... -w`, рост реплик `2 -> 4 -> 6`. |
| `hpa-k9s.png` | 2.6 HPA | k9s после нагрузки: API pod'ы еще на максимуме, CPU уже успокоился. |
| `hpa-describe.png` | 2.6 HPA | `kubectl describe hpa`, события `SuccessfulRescale`. |
| `locust-metrics.png` | 2.6 HPA | Locust percentiles, p95 `5200 ms`. |
| Скриншоты red runs | 2.7 Red Runs | Добавляются после отдельных красных прогонов. |

## Чеклист

| Пункт | Статус / артефакт |
| --- | --- |
| 2.1 Платформа в кластере | `kubectl get pods,ingress -A`: Postgres, 2 API pod'а, MLflow, Traefik и системные pod'ы `Running`; Ingress hosts: `pred-main.localhost`, `mlflow.localhost`. |
| 2.1 MLflow UI | Скрин MLflow на `http://mlflow.localhost` в режиме `Model training`. |
| 2.2 Обучение и gate | `src/app/train.py`: PR-AUC gate, `MIN_GAIN=0.005`, `metadata.json`, `confusion_matrix.json`, `data_md5`, регистрация модели через `registered_model_name`. |
| 2.2 Model Registry | Скрин модели `predictive-maintenance`: версии 1, 2, 3; у версии 3 aliases `challenger`, `champion`. |
| 2.3 Загрузка модели по alias | `/health` показывает `predictive-maintenance:v3@champion`; после отката alias - `predictive-maintenance:v2@champion`. |
| 2.3 Откат модели | `kubectl rollout restart deploy/predictive-maintenance-api`; время от клика в UI до ответа старой версии: `29.2054069` сек. |
| 2.4 CI/CD в свой кластер | Зеленый deploy run: [`37232524231`](https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/37232524231); jobs `tests -> build -> deploy`; deploy job идет на `[self-hosted, kind]`, в логе виден runner name. |
| 2.4 Smoke через Ingress | Smoke проверяет `/health`, `/ready`, `POST /v1/predict`, осмысленный `score` и строку в Postgres по тому же `request_id`. |
| 2.5 DVC | `data/raw/ai4i2020.csv.dvc` в репозитории, CSV исключен через `data/raw/.gitignore`, remote `local` указывает на `../../dvc-storage`. |
| 2.5 DVC v2 | Вторая версия: удалены 19 строк с `RNF=1`, добавлена колонка `Temperature delta [K]`. |
| 2.5 DVC push/diff/pull | `dvc push`: `1 file pushed`; `dvc diff HEAD~1 HEAD`: `Modified: data/raw/ai4i2020.csv`; clean clone `dvc pull`: `1 file fetched and 1 file added`. |
| 2.5 MLflow data_md5 | В MLflow есть прогоны с `data_md5=f0adaa9c5e25366c6df1cc2684479871` и `data_md5=5d9ee05b71518e3e7e71e6e60c7da425`. |
| 2.6 HPA | `k8s/hpa.yaml`: min 2, max 6, target CPU 60%; `metrics-server` установлен с `--kubelet-insecure-tls`. |
| 2.6 Locust/HPA | HPA вырос `2 -> 4 -> 6`, затем вернулся к 2; `kubectl describe hpa` показывает `SuccessfulRescale`. |
| 2.7 Красные прогоны | План отдельного блока: alias отсутствует, неверный `KIND_CLUSTER`, несовпадающий Ingress host. |

## 2.1 Platform

Кластер создан через `platform/kind-config.yaml` с пробросом порта 80. Входной трафик принимает
Traefik, маршрутизация сделана через Ingress:

- `mlflow.localhost` -> сервис MLflow в namespace `mlops`;
- `pred-main.localhost` -> FastAPI service `predictive-maintenance-api`.

Проверочный вывод:

```text
kubectl get pods,ingress -A

default      pod/postgres-797c8f4c74-p2fpz                    1/1 Running
default      pod/predictive-maintenance-api-677586bbd5-jqmx6  1/1 Running
default      pod/predictive-maintenance-api-677586bbd5-rrs5t  1/1 Running
mlops        pod/mlflow-9f98c4469-4sgvt                       1/1 Running
traefik      pod/traefik-6d88bc478f-js67g                     1/1 Running

default      ingress.networking.k8s.io/predictive-maintenance-api  traefik  pred-main.localhost  80
mlops        ingress.networking.k8s.io/mlflow                      traefik  mlflow.localhost     80
```

![kubectl get pods,ingress -A](2.1-platform.png)

MLflow был открыт по `http://mlflow.localhost`; UI доступен в режиме `Model training`.

## 2.2 Training, Registry And Gate

Обучение вынесено в `src/app/train.py`. Скрипт:

- читает датасет `data/raw/ai4i2020.csv`;
- считает `data_md5`;
- обучает `RandomForestClassifier`;
- логирует параметры и метрики в MLflow;
- сохраняет `metadata.json`;
- логирует `confusion_matrix.json` как дополнительный артефакт;
- регистрирует модель `predictive-maintenance`;
- каждой новой версии ставит alias `challenger`;
- ставит alias `champion`, если PR-AUC лучше текущего champion минимум на `MIN_GAIN=0.005`.

Gate metric выбран как PR-AUC, потому что класс отказа редкий: в исходном AI4I датасете отказов
существенно меньше, чем нормальных наблюдений. ROC-AUC на таком классе может выглядеть слишком
оптимистично, а PR-AUC лучше показывает качество именно на положительном редком классе. Запас
`MIN_GAIN=0.005` нужен, чтобы не перевешивать `champion` из-за микроскопического случайного улучшения.

Три запуска gate:

| Version | Aliases сейчас | PR-AUC | Решение gate | Run ID | Params |
| --- | --- | ---: | --- | --- | --- |
| 1 | - | 0.4950 | Первый запуск, `champion` еще не было -> `promoted=true` | `d007f5a76e8a42f0852561a73cd8d9a4` | `n_estimators=50`, `max_depth=6`, `min_samples_leaf=5` |
| 2 | - | 0.2937 | Хуже Version 1 -> `promoted=false` | `055c69fbc97f443f833f638e6efccb56` | `n_estimators=5`, `max_depth=2`, `min_samples_leaf=30` |
| 3 | `challenger`, `champion` | 0.7543 | Лучше Version 1 -> `promoted=true` | `7ba9ccf1a36042228ea5adc8deeaff1c` | `n_estimators=300`, `max_depth=None`, `min_samples_leaf=2` |

Скрин Model Registry показывает модель `predictive-maintenance`, версии 1-3 и aliases у версии 3:
`challenger`, `champion`.

![MLflow registry versions](mlflow-model-registry.png)

## 2.3 Service By Alias And Rollback

В Kubernetes сервис получает конфиг:

```yaml
MODEL_NAME: "predictive-maintenance"
MODEL_ALIAS: "champion"
MLFLOW_TRACKING_URI: "http://mlflow.mlops:5000"
```

При наличии `MODEL_NAME` сервис на старте загружает модель из MLflow Registry:

```text
models:/predictive-maintenance@champion
```

Для CI и локальных тестов без MLflow оставлен fallback: если `MODEL_NAME` не задан, сервис грузит локальный
bundle из `artifacts/predictive_maintenance_pipeline.joblib`.

До отката `/health` показывал:

```json
{
  "status": "ok",
  "model_version": "predictive-maintenance:v3@champion"
}
```

![health before rollback](2.3-before.png)

После перевешивания alias `champion` в MLflow UI на прошлую версию и рестарта pod'ов:

```powershell
$elapsed = Measure-Command {
  kubectl rollout restart deploy/predictive-maintenance-api
  kubectl rollout status deploy/predictive-maintenance-api
  curl http://pred-main.localhost/health
}
"Rollback seconds: $($elapsed.TotalSeconds)"
```

Результат:

```text
Rollback seconds: 29.2054069
```

![rollback seconds](2.3-time-measuring.png)

После отката `/health` показывал:

```json
{
  "status": "ok",
  "model_version": "predictive-maintenance:v2@champion"
}
```

![health after rollback](2.3-after.png)

## 2.4 CI/CD To Local Kind

Workflow `.github/workflows/ci.yaml` состоит из трех jobs:

- `tests`: GitHub-hosted runner, PostgreSQL service, `ruff`, `pytest`;
- `build`: GitHub-hosted runner, build/push image в GHCR;
- `deploy`: self-hosted runner с labels `[self-hosted, kind]`.

Deploy запускается только вручную на `main`:

```yaml
if: github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'
```

Runner запущен в Docker и подключен к сети `kind`. Это нужно, чтобы job могла обратиться к kind control-plane
по internal Docker network и выполнить:

```bash
kind export kubeconfig --name "$KIND_CLUSTER" --internal
```

Secret создается идемпотентно:

```bash
kubectl create secret generic pred-main-secrets \
  --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://postgres:$DB_PASSWORD@postgres:5432/predictive_maintenance" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Smoke идет через Ingress:

```bash
U="http://$KIND_CLUSTER-control-plane:30080"
H="Host: pred-main.localhost"
```

Smoke проверяет:

- `/health` содержит registry version вида `predictive-maintenance:v...@champion`;
- `/ready` отвечает успешно;
- `POST /v1/predict` возвращает осмысленный `score`;
- в Postgres есть ровно одна строка с `request_id` из ответа predict.

Зеленый deploy run: [`37232524231`](https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/37232524231).
Скрин deploy job показывает runner:

```text
Runner name: 5d1f44dd7388
```

![GitHub Actions green deploy](deploy-jobe.png)

Скрин GitHub Settings -> Actions -> Runners показывает self-hosted runner с labels `self-hosted`, `Linux`,
`X64`, `kind`:

![GitHub self-hosted runner](github-runner.png)

После сдачи runner нужно выключить:

```powershell
docker rm -f gh-runner
```

и удалить запись runner в GitHub Settings -> Actions -> Runners.

## 2.5 DVC Data Versions

DVC подключен с локальным remote рядом с репозиторием:

```ini
[core]
    remote = local
['remote "local"']
    url = ../../dvc-storage
```

Путь выглядит как `../../dvc-storage`, потому что DVC считает его от папки `.dvc`.

Файл `data/raw/ai4i2020.csv.dvc` в текущей версии:

```yaml
outs:
- md5: 5d9ee05b71518e3e7e71e6e60c7da425
  size: 567521
  hash: md5
  path: ai4i2020.csv
```

CSV больше не хранится в Git; он добавлен в `data/raw/.gitignore`.

### Версия 1

Исходная версия датасета:

```yaml
md5: f0adaa9c5e25366c6df1cc2684479871
size: 522048
```

### Версия 2

Во второй версии:

- удалены 19 строк с `RNF=1` как случайные шумовые отказы;
- добавлена колонка `Temperature delta [K] = Process temperature [K] - Air temperature [K]`;
- строк стало `9981` вместо `10000`;
- размер стал `567521`.

Push второй версии:

```text
uv run dvc push data/raw/ai4i2020.csv.dvc
Collecting
Pushing
1 file pushed
```

![DVC push](dvc-push.png)

Diff между версиями:

```text
uv run dvc diff HEAD~1 HEAD
Modified:
    data\raw\ai4i2020.csv

files summary: 1 modified
```

![DVC diff](dvc-diff.png)

Проверка восстановления в чистом клоне:

```text
uv run dvc pull data/raw/ai4i2020.csv.dvc
A       data\raw\ai4i2020.csv
1 file fetched and 1 file added
```

![DVC pull in clean clone](dvc_pull.png)

MLflow runs с разными версиями данных:

| Run | Registered model version | data_md5 | Комментарий |
| --- | --- | --- | --- |
| `hilarious-boar-352` | v3 | `f0adaa9c5e25366c6df1cc2684479871` | Обучение на v1 датасета. |
| `ambitious-mule-264` | v4 | `5d9ee05b71518e3e7e71e6e60c7da425` | Обучение на v2 датасета. |

![MLflow run with data v1](model_first_md5.png)

![MLflow run with data v2](model_second_md5.png)

CSV не копируется в Docker image. Сервису полный датасет в production не нужен: модель приходит из MLflow Registry.

## 2.6 HPA And Locust

Для HPA у deployment заданы resource requests:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: "1"
    memory: 512Mi
```

`metrics-server` установлен с values:

```yaml
args:
  - --kubelet-insecure-tls
```

HPA manifest:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: predictive-maintenance-hpa
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: predictive-maintenance-api}
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target: {type: Utilization, averageUtilization: 60}
```

Нагрузка запускалась через Traefik/Ingress:

```powershell
uv run locust -f load/locustfile.py --headless -u 60 -r 20 -t 4m --host http://pred-main.localhost
```

Locust отправляет `POST /v1/predict`.

![k9s after HPA scale-up](hpa-k9s.png)

HPA watch показал рост:

```text
TARGETS       MINPODS MAXPODS REPLICAS
cpu: 53%/60%  2       6       2
cpu: 1000%/60% 2      6       2
cpu: 568%/60% 2       6       4
cpu: 294%/60% 2       6       6
...
cpu: 4%/60%   2       6       6
```

![HPA watch](hpa-w.png)

`kubectl describe hpa`:

```text
Normal  SuccessfulRescale  New size: 4; reason: cpu resource utilization (percentage of request) above target
Normal  SuccessfulRescale  New size: 6; reason: cpu resource utilization (percentage of request) above target
Normal  SuccessfulRescale  New size: 2; reason: All metrics below target
```

![HPA describe](hpa-describe.png)

После остановки Locust HPA вернул deployment к двум репликам. `kubectl top pods` после замера:

```text
predictive-maintenance-api-695c8f68d9-5pvg2   4m   231Mi
predictive-maintenance-api-695c8f68d9-xkbzz   4m   229Mi
```

Requests оставлены без изменений: memory request `256Mi` близок к фактическому потреблению `229-231Mi`,
а cpu request `100m` позволяет HPA быстро реагировать на рост CPU при Locust-нагрузке.

Таблица подтвержденного Locust-прогона:

| Run | Users | Max replicas | p95 | CPU на pod | Requests before | Requests after |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 1 | 60 | 6 | 5200 ms | До `1000m` под нагрузкой, после нагрузки `4m`; memory после нагрузки `229-231Mi` | `100m / 256Mi` | `100m / 256Mi` |

![Locust percentiles](locust-metrics.png)

В ТЗ запрошена таблица из трех прогонов. На текущий момент скриншотом подтвержден один прогон; еще две строки
нужно добавить после двух дополнительных измерений, чтобы не подставлять в отчет вымышленные p95 и CPU.

## 2.7 Red Runs

Этот блок еще нужно выполнить отдельными контролируемыми прогонами:

| Поломка | Красный run | Зеленый run | Диагноз |
| --- | --- | --- | --- |
| Alias модели отсутствует (`MODEL_ALIAS=prod`) | [red deploy job](https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/37340103056/job/111865257104) | [green deploy run](https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/37341857901) | API pod уходит в `CrashLoopBackOff`, deploy падает на rollout/smoke, потому что сервис не может загрузить модель по отсутствующему alias из MLflow Registry. |
| Runner не видит кластер (`KIND_CLUSTER` неверный) | [red deploy job](https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/37345166633/job/111882302288) | [green deploy job](https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/37346123310/job/111885491806) | Step `kind, kubectl and cluster access` падает на `kind export kubeconfig`, потому что runner ищет kind-кластер с неправильным именем. |
| Ingress мимо (`host` в ingress не совпадает со smoke) | после прогона | после фикса | Ожидаемо: deploy и rollout проходят, но smoke падает на `curl --fail`, потому что Traefik не находит rule для `Host: pred-main.localhost`. |

После отдельных красных прогонов сюда добавляются ссылки на красный и зеленый GitHub Actions run для каждой
поломки.

В красном прогоне с отсутствующим alias новые pod'ы API не смогли загрузить модель из MLflow Registry и ушли в
`CrashLoopBackOff`. После возврата `MODEL_ALIAS=champion` rollout и smoke снова прошли успешно.

В красном прогоне с неверным `KIND_CLUSTER` self-hosted runner был жив, но искал несуществующий kind-кластер.
Из-за этого deploy упал до применения Kubernetes-манифестов, на шаге `kind export kubeconfig`; после возврата
`KIND_CLUSTER=pred-main-mlops` runner снова получил kubeconfig и deploy прошел.

## Eight Questions

### 1. Почему `tests` и `build` идут в облаке GitHub, а `deploy` не может?

`tests` и `build` не требуют доступа к локальному kind-кластеру: GitHub-hosted runner может поднять service
Postgres, запустить pytest, собрать Docker image и отправить его в GHCR. `deploy` должен выполнить `kubectl`
против kind-кластера на моей машине, который находится за NAT и не доступен снаружи. Поэтому deploy выполняет
self-hosted runner, который запущен локально рядом с Docker/kind.

Другие варианты доставки: открыть Kubernetes API наружу, использовать VPN/Tailscale, поставить pull-based CD
внутри кластера вроде Argo CD/Flux или держать runner на отдельной VM в той же сети. Для домашки выбран
self-hosted runner, потому что он проще всего связывает GitHub Actions с локальным kind без публикации кластера
в интернет.

### 2. Зачем runner запущен с `--network kind`, Docker socket и `--group-add 0`?

`--network kind` подключает runner-контейнер к Docker-сети kind, чтобы `kind export kubeconfig --internal`
создал рабочий kubeconfig до control-plane по внутренней сети. Docker socket нужен, чтобы runner мог выполнять
`docker pull` и `kind load docker-image`, то есть управлять Docker daemon на хосте. `--group-add 0` нужен для
доступа к `/var/run/docker.sock`: без прав на socket команды Docker внутри runner падают с permission denied или
не могут подключиться к Docker API.

Без `--network kind` runner может зарегистрироваться в GitHub, но не увидеть кластер. Без socket не работают
`docker pull` и `kind load`. Без `--group-add 0` socket может быть смонтирован, но недоступен процессу внутри
контейнера.

### 3. Почему secret создается через `--dry-run=client -o yaml | kubectl apply`?

Обычный `kubectl create secret ...` не идемпотентен: на втором деплое он упадет с ошибкой `AlreadyExists`.
Схема `--dry-run=client -o yaml | kubectl apply -f -` сначала генерирует YAML, а потом применяет его как
декларативный объект. Поэтому первый деплой создает secret, а последующие обновляют его без падения pipeline.

### 4. Чем `challenger` отличается от `champion`? Почему сервис просит alias, а не номер версии?

`challenger` - последняя зарегистрированная версия-кандидат. Она может быть хуже текущей production-модели.
`champion` - версия, которую gate пропустил как production-кандидата и которую должен брать сервис.

Сервис просит alias `champion`, а не конкретный номер версии, чтобы модель можно было откатить без пересборки
образа и изменения кода. Откат модели через alias меняет, какая модель загрузится при следующем restart pod'ов.
Откат кода через `rollout undo` возвращает старый ReplicaSet/старый Docker image. Это разные уровни: alias -
данные/модель, rollout undo - код приложения.

### 5. Что будет, если задеплоить сервис в кластер, где еще никто не обучил модель?

Если в MLflow Registry нет модели `predictive-maintenance@champion`, API pod упадет на старте при загрузке
модели из registry. В k9s это будет видно как `CrashLoopBackOff` или rollout, который не завершается. В CI это
проявится как timeout на `kubectl rollout status deploy/predictive-maintenance-api`, а diagnostics/logs покажут
ошибку загрузки registered model или alias.

### 6. Проследите запрос от браузера до pod'а MLflow.

Браузер идет на `http://mlflow.localhost` по порту 80. Этот порт проброшен в kind при создании кластера через
`kind-config.yaml`, поэтому трафик попадает в control-plane container и далее в Traefik. Traefik читает Ingress
с host `mlflow.localhost` и маршрутизирует запрос в Service `mlflow` в namespace `mlops`, а дальше на pod MLflow
порт 5000.

`--allowed-hosts` нужен MLflow, чтобы разрешить Host headers вроде `mlflow.localhost` и `mlflow.mlops`.
`--cors-allowed-origins=http://mlflow.localhost` нужен UI/API, чтобы браузер не блокировал cross-origin запросы.
Порт 80 задается при создании kind-кластера, потому что host port mapping для kind node container нельзя нормально
добавить постфактум к уже созданному контейнеру.

### 7. Сколько реплик HPA должен был выставить?

Формула HPA:

```text
desiredReplicas = ceil(currentReplicas * currentMetric / desiredMetric)
```

При target `60%` и наблюдаемом `1000%` при двух pod'ах:

```text
ceil(2 * 1000 / 60) = ceil(33.33) = 34
```

Но в `hpa.yaml` задан `maxReplicas: 6`, поэтому фактически HPA уперся в потолок и выставил 6 pod'ов. Это
совпадает с наблюдением: сначала реплики выросли до 4, затем до 6. Вниз реплики уходили дольше, потому что у HPA
есть stabilization window: он быстро реагирует на рост нагрузки, но не уменьшает реплики на каждом коротком
провале метрики.

### 8. Что лежит в Git, а что в DVC storage? Как восстановить данные для версии N?

В Git лежат маленькие метафайлы: `data/raw/ai4i2020.csv.dvc`, `data/raw/.gitignore`, `.dvc/config`,
`.dvcignore`, код и манифесты. Сам CSV в Git не лежит: он игнорируется и хранится как объект по md5 в DVC remote
`../../dvc-storage`.

Чтобы восстановить данные для конкретной версии модели N:

1. В MLflow открыть run, из которого зарегистрирована версия N.
2. Посмотреть параметр `data_md5`.
3. Найти коммит/`.dvc`-файл, где `md5` совпадает с этим `data_md5`.
4. Сделать checkout нужного `.dvc`-файла или нужного коммита.
5. Выполнить `uv run dvc pull data/raw/ai4i2020.csv.dvc`.
6. DVC восстановит `data/raw/ai4i2020.csv` ровно из объекта с нужным md5.

## Problem Log

- При первом запуске self-hosted runner команда внутри контейнера была `config.sh`, а не `./config.sh`.
  Контейнер крутился, но не регистрировался в GitHub. Диагноз: `bash: config.sh: command not found`.
  Исправление: запускать `./config.sh` и `./run.sh`.
- При запуске runner из Git Bash сломался mount Docker socket. Deploy упал на `kind export kubeconfig`, потому что
  внутри runner не было `/var/run/docker.sock`. Исправление: пересоздать runner из PowerShell и проверить
  `docker exec gh-runner docker ps`.
- Один deploy упал на `password authentication failed` к Postgres. Причина: старый Postgres deployment был
  инициализирован в старом состоянии, а актуальный Kubernetes Secret уже был другим источником правды.
  Исправление для учебного kind: удалить deployments Postgres/API и дать workflow пересоздать их из актуального
  secret.
- В clean clone DVC не видел данные, потому что путь `../../dvc-storage` из папки `check/predictive-maintenance-mlops`
  указывал на `check/dvc-storage`, а реальный remote лежал в `FINAL_project/dvc-storage`. Исправление для проверки:
  локально переопределить remote через `.dvc/config.local` или клонировать репозиторий рядом с `dvc-storage`.
- В начале HPA мог показывать `<unknown>`, пока metrics-server не собрал метрики. Это ожидаемо для kind; после
  прогрева `kubectl top pods` и HPA начали показывать CPU.
