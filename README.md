# Predictive Maintenance MLOps

ML-сервис для оценки риска отказа оборудования. Сейчас в проекте есть базовый notebook для обучения модели, сохраненный model artifact и metadata-файл с описанием обученной версии.

Проект сделан так, чтобы его можно было развернуть через `uv`, открыть notebook, посмотреть данные, обучить модель и получить артефакты для будущего API.

## Структура

```text
.
├── artifacts/
│   ├── metadata.json
│   └── predictive_maintenance_pipeline.joblib
├── data/
│   └── raw/
│       └── ai4i2020.csv
├── notebooks/
│   └── predictive-maintenance.ipynb
├── src/
│   └── app/
├── pyproject.toml
├── uv.lock
└── README.md
```

## Что Нужно Заранее

Установленный `uv`.

Проверить:

```powershell
uv --version
```

Датасет лежит здесь:

```text
data/raw/ai4i2020.csv
```

Файл небольшой, поэтому его можно хранить прямо в репозитории. Это упрощает запуск проекта: после `git clone` и `uv sync` notebook уже сможет обучить модель без ручного скачивания данных.

## Быстрый Старт

Из корня проекта:

```powershell
uv sync
```

Команда создаст `.venv` и поставит зависимости из `pyproject.toml` + `uv.lock`.

## Pre-commit

В проекте есть pre-commit hook, который перед коммитом чистит outputs у Jupyter notebook. Это нужно, чтобы в репозиторий не попадали тяжелые выводы ячеек, execution counts и лишний шум в diff.

Установить hooks:

```powershell
uv run pre-commit install
```

Эта команда создает локальный Git hook:

```text
.git/hooks/pre-commit
```

Файл внутри `.git/` не коммитится и не уезжает в репозиторий. В репе хранятся только настройки hook:

```text
.pre-commit-config.yaml
scripts/strip_notebook_outputs.py
```

Поэтому после `git clone` новый человек должен один раз выполнить `uv run pre-commit install`.

Если на Windows `pre-commit` ругается на доступ к `C:\Users\<user>\.cache\pre-commit`, можно использовать локальный cache проекта:

```powershell
$env:PRE_COMMIT_HOME='.pre-commit-cache'
uv run pre-commit install
```

Запустить вручную для всех файлов:

```powershell
uv run pre-commit run --all-files
```

Локальный hook вызывает:

```text
scripts/strip_notebook_outputs.py
```

Он не меняет код ячеек, только очищает `outputs`, `execution_count` и техническую metadata выполнения.

Проверить Python окружения:

```powershell
uv run python --version
uv run python -c "import pandas, sklearn, joblib; print('ok')"
```

## Подключение Notebook Kernel

Один раз зарегистрировать kernel:

```powershell
uv run python -m ipykernel install --user --name predictive-maintenance-service --display-name "Python (.venv predictive-maintenance)"
```

После этого в VS Code или Jupyter выбрать ядро:

```text
Python (.venv predictive-maintenance)
```

Если VS Code показывает только путь к интерпретатору, выбирай:

```text
.venv\Scripts\python.exe
```

Проверочная ячейка в notebook:

```python
import sys
sys.executable
```

Ожидаемый путь должен вести в проект:

```text
...\predictive-maintenance-mlops\.venv\Scripts\python.exe
```

## Запуск Notebook

Через VS Code:

1. Открыть `notebooks/predictive-maintenance.ipynb`.
2. Выбрать kernel `Python (.venv predictive-maintenance)` или `.venv\Scripts\python.exe`.
3. Запускать ячейки сверху вниз.

Через Jupyter в браузере:

```powershell
uv run jupyter notebook notebooks/predictive-maintenance.ipynb
```

Проверочный запуск всего notebook из терминала:

```powershell
uv run jupyter nbconvert --to notebook --execute notebooks/predictive-maintenance.ipynb --output predictive-maintenance.executed.ipynb --output-dir artifacts
```

Файл `predictive-maintenance.executed.ipynb` нужен только как отчетная копия с выводами ячеек. Для сервиса он не нужен.

## Данные

Используется датасет AI4I 2020 Predictive Maintenance.

Целевая переменная:

```text
Machine failure
```

`1` означает отказ машины, `0` означает нормальную работу.

Признаки модели:

