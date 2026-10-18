# Predictive Maintenance MLOps

Учебный MLOps-проект: сервис прогнозирует вероятность отказа промышленного оборудования по температуре, оборотам, крутящему моменту, износу инструмента и типу оборудования. Модель RandomForest обучается на очищенном датасете AI4I 2020 и доступна через FastAPI.

Проект объединяет версионирование данных в DVC/S3, проверку данных Pandera, реестр моделей MLflow, переобучение в Airflow и доставку приложения в Kubernetes через GitHub Actions. Новая модель становится `champion` и выкатывается только после прохождения гейта по PR-AUC; работа API наблюдается в Prometheus и Grafana и проверяется под трафиком Locust.

## Технологии

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)

![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-0F1689?style=flat-square&logo=helm&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)

![MLflow](https://img.shields.io/badge/MLflow-0194E2?style=flat-square&logo=mlflow&logoColor=white)
![DVC](https://img.shields.io/badge/DVC-13ADC7?style=flat-square&logo=dvc&logoColor=white)
![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-017CEE?style=flat-square&logo=apacheairflow&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat-square&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?style=flat-square&logo=grafana&logoColor=white)

Также используются **kind**, **RustFS (S3)**, **Pandera**, **Locust**, **uv** и **GHCR**.

## Quickstart

### Перед стартом: установить инструменты

**Эти инструменты устанавливаются самостоятельно. `up.sh` не устанавливает их на компьютер — он использует их для создания платформы.**

| Инструмент | Для чего нужен | Официальная установка |
| --- | --- | --- |
| Git и Git Bash на Windows | Клонирование репозитория и запуск Bash-команд | [Git](https://git-scm.com/downloads/), [Git for Windows](https://gitforwindows.org/) |
| Python **3.11 или 3.12** | Локальные проверка данных и обучение | [Python](https://www.python.org/downloads/) |
| uv | Установка Python-зависимостей и запуск команд проекта | [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Docker Desktop на Windows/macOS / Docker Engine на Linux | Контейнеры и узел kind | [Docker Desktop](https://docs.docker.com/desktop/), [Docker Engine](https://docs.docker.com/engine/install/) |
| kind | Создание локального Kubernetes-кластера | [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) |
| kubectl | Управление ресурсами Kubernetes | [kubectl](https://kubernetes.io/docs/tasks/tools/) |
| Helm | Установка компонентов платформы из чартов | [Helm](https://helm.sh/docs/intro/install/) |
| curl с `--aws-sigv4` | HTTP-проверки и создание S3-бакета | [curl](https://curl.se/download.html) |

**Желательно, но необязательно:** [k9s](https://k9scli.io/topics/install/) — терминальный интерфейс для просмотра pod, событий и логов. Для запуска платформы он не нужен; после создания кластера можно открыть `k9s --context kind-pred-main-mlops -A`. Не удаляй ресурсы через интерфейс, если нужен только просмотр.

Все команды ниже выполняются **из корня уже клонированного репозитория в Bash**: на Windows используй **Git Bash**, на Linux/macOS — `bash`. Исключение — отдельно помеченные команды Windows CMD. Docker должен быть запущен (на Windows — Linux-контейнеры), порт 80 свободен. После установки инструментов открой новый терминал, чтобы обновился PATH. На macOS полный маршрут пока не проверен.

**Почему Git Bash:** `up.sh` и команды этого руководства используют синтаксис Bash: `source`, `$VARIABLE`, циклы и переносы строк через `\`. PowerShell — другой язык команд и не исполняет их напрямую. Git Bash позволяет запустить тот же скрипт на Windows без отдельной PowerShell-версии; Docker и Kubernetes при этом остаются на твоем компьютере. Терминал VS Code подходит, если выбран профиль **Git Bash**. Активация Python `.venv` не превращает PowerShell в Bash.

Проверка инструментов:

```bash
git --version
uv --version
docker info
kind version
kubectl version --client
helm version
curl --help all | grep -- --aws-sigv4
```

**Ожидаем:** команды найдены, `docker info` подключается к Docker, последняя команда показывает опцию `--aws-sigv4`. Если инструмент не найден или Docker недоступен, сначала исправь это, затем продолжай.

> Скрипт написан, но полный маршрут в свежем клоне и новом кластере пока не проверен. Не удаляй существующий кластер без сохранения данных PVC. Разбор скрипта: [platform/UP.md](platform/UP.md).

### 1. Локальные адреса сервисов

Адреса `*.localhost` должны указывать на `127.0.0.1` — твой компьютер, где kind принимает HTTP-запросы. Это настройка **hosts, не PATH**; она нужна и браузеру, и Python/DVC. `up.sh` системный hosts не меняет.

Если записи уже есть, повторно добавлять их не нужно. При другом IP исправь существующие записи вместо создания дубликатов.

**Windows:** открой **CMD от имени администратора** (не PowerShell и не Git Bash), выполни один раз:

```bat
echo.>> C:\Windows\System32\drivers\etc\hosts
echo 127.0.0.1 mlflow.localhost airflow.localhost grafana.localhost pred-main.localhost s3.localhost s3-console.localhost>> C:\Windows\System32\drivers\etc\hosts
ipconfig /flushdns
```

Альтернатива: открой `C:\Windows\System32\drivers\etc\hosts` в Блокноте от администратора и добавь ту же строку вручную; сохрани без расширения `.txt`.

**Linux/macOS:** в терминале Bash выполни один раз:

```bash
printf '\n127.0.0.1 mlflow.localhost airflow.localhost grafana.localhost pred-main.localhost s3.localhost s3-console.localhost\n' | sudo tee -a /etc/hosts
```

На macOS после изменения сбрось кеш DNS:

```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

**Ожидаем:** все шесть адресов направлены на локальный компьютер. Дальше вернись в Bash; на Windows — в Git Bash.

### 2. Поднять платформу

**Где запускать:** на своем компьютере, в Bash (Windows: Git Bash), **из корня клонированного проекта**, где лежат `README.md`, `.env.example` и каталог `platform/`. Не внутри pod, контейнера или папки `platform/`.

Установи Python-зависимости и создай `.env`, если своего файла еще нет:

```bash
uv sync --frozen
test -f .env || cp .env.example .env
```

Учебные S3-ключи — `admin/admin123`, Grafana — `admin/admin`. Свои стартовые S3-ключи задай в `.env` **до первого запуска**; файл не коммитится. Затем загрузи настройки в текущий терминал и запусти платформу:

```bash
set -a; source .env; set +a
uv run python -c "import socket; print(socket.gethostbyname('s3.localhost')); print(socket.gethostbyname('mlflow.localhost'))"
bash platform/up.sh
kubectl get pods -A
```

Python-проверка должна показать две строки `127.0.0.1`. Если результат другой или появилась ошибка, исправь hosts из шага 1 и только потом запускай `up.sh`. `set -a; source .env; set +a` экспортирует настройки для последующих команд; в новом Bash-терминале его нужно повторить из папки проекта.

**Ожидаем:** скрипт завершился сообщением «Платформа готова», поды MLflow, RustFS, Airflow, Traefik, monitoring и metrics-server готовы; бакет `pred-main-dvc` создан. API и PostgreSQL появятся позже, после deploy.

**Образ приложения на этом шаге не собирается и не скачивается.** Его получим через CI/CD в шаге 7. Поэтому отсутствие API-pod сразу после `up.sh` нормально; сначала нужны данные, первый champion и runner.

| Интерфейс | Адрес |
| --- | --- |
| MLflow | http://mlflow.localhost |
| Airflow | http://airflow.localhost |
| Grafana | http://grafana.localhost |
| RustFS | http://s3-console.localhost/rustfs/console/index.html |

Логин standalone Airflow смотри в `kubectl -n mlops logs deploy/airflow`; credentials не публикуй.

### 3. Настроить доступ DVC к S3

```bash
uv run dvc remote modify --local laptop access_key_id "$S3_ACCESS_KEY"
uv run dvc remote modify --local laptop secret_access_key "$S3_SECRET_KEY"
```

**Ожидаем:** команды завершились без ошибок; credentials DVC сохранены только в игнорируемом `.dvc/config.local`. Выполняй их в том же Bash, где загружен `.env`. В новом терминале сначала повтори `set -a; source .env; set +a`.

### 4. Подготовить и загрузить данные

Если хороший датасет уже есть в этом S3, достаточно `uv run dvc pull -r laptop`. **Для нового пустого бакета** получи исходный AI4I 2020 из UCI и воспроизведи очищенный слой:

```bash
uv run python - <<'PY'
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile
import pandas as pd

url = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
with urllib.request.urlopen(url, timeout=60) as response:
    archive = zipfile.ZipFile(io.BytesIO(response.read()))
    name = next(n for n in archive.namelist() if n.endswith("ai4i2020.csv"))
    df = pd.read_csv(archive.open(name))
df = df.loc[df["RNF"] == 0].copy()
df.insert(5, "Temperature delta [K]",
          (df["Process temperature [K]"] - df["Air temperature [K]"]).round(1))
content = df.to_csv(index=False).encode("utf-8")
expected = "5d9ee05b71518e3e7e71e6e60c7da425"
assert hashlib.md5(content).hexdigest() == expected, "MD5 не совпал: остановись, не делай dvc add"
Path("data/raw/ai4i2020.csv").write_bytes(content)
print("Готово:", len(df), "строк, MD5:", expected)
PY
uv run dvc status
uv run dvc commit data/raw/ai4i2020.csv.dvc
uv run dvc push -r laptop data/raw/ai4i2020.csv.dvc
```

**Ожидаем:** 9981 строка, хороший MD5 и успешный push. `dvc commit` помещает восстановленный файл в локальный кеш DVC, это не Git-коммит. Указатель не меняем: `dvc add` здесь не нужен. Если проверка MD5 не прошла, следующие шаги не выполняй.

### 5. Создать первого champion

```bash
export MLFLOW_TRACKING_URI=http://mlflow.localhost
export PYTHONIOENCODING=utf-8
uv run python -m app.validate
uv run python -m app.train
```

**Ожидаем:** проверка прошла, в MLflow появилась модель `predictive-maintenance` с alias `champion`. Номер версии не фиксирован. Это первоначальное обучение на ноутбуке; дальнейшие запуски выполняет Airflow.

### 6. Подключить свой runner и Secret БД

Для своего развертывания используй Fork с включенными Actions. Runner подключай к своему репозиторию; владелец проекта может использовать исходный.

В своем репозитории: **Settings → Secrets and variables → Actions → New repository secret**. Создай `DB_PASSWORD` со значением из локального `.env` (учебное — `postgres`). Deploy сам создаст Secret БД/API.

Затем **Settings → Actions → Runners → New self-hosted runner → Linux x64**. Возьми свежий registration token и запусти:

<details>
<summary>Команды runner в Docker</summary>

```bash
read -r -p "HTTPS URL вашего репозитория на GitHub: " REPO_URL
read -r -s -p "Runner registration token: " RUNNER_TOKEN
echo
export REPO_URL RUNNER_TOKEN
MSYS_NO_PATHCONV=1 docker run -d --name gh-runner --network kind \
  -w /home/runner --group-add 0 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e REPO_URL -e RUNNER_TOKEN \
  ghcr.io/actions/actions-runner:2.337.0 \
  bash -lc './config.sh --url="$REPO_URL" --token="$RUNNER_TOKEN" --name=pred-main-runner --labels=kind --unattended && exec ./run.sh'
unset RUNNER_TOKEN
docker logs --tail 30 gh-runner
```

Если контейнер с таким именем уже существует, не удаляй его вслепую: используй существующий runner или сначала разберись с его состоянием.

</details>

**Ожидаем:** `Listening for Jobs` в логах, runner `Idle` с меткой `kind` в GitHub. Docker socket дает runner широкие права на машину: не запускай непроверенный код и не подключай этот runner к чужому репозиторию. После проверки останови его: `docker stop gh-runner`.

### 7. Первый deploy и ответ API

В GitHub: **Actions → ci → Run workflow → main**. Runner должен работать. Дождись зеленых `tests`, `build`, `deploy`.

Откуда появляется образ сервиса:

1. `tests` проверяет код на GitHub-hosted runner.
2. `build` собирает образ из Dockerfile и публикует в GHCR **того репозитория, где запущен workflow**: `ghcr.io/<владелец>/<репозиторий>:sha-<коммит>`. При работе в форке это образ форка, а не исходного проекта.
3. `deploy` на твоем self-hosted runner выполняет `docker pull` этого образа и `kind load docker-image`, чтобы образ оказался внутри узла kind.
4. Deploy разворачивает PostgreSQL и API, командой `kubectl set image` назначает API собранный SHA-образ, затем записывает тот же адрес в Airflow Variable `pred_main_image`. Airflow использует его для отдельных pod `validate` и `train`.

**Отдельно собирать образ приложения руками не нужно.** API и обучение используют один Dockerfile; первое обучение в шаге 5 выполняется локально через uv, поэтому готовый образ для него еще не требуется. Статический тег `:1.0` в Deployment — не образ, который нужно предварительно искать: deploy заменяет его на собранный `$IMAGE`.

```bash
kubectl get pods -A
curl --fail http://pred-main.localhost/health
curl --fail http://pred-main.localhost/ready
curl --fail -H "Content-Type: application/json" \
  --data-binary @good.json http://pred-main.localhost/v1/predict
```

**Ожидаем:** PostgreSQL и API готовы; health содержит `predictive-maintenance:v…@champion`, predict возвращает `score` от 0 до 1 и `request_id`. CI также проверяет запись этого запроса в PostgreSQL. Если изменил `CLUSTER`, перед deploy согласуй `KIND_CLUSTER` в workflow.

### 8. Ручное переобучение и нагрузка

Открой Airflow, дождись появления `pred_main_retrain` после deploy и запусти вручную. Стартовые параметры: `n_estimators=300`, `max_depth=null`, `min_samples_leaf=2`.

**Ожидаем:** validate и train проходят. Если прирост PR-AUC больше `0.005`, новый champion выкатывается; иначе rollout пропускается — это нормальный результат.

Для наблюдения в Grafana:

```bash
uv run locust -f load/locustfile.py --host http://pred-main.localhost
```

Открой http://localhost:8089, задай 5 пользователей и spawn rate 1. UI Locust работает на ноутбуке, отдельный Ingress ему не нужен. Для проверки выката не останавливай нагрузку между запуском DAG и готовностью новой версии.

## Как Работает Система

<!-- ARCHITECTURE: место для согласованных схем и описания взаимодействия компонентов. -->

Раздел зарезервирован для общей схемы платформы и объяснения пути запроса, доставки приложения и переобучения. Черновики схем пока не включены: они будут доработаны перед публикацией.

## Отчет По Проекту

<!-- REPORT: место для итоговых результатов и ссылок на доказательства. -->

Здесь будет краткий итог работы и ссылка на итоговый `REPORT.md` в корне репозитория. Сам отчет будет содержать таблицу требований и доказательств, результаты прогонов, описание восстановления и журнал проблем; подробные материалы не будут целиком дублироваться в README.

Текущие рабочие отчеты и скриншоты:

- [HW4: мониторинг, DVC/S3, Pandera и Airflow](reports/hw4/REPORT.md).
- [HW3: MLflow, Model Registry, DVC и CI/CD](reports/hw3/REPORT.md).
- [HW2](reports/hw2/REPORT.md).
- [HW1](reports/hw1/REPORT.md).
