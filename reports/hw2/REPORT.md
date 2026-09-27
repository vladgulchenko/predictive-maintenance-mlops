# Predictive Maintenance MLOps HW2 Report

Отчет по ДЗ 2: CI/CD pipeline для ML-сервиса из ДЗ 1. Pipeline включает
`tests`, `build`, `deploy`, интеграционные тесты с PostgreSQL, публикацию image
в GHCR и деплой в kind-кластер.

Важно: по условию ДЗ финальный отчет должен лежать в корне репозитория как
`REPORT.md`. Этот файл ведется как рабочая версия отчета для ДЗ 2.

## Чекпойнты

| Пункт задания | Ссылка / статус |
| --- | --- |
| Базовый CI: `ruff` и `pytest` | Зеленый прогон после фикса ruff: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36270278965 |
| Первый красный PR-прогон | Ruff упал на notebook/scripts/config: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36269475049 |
| Интеграционные тесты с PostgreSQL | `tests` job поднимает `postgres:16`, `DATABASE_URL` передается в приложение, тесты проверяют `status_code=200` и `status_code=422` |
| Build image в GHCR | Package: https://github.com/vladgulchenko/predictive-maintenance-mlops/pkgs/container/predictive-maintenance-mlops |
| Deploy в kind | `deploy` job применяет `k8s/postgres.yaml`, `k8s/configmap.yaml`, `k8s/deployment.yaml`, `k8s/service.yaml`, затем выполняет smoke |
| Smoke predict | Через `kubectl port-forward svc/predictive-maintenance-api 8080:80`, `curl /health`, `curl /ready`, `POST /v1/predict`, проверка `0 <= score <= 1` |
| Проверка лога после smoke | По `request_id` из `pred.json` выполняется `SELECT count(*) FROM predictions WHERE request_id = ...` |

## Красные Прогоны

### PR: Ruff Failure

- Красный прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36269475049
- Причина: `ruff check .` проверял весь репозиторий и нашел проблемы в notebook,
  `scripts/strip_notebook_outputs.py` и `src/app/config.py`.
- Симптомы: job `tests`, step `uv run ruff check .`, ошибки `I001`, `UP017`,
  `RUF046`, `SIM102`.
- Фикс: форматирование импортов, исправления ruff-предупреждений и повторный
  зеленый прогон.
- Зеленый прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36270278965

### ConfigMap: Wrong Model Path

- Красный прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36338972492/job/108675398337
- Зеленый прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36340102111
- Что ломалось: в `ConfigMap` был указан несуществующий путь к модели.
- Где упало: deploy job, этап подъема pod'ов приложения / rollout.
- Как диагностировалось: после падения отработал блок `диагностика` из
  `ci.yaml`; в логах приложения был traceback из `lifespan`, где `joblib.load`
  пытался открыть модель по несуществующему пути.
- Фикс: вернуть корректный `MODEL_PATH`:
  `artifacts/predictive_maintenance_pipeline.joblib`.

### Secret: Broken Secret Name

- Красный прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36341179362
- Зеленый прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36342259524
- Что ломалось: имя Kubernetes Secret, создаваемого pipeline, не совпало с
  именем, которое ожидают `secretRef` в манифестах.
- Особенность конкретного прогона: сломанный secret был назван с недопустимым
 /неподходящим именованием, из-за чего Kubernetes также ругался на имя.
- Как диагностировалось: deploy job упал, затем diagnostics step вывел состояние
  pod'ов, describe deployment и события кластера. При mismatch secretRef нужно
  смотреть ошибки вида `secret ... not found` / `CreateContainerConfigError`.
- Фикс: привести имя создаваемого секрета и `secretRef` к одному значению:
  `pred-main-secrets`.

### Resources: Impossible Memory Request

- Красный прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36343313370
- Зеленый прогон: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36344243020
- Что ломалось: в resources был выставлен нереалистичный memory request.
- Где упало: deploy job на rollout приложения.
- Как диагностировалось: diagnostics step показал pod/deployment events; в
  describe deployment/pod было видно, что scheduler не может разместить pod из-за
  запрошенной памяти.
- Фикс: вернуть адекватный request памяти для API pod.

## Ответы На Вопросы

### 1. Сколько секунд шел job build в первом прогоне и сколько во втором? Какой слой Dockerfile взят из cache и почему?