```text
Type
Air temperature [K]
Process temperature [K]
Rotational speed [rpm]
Torque [Nm]
Tool wear [min]
```

Колонки, которые не используются:

```text
UDI
Product ID
TWF
HDF
PWF
OSF
RNF
```

`UDI` и `Product ID` являются идентификаторами. `TWF`, `HDF`, `PWF`, `OSF`, `RNF` описывают типы отказов, поэтому для предсказания `Machine failure` они считаются утечкой целевой информации.

## Что Делает Notebook

Notebook `notebooks/predictive-maintenance.ipynb`:

1. Загружает CSV из `data/raw/ai4i2020.csv`.
2. Показывает структуру данных, пропуски и баланс классов.
3. Разделяет данные на train/test со стратификацией.
4. Собирает `sklearn Pipeline`.
5. Обучает `RandomForestClassifier`.
6. Считает метрики.
7. Подбирает threshold для класса отказа.
8. Сохраняет модель и metadata в `artifacts/`.

## Модель

Текущий baseline:

```text
RandomForestClassifier
```

Pipeline включает:

```text
numeric features:
  SimpleImputer(strategy="median")
  StandardScaler()

categorical features:
  SimpleImputer(strategy="most_frequent")
  OneHotEncoder(handle_unknown="ignore")

model:
  RandomForestClassifier(class_weight="balanced")
```

`class_weight="balanced"` используется из-за дисбаланса классов: отказов сильно меньше, чем нормальных наблюдений.

## Артефакты

После обучения создаются:

```text
artifacts/predictive_maintenance_pipeline.joblib
artifacts/metadata.json
```

`predictive_maintenance_pipeline.joblib` - сохраненный pipeline с preprocessing и моделью.

`metadata.json` - паспорт модели. Он нужен, чтобы сервис и разработчик понимали:

- какую модель загрузили;
- какая версия модели используется;
- какие признаки ожидаются на входе;
- какой threshold применять;
- какие колонки были исключены;
- какие метрики были получены на test-срезе;
- с какими версиями библиотек модель обучалась.

Пример ключей:

```json
{
  "model_name": "predictive-maintenance-baseline",
  "model_version": "0.1.0",
  "target": "Machine failure",
  "threshold": 0.6117,
  "features": [
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]"
  ]
}
```

## Как Использовать Модель В Коде

Минимальный пример загрузки:

```python
import json
from pathlib import Path

import joblib
import pandas as pd

ARTIFACTS_DIR = Path("artifacts")

artifact = joblib.load(ARTIFACTS_DIR / "predictive_maintenance_pipeline.joblib")
metadata = json.loads((ARTIFACTS_DIR / "metadata.json").read_text(encoding="utf-8"))

pipeline = artifact["pipeline"]
threshold = metadata["threshold"]
features = metadata["features"]

sample = pd.DataFrame([
    {
        "Type": "M",
        "Air temperature [K]": 298.1,
        "Process temperature [K]": 308.6,
        "Rotational speed [rpm]": 1551,
        "Torque [Nm]": 42.8,
        "Tool wear [min]": 0,
    }
])

failure_probability = float(pipeline.predict_proba(sample[features])[:, 1][0])
prediction = int(failure_probability >= threshold)

print({
    "failure_probability": round(failure_probability, 4),
    "prediction": prediction,
})
```

## Если VS Code Долго Подключается К Ядру

Проверить, что `.venv` живой:

```powershell
uv run python -c "import sys; print(sys.executable)"
```

Если путь ведет в `.venv`, окружение нормальное.

В VS Code:

1. `Ctrl+Shift+P`
2. `Jupyter: Shut Down All Kernels`
3. `Developer: Reload Window`
4. Открыть notebook заново
5. Выбрать `.venv\Scripts\python.exe`

Если VS Code продолжает зависать, можно работать через браузерный Jupyter:

```powershell
uv run jupyter notebook
```

## Следующие Шаги

Ближайший логичный шаг - обернуть модель в API:

```text
FastAPI endpoint
  -> загрузить joblib artifact
  -> прочитать metadata.json
  -> проверить входные признаки
  -> вернуть failure_probability и prediction
```

Потом можно добавить:

- тесты для API;
- Dockerfile;
- логирование запросов;
- сохранение новых предсказаний в PostgreSQL;
- мониторинг качества модели.
