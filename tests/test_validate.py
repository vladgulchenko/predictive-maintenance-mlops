from unittest.mock import MagicMock

import pandas as pd
import pytest
from pandera.errors import SchemaErrors

from app import validate


def sample_data(n_rows=1000):
    """Synthetic rows only: these tests require neither DVC nor the real CSV."""
    return pd.DataFrame(
        {
            "UDI": range(1, n_rows + 1),
            "Product ID": [f"M{index}" for index in range(1, n_rows + 1)],
            "Type": ["M"] * n_rows,
            "Air temperature [K]": [300.0] * n_rows,
            "Process temperature [K]": [310.0] * n_rows,
            "Rotational speed [rpm]": [1500] * n_rows,
            "Torque [Nm]": [40.0] * n_rows,
            "Tool wear [min]": [100] * n_rows,
            "Machine failure": [int(index % 30 == 0) for index in range(n_rows)],
            **{name: [0] * n_rows for name in ("TWF", "HDF", "PWF", "OSF", "RNF")},
        }
    )


def test_good_rows_pass():
    df = sample_data(3)
    pd.testing.assert_frame_equal(validate.ROW_SCHEMA.validate(df, lazy=True), df)


def test_good_batch_passes():
    df = sample_data()
    pd.testing.assert_frame_equal(validate.validate_data(df), df)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("Air temperature [K]", 26.85),  # Celsius instead of Kelvin.
        ("Rotational speed [rpm]", -100),
        ("Torque [Nm]", 400.0),
        ("Type", "UNKNOWN"),
        ("Machine failure", 2),
    ],
)
def test_invalid_row_value_is_rejected(column, value):
    df = sample_data(3)
    df.loc[0, column] = value
    with pytest.raises(SchemaErrors) as error:
        validate.ROW_SCHEMA.validate(df, lazy=True)
    assert column in set(error.value.failure_cases["column"])


def test_duplicate_identifier_is_rejected():
    df = sample_data(3)
    df.loc[1, "UDI"] = df.loc[0, "UDI"]
    with pytest.raises(SchemaErrors):
        validate.ROW_SCHEMA.validate(df, lazy=True)


def test_missing_feature_is_rejected():
    df = sample_data(3).drop(columns=["Torque [Nm]"])
    with pytest.raises(SchemaErrors):
        validate.ROW_SCHEMA.validate(df, lazy=True)


def test_small_export_is_rejected():
    with pytest.raises(SchemaErrors) as error:
        validate.validate_data(sample_data(30))
    assert "minimum_row_count" in set(error.value.failure_cases["check"])


def test_class_distribution_shift_is_rejected():
    df = sample_data()
    df["Machine failure"] = 0
    with pytest.raises(SchemaErrors) as error:
        validate.validate_data(df)
    assert "failure_share_between_1_and_10_percent" in set(error.value.failure_cases["check"])


def test_lazy_validation_collects_multiple_errors():
    df = sample_data(3)
    df.loc[0, "Torque [Nm]"] = -1.0
    df.loc[1, "Type"] = "UNKNOWN"
    with pytest.raises(SchemaErrors) as error:
        validate.ROW_SCHEMA.validate(df, lazy=True)
    assert {"Torque [Nm]", "Type"} <= set(error.value.failure_cases["column"])


@pytest.mark.parametrize("valid", [True, False])
def test_main_records_validation_result(tmp_path, monkeypatch, valid):
    df = sample_data()
    if not valid:
        df.loc[0, "Air temperature [K]"] = 26.85
    data_path = tmp_path / "sample.csv"
    df.to_csv(data_path, index=False)
    monkeypatch.setenv("DATA_PATH", str(data_path))
    tracking = MagicMock()
    monkeypatch.setattr(validate, "mlflow", tracking)
    artifacts = []
    tracking.log_artifact.side_effect = lambda path: artifacts.append(pd.read_csv(path))

    if valid:
        validate.main()
        tracking.set_tag.assert_called_once_with("valid", "true")
        tracking.log_artifact.assert_not_called()
    else:
        with pytest.raises(SystemExit) as error:
            validate.main()
        assert error.value.code == 1
        tracking.set_tag.assert_not_called()
        assert artifacts[0]["column"].tolist() == ["Air temperature [K]"]
        assert tracking.start_run.return_value.__exit__.call_args.args[0] is SystemExit

    assert tracking.start_run.call_args.kwargs["tags"]["valid"] == "false"
    assert "data_md5" in tracking.log_params.call_args.args[0]