Первый `build` job шел 54 секунды, второй - 15 секунд. Ускорение появилось из-за
Docker/GitHub Actions cache: повторно использовались слои установки зависимостей
через `uv`, прежде всего `RUN uv sync --frozen --no-dev --no-install-project` и
`RUN uv sync --frozen --no-dev`.

Прогоны:

- Первый build job: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36315372992/job/108609042609
- Второй build job: https://github.com/vladgulchenko/predictive-maintenance-mlops/actions/runs/36330022531/job/108650159308

Эти слои кешируются, потому что перед первым `uv sync` в image копируются только
`pyproject.toml` и `uv.lock`. Пока lock-файл и зависимости не меняются, Docker
может переиспользовать уже собранный слой с `.venv`. `COPY artifacts/ artifacts/`
стоит после `uv sync`, поэтому слой с модельными артефактами не заставляет заново
ставить зависимости.

### 2. В логе deploy видны pod'ы в ImagePullBackOff, а прогон зеленый. Откуда эти pod'ы и почему это не ошибка?

В моих deploy runs pod'ов в `ImagePullBackOff` не было найдено ни в зеленом
deploy, ни в зафейленных прогонах. Это ожидаемо для текущей схемы pipeline:
каждый run поднимает новый kind-кластер через `helm/kind-action`, затем image
явно скачивается из GHCR и загружается в kind через `kind load docker-image`.

`ImagePullBackOff` был бы ожидаем, если Deployment ссылался бы на image, который
кластер не может скачать или найти: например, tag не существует, нет доступа к
registry или image не был загружен в kind. В моей реализации сломанные deploy
прогоны падали по другим причинам: неверный `MODEL_PATH`, проблема с Secret и
нереалистичные resource requests.

Поэтому для моего зеленого прогона отсутствие `ImagePullBackOff` в логах не
является проблемой: rollout и smoke проходят, а diagnostics step запускается
только при failure.

### 3. Какой путь проходит пароль базы от GitHub settings до переменной окружения в pod? Почему его нельзя положить в ConfigMap?

Сначала пароль задается в настройках GitHub repository secrets как `DB_PASSWORD`.
GitHub хранит его в зашифрованном виде и подставляет только во время выполнения
workflow. В deploy job он попадает в переменную окружения step:

```yaml
env:
  DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
```

После этого команда `kubectl create secret generic pred-main-secrets` создает
Kubernetes Secret внутри kind-кластера. В этот Secret кладутся два значения:
`POSTGRES_PASSWORD` для старта Postgres и `DATABASE_URL` для API:

```bash
--from-literal=POSTGRES_PASSWORD="$DB_PASSWORD"
--from-literal=DATABASE_URL="postgresql://postgres:$DB_PASSWORD@postgres:5432/predictive_maintenance"
```

Дальше Postgres pod получает `POSTGRES_PASSWORD` через `secretKeyRef`, а API pod
получает значения через `envFrom.secretRef`. Внутри приложения Pydantic Settings
читает только `DATABASE_URL`, потому что сервису нужен уже готовый connection
string до базы, а не отдельный пароль.

В ConfigMap пароль класть нельзя, потому что ConfigMap предназначен для
несекретной конфигурации. Его содержимое хранится как обычный объект Kubernetes и
легко читается через `kubectl get configmap ... -o yaml`. Пароли и connection
string с паролем должны лежать в Secret.

### 4. Что будет, если убрать `needs: tests` у job build?

Если убрать `needs: tests`, job `build` перестанет зависеть от успешного
прохождения тестов. Тогда при `push` в `main` сборка Docker image сможет
стартовать параллельно с `tests` или вообще независимо от результата тестов.

В плохом сценарии `ruff` или `pytest` уже падают, но image из этого же коммита
все равно собирается и публикуется в GHCR. Так как `deploy` зависит от `build`,
дальше pipeline может попытаться выкатить в kind-кластер образ, который не
прошел базовую проверку.

Для pull request в моей текущей конфигурации это отдельно ограничено строкой
`if: github.ref == 'refs/heads/main'` у `build`: на PR build не запускается.
Но для merge/push в `main` `needs: tests` нужен, чтобы сборка и деплой начинались
только после зеленых тестов.

### 5. Почему на pull request бегут только tests, а build и deploy нет? Какая строка за это отвечает?

На pull request workflow запускается, поэтому job `tests` выполняется. Но job
`build` не запускается, потому что в ней стоит условие:

```yaml
if: github.ref == 'refs/heads/main'
```

