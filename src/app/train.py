"""Train predictive-maintenance model, log it to MLflow, register and gate aliases.

Example:
    MLFLOW_TRACKING_URI=http://mlflow.localhost uv run python -m app.train

Every new registered version gets the `challenger` alias. It gets `champion` only
when PR-AUC is better than the current champion by at least GATE_MIN_GAIN, or when
there is no champion yet.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

DATA_PATH = Path(os.getenv("DATA_PATH", "data/raw/ai4i2020.csv"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", "artifacts"))
MODEL_NAME = os.getenv("MODEL_NAME", "predictive-maintenance")
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "predictive-maintenance")

N_ESTIMATORS = int(os.getenv("N_ESTIMATORS", "300"))
MAX_DEPTH_RAW = os.getenv("MAX_DEPTH")
MAX_DEPTH = None if MAX_DEPTH_RAW in (None, "", "None") else int(MAX_DEPTH_RAW)
MIN_SAMPLES_LEAF = int(os.getenv("MIN_SAMPLES_LEAF", "2"))
MIN_GAIN = float(os.getenv("GATE_MIN_GAIN", "0.005"))
SEED = 42

TARGET = "Machine failure"
LEAKAGE_COLUMNS = ["TWF", "HDF", "PWF", "OSF", "RNF"]
ID_COLUMNS = ["UDI", "Product ID"]
NUMERIC = [
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
]
CATEGORICAL = ["Type"]
FEATURES = CATEGORICAL + NUMERIC

SKOPS_TRUSTED = [
    "numpy.dtype",
    "sklearn.compose._column_transformer._RemainderColsList",
    "sklearn.tree._tree.Tree",
]


def load_and_validate(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = set(FEATURES + [TARGET] + LEAKAGE_COLUMNS + ID_COLUMNS)
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in dataset: {sorted(missing)}")
    if len(df) < 1000:
        raise ValueError(f"Dataset is too small: {len(df)} rows")
    if not set(df[TARGET].unique()) <= {0, 1}:
        raise ValueError(f"Unexpected target values: {df[TARGET].unique()[:5]}")
    return df


def build_pipeline() -> Pipeline:
    preprocess = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL,
            ),
        ]
    )
    model = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        min_samples_leaf=MIN_SAMPLES_LEAF,
        class_weight="balanced",
        random_state=SEED,
        n_jobs=-1,
    )
    return Pipeline([("preprocess", preprocess), ("model", model)])


def best_threshold_by_f1(y_true: pd.Series, proba: np.ndarray) -> tuple[float, float]:
    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    f1_scores = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    best_idx = int(np.nanargmax(f1_scores[:-1]))
    return float(thresholds[best_idx]), float(f1_scores[best_idx])


def champion_pr_auc(client: MlflowClient) -> tuple[str | None, float | None]:
    try:
        model_version = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        return None, None
    pr_auc = client.get_run(model_version.run_id).data.metrics.get("pr_auc")
    return str(model_version.version), pr_auc


def save_local_bundle(pipeline: Pipeline, metadata: dict) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"pipeline": pipeline, "metadata": metadata},
        MODEL_DIR / "predictive_maintenance_pipeline.joblib",
    )
    (MODEL_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> dict:
    df = load_and_validate(DATA_PATH)
    data_md5 = hashlib.md5(DATA_PATH.read_bytes()).hexdigest()

    x_train, x_test, y_train, y_test = train_test_split(
        df[FEATURES],
        df[TARGET],
        test_size=0.2,
        stratify=df[TARGET],
        random_state=SEED,
    )

    pipeline = build_pipeline().fit(x_train, y_train)
    proba = pipeline.predict_proba(x_test)[:, 1]
    threshold, best_f1 = best_threshold_by_f1(y_test, proba)
    prediction = (proba >= threshold).astype(int)
    report = classification_report(y_test, prediction, output_dict=True, zero_division=0)

    roc_auc = float(roc_auc_score(y_test, proba))
    pr_auc = float(average_precision_score(y_test, proba))
    precision = float(report["1"]["precision"])
    recall = float(report["1"]["recall"])
    f1 = float(f1_score(y_test, prediction))

    metadata = {
        "model_name": MODEL_NAME,
        "model_version": "mlflow-registry",
        "trained_at": datetime.now(UTC).isoformat(),
        "dataset": str(DATA_PATH),
        "data_md5": data_md5,
        "target": TARGET,
        "features": FEATURES,
        "numeric_cols": NUMERIC,
        "categorical_cols": CATEGORICAL,
        "dropped_columns": ID_COLUMNS + LEAKAGE_COLUMNS,
        "n_train": len(x_train),
        "n_test": len(x_test),
        "threshold": round(threshold, 4),
        "metrics_test": {
            "ROC-AUC": round(roc_auc, 4),
            "PR-AUC": round(pr_auc, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "F1": round(f1, 4),
        },
        "libs": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit-learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "mlflow": mlflow.__version__,
        },
    }

    save_local_bundle(pipeline, metadata)

    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()
    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "model": "RandomForestClassifier",
                "n_estimators": N_ESTIMATORS,
                "max_depth": MAX_DEPTH,
                "min_samples_leaf": MIN_SAMPLES_LEAF,
                "class_weight": "balanced",
                "seed": SEED,
                "data": str(DATA_PATH),
                "data_md5": data_md5,
                "gate_metric": "pr_auc",
                "min_gain": MIN_GAIN,
            }
        )
        mlflow.log_metrics(
            {
                "roc_auc": roc_auc,
                "pr_auc": pr_auc,
                "threshold": threshold,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "best_f1": best_f1,
            }
        )
        mlflow.log_dict(metadata, "metadata.json")
        mlflow.log_dict(
            {
                "labels": ["no_failure", "failure"],
                "matrix": confusion_matrix(y_test, prediction).tolist(),
            },
            "confusion_matrix.json",
        )

        info = mlflow.sklearn.log_model(
            pipeline,
            name="model",
            registered_model_name=MODEL_NAME,
            skops_trusted_types=SKOPS_TRUSTED,
        )
        version = info.registered_model_version

    old_version, old_pr_auc = champion_pr_auc(client)
    promoted = old_pr_auc is None or pr_auc > old_pr_auc + MIN_GAIN
    client.set_registered_model_alias(MODEL_NAME, "challenger", version)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, "champion", version)

    result = {
        "run_id": run.info.run_id,
        "version": version,
        "pr_auc": round(pr_auc, 4),
        "champion_before": old_version,
        "champion_pr_auc_before": old_pr_auc,
        "promoted": promoted,
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
