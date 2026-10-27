"""Validate artifacts collected by the deployment smoke step."""

import json
import re
from pathlib import Path


def main():
    health = json.loads(Path("health.json").read_text(encoding="utf-8"))
    prediction = json.loads(Path("pred.json").read_text(encoding="utf-8"))
    metrics = Path("metrics.txt").read_text(encoding="utf-8")

    version = health["model_version"]
    assert re.fullmatch(r"predictive-maintenance:v[1-9][0-9]*@champion", version), (
        f"Unexpected registry version: {version!r}"
    )
    assert prediction["machine_failure"] is False, (
        f"Expected machine_failure=false for good.json: {prediction}"
    )
    assert prediction["model_version"] == version, (
        f"Prediction version differs from health: {prediction['model_version']!r} != {version!r}"
    )
    assert 0 <= prediction["score"] <= 1, f"Invalid score: {prediction}"

    series = f'predictive_maintenance_model_info{{version="{version}"}}'
    values = []
    for line in metrics.splitlines():
        fields = line.split()
        if fields and fields[0] == series:
            assert len(fields) >= 2, f"Missing model metric value: {line!r}"
            values.append(float(fields[1]))
    assert values == [1.0], f"Expected exactly one active sample {series} = 1, got {values}"

    print(f"Smoke passed: machine_failure=false, model_version={version}, model_info=1")


if __name__ == "__main__":
    main()
