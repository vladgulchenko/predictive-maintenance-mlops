import json
import subprocess
import sys
from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry, Gauge, generate_latest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_smoke.py"
VERSION = "predictive-maintenance:v12@champion"
SERIES = f'predictive_maintenance_model_info{{version="{VERSION}"}}'
HELP = "# HELP predictive_maintenance_model_info Model loaded by this pod\n"


def run_check(tmp_path, *, prediction=None, metrics=None, version=VERSION):
    body = {
        "score": 0.03,
        "machine_failure": False,
        "model_version": VERSION,
    }
    body.update(prediction or {})
    (tmp_path / "health.json").write_text(
        json.dumps({"model_version": version}), encoding="utf-8"
    )
    (tmp_path / "pred.json").write_text(json.dumps(body), encoding="utf-8")
    (tmp_path / "metrics.txt").write_text(
        metrics if metrics is not None else f"{HELP}{SERIES} 1.0\n", encoding="utf-8"
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize("value", ["1", "1.0", "1e0"])
def test_accepts_expected_prediction_and_active_model_metric(tmp_path, value):
    result = run_check(tmp_path, metrics=f"{HELP}{SERIES} {value}\n")
    assert result.returncode == 0, result.stderr
    assert "Smoke passed" in result.stdout


def test_accepts_metric_exported_by_prometheus_client(tmp_path):
    registry = CollectorRegistry()
    metric = Gauge(
        "predictive_maintenance_model_info", "Model loaded by this pod", ["version"], registry=registry
    )
    metric.labels(version=VERSION).set(1)
    result = run_check(tmp_path, metrics=generate_latest(registry).decode("utf-8"))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("machine_failure", [True, "false", 0, None])
def test_rejects_incorrect_prediction_class(tmp_path, machine_failure):
    result = run_check(tmp_path, prediction={"machine_failure": machine_failure})
    assert result.returncode != 0
    assert "Expected machine_failure=false" in result.stderr


def test_rejects_prediction_version_different_from_health(tmp_path):
    result = run_check(tmp_path, prediction={"model_version": "predictive-maintenance:v11@champion"})
    assert result.returncode != 0
    assert "Prediction version differs from health" in result.stderr


@pytest.mark.parametrize("version", ["0.1.0", "prefix-predictive-maintenance:v12@champion"])
def test_rejects_non_registry_health_version(tmp_path, version):
    result = run_check(tmp_path, version=version)
    assert result.returncode != 0
    assert "Unexpected registry version" in result.stderr


@pytest.mark.parametrize(
    "metrics",
    [
        "",
        HELP,
        f"{HELP}# TYPE predictive_maintenance_model_info gauge\n",
        "predictive_maintenance_model_info 1\n",
        'predictive_maintenance_model_info{version="predictive-maintenance:v11@champion"} 1\n',
        f"{SERIES} 0\n",
        f"{SERIES} NaN\n",
        f"{SERIES}\n",
        f"{SERIES} 1\n{SERIES} 1\n",
    ],
)
def test_rejects_missing_or_invalid_model_metric(tmp_path, metrics):
    result = run_check(tmp_path, metrics=metrics)
    assert result.returncode != 0
    assert "metric" in result.stderr or "active sample" in result.stderr


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_rejects_invalid_score(tmp_path, score):
    result = run_check(tmp_path, prediction={"score": score})
    assert result.returncode != 0
    assert "Invalid score" in result.stderr
