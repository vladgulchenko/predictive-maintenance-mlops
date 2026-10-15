"""Validate the training CSV and record a separate validation run in MLflow.

Run with: uv run python -m app.validate
DATA_PATH, MLFLOW_TRACKING_URI and MLFLOW_EXPERIMENT are environment variables.
"""

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import mlflow
import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

TARGET = "Machine failure"
MIN_ROWS = 1000
MIN_FAILURE_SHARE = 0.01
MAX_FAILURE_SHARE = 0.10

# Очищенный набор данных AI4I содержит 9 981 строку, доля отказов составляет 3,39 %.
# Следует предусмотреть достаточно широкий диапазон (1–10 %), чтобы выявлять
# пропущенные метки или значительный сдвиг в распределении классов,
# отличая их от обычного выборочного шума.
# Диапазоны значений датчиков включают определенный запас относительно
# наблюдаемых величин (K, об/мин, Н·м, мин); принудительная корректировка
# или удаление строк не допускаются: наличие некорректных входных данных
# должно приводить к остановке процесса обучения.
ROW_SCHEMA = pa.DataFrameSchema(
    {
        "UDI": pa.Column(int, pa.Check.greater_than(0), unique=True),
        "Product ID": pa.Column(str, pa.Check.str_length(min_value=1)),
        "Type": pa.Column(str, pa.Check.isin(["L", "M", "H"])),
        "Air temperature [K]": pa.Column(float, pa.Check.in_range(290, 310)),
        "Process temperature [K]": pa.Column(float, pa.Check.in_range(300, 325)),
        "Rotational speed [rpm]": pa.Column(int, pa.Check.in_range(1000, 3500)),
        "Torque [Nm]": pa.Column(
            float, [pa.Check.greater_than(0), pa.Check.less_than_or_equal_to(100)]
        ),
        "Tool wear [min]": pa.Column(int, pa.Check.in_range(0, 300)),
        TARGET: pa.Column(int, pa.Check.isin([0, 1])),
        **{
            name: pa.Column(int, pa.Check.isin([0, 1]))
            for name in ("TWF", "HDF", "PWF", "OSF", "RNF")
        },
    },
    # Допускается использование дополнительных производных столбцов, например, разности температур [K].
    strict=False,
    name="ai4i_rows",
)

BATCH_SCHEMA = pa.DataFrameSchema(
    checks=[
        pa.Check(lambda df: len(df) >= MIN_ROWS, name="minimum_row_count"),
        pa.Check(
            lambda df: MIN_FAILURE_SHARE <= df[TARGET].mean() <= MAX_FAILURE_SHARE,
            name="failure_share_between_1_and_10_percent",
        ),
    ],
    name="ai4i_batch",
)


def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    """Check individual rows, then the whole export; perform no I/O."""
    validated = ROW_SCHEMA.validate(df, lazy=True)
    return BATCH_SCHEMA.validate(validated, lazy=True)


def main() -> None:
    data_path = Path(os.getenv("DATA_PATH", "data/raw/ai4i2020.csv"))
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "predictive-maintenance"))

    with mlflow.start_run(run_name="validate", tags={"stage": "validate", "valid": "false"}):
        mlflow.log_params(
            {
                "data": str(data_path),
                "data_md5": hashlib.md5(data_path.read_bytes()).hexdigest(),
                "min_rows": MIN_ROWS,
                "min_failure_share": MIN_FAILURE_SHARE,
                "max_failure_share": MAX_FAILURE_SHARE,
            }
        )
        df = pd.read_csv(data_path)
        mlflow.log_metric("n_rows", len(df))

        try:
            validated = validate_data(df)
        except SchemaErrors as exc:
            with TemporaryDirectory(prefix="pred-main-validation-") as directory:
                failures_path = Path(directory) / "failure_cases.csv"
                exc.failure_cases.to_csv(failures_path, index=False)
                mlflow.log_artifact(str(failures_path))
            mlflow.log_metric("n_failure_cases", len(exc.failure_cases))
            print("Validation failed:")
            print(exc.failure_cases.to_string(index=False))
            # Raised inside the run context so MLflow also marks the run FAILED.
            raise SystemExit(1) from exc

        mlflow.log_metrics(
            {"failure_share": float(validated[TARGET].mean()), "n_failure_cases": 0}
        )
        mlflow.set_tag("valid", "true")
        print(f"Validation passed: {len(validated)} rows, failures={validated[TARGET].mean():.2%}")


if __name__ == "__main__":
    main()