В PR `github.ref` указывает не на `refs/heads/main`, а на pull request ref,
поэтому GitHub Actions пропускает `build`. Job `deploy` завязан на `build` через
`needs: build`, поэтому если `build` не был запущен, `deploy` тоже не стартует.

Итог: на PR проверяются только быстрые и безопасные проверки (`ruff`, `pytest`),
а сборка image, push в GHCR и deploy выполняются только после попадания изменений
в `main`.

### 6. Зачем в `init()` стоит `pg_advisory_xact_lock`? Что будет без него при двух репликах и пустой базе?

В `k8s/deployment.yaml` для API указано `replicas: 2`, то есть Kubernetes
поднимает две реплики приложения. Реплики здесь - это именно два API pod'а, а не
реплики Postgres. При старте каждый API pod заходит в lifespan приложения и
вызывает `db.init()`, где выполняется DDL для создания таблицы `predictions`.

`pg_advisory_xact_lock(7001)` нужен, чтобы сериализовать эту инициализацию схемы
БД. Первый pod, который дошел до `db.init()`, берет advisory lock и выполняет
DDL. Второй pod, если стартовал одновременно, доходит до этой же строки и ждет,
пока первый pod закончит транзакцию. После выхода из `with psycopg.connect(...)`
транзакция завершается, transaction-level lock автоматически отпускается, и
второй pod продолжает работу уже с готовой схемой.

Без lock обе реплики API могут одновременно попытаться инициализировать пустую
базу. С текущим простым `CREATE TABLE IF NOT EXISTS predictions` это часто не
сломается, потому что Postgres умеет обработать такой DDL безопасно. Но как
только инициализация станет сложнее: несколько таблиц, индексы, `ALTER TABLE`,
seed-данные или ручные миграции, одновременный запуск двух `db.init()` может
привести к гонке, конфликтам DDL или частично примененной схеме.

Поэтому lock здесь нужен не потому, что Postgres "не умеет" создавать таблицу, а
как защитный механизм для старта нескольких API pod'ов. Он гарантирует, что
инициализация схемы будет выполняться одним процессом за раз.

### 7. В трех красных прогонах pod'ы застряли в трех разных статусах. Расположите эти статусы в порядке жизни pod'а.

Порядок этих ошибок соответствует тому, на каком этапе жизни pod'а происходит
поломка:

```text
Pending -> CreateContainerConfigError -> CrashLoopBackOff
```

При нереалистичных `resources` pod даже не стартует. Scheduler не может найти
node, на котором хватит запрошенной памяти, поэтому pod остается на этапе
планирования. Это самый ранний этап: контейнер еще не создан и приложение не
запускалось.

При неправильном Secret pod уже может быть создан и назначен на node, но
Kubernetes не может подготовить конфигурацию контейнера. Например, Deployment
ссылается на secretRef, которого нет, или на некорректное имя Secret. В этом
случае контейнер не стартует, потому что env-переменные из Secret не могут быть
переданы в pod.

При неправильном `MODEL_PATH` контейнер уже стартует, Python-приложение начинает
работать, но падает внутри lifespan при загрузке модели. Поэтому в диагностике
виден traceback из приложения: Kubernetes смог запустить контейнер, но процесс
внутри контейнера завершился с ошибкой, после чего pod начинает перезапускаться.

Итого: resources ломают pod до старта, Secret ломает pod на подготовке
конфигурации контейнера, а `MODEL_PATH` ломает уже работающее приложение внутри
контейнера.

## Журнал Проблем

- Первый PR-прогон упал на `ruff check .`: локально не было очевидно, что ruff
  будет проверять notebook и scripts. Причина найдена по step `uv run ruff check .`.
  Исправлено следующим коммитом.
- При локальном запуске DB integration tests подключение к `localhost:5432`
  падало с `password authentication failed`. Причина оказалась не в коде, а в
  локальном конфликте портов: на Windows одновременно слушал локальный
  `postgres.exe` и Docker Compose Postgres. Для проверки был использован
  временный Postgres на `5433`; тесты прошли.
- Для `422` оказалось недостаточно логировать внутри `/v1/predict`: Pydantic
  отсекает невалидный request до входа в handler. Решение: добавить
  `RequestValidationError` handler, который пишет строку с `status_code=422`.
- Для deploy в kind нужно было явно связать image из GHCR с Deployment:
  `kind load docker-image` только загружает image в кластер, а
  `kubectl set image ...` говорит Deployment использовать этот image.
