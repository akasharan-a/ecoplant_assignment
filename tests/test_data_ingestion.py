import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_ingestion import (
    load_static_data,
    validate_columns,
    preprocess_sensor_data,
    data_quality_checks,
)


# --- Fixtures ---

@pytest.fixture
def sample_data_spec():
    """Minimal data specification DataFrame for testing."""
    return pd.DataFrame({
        "column_name": [
            "compressor_1_pressure", "compressor_1_flow", "compressor_1_power",
            "compressor_1_activity", "compressor_1_oil_temp",
        ],
        "type": ["float", "float", "float", "categorical", "float"],
        "unit": ["PSI", "CFM", "kW", "-", "°C"],
        "normal_range": [
            "98 - 103", "0 (off) / 422 - 475 (loaded)",
            "0 (off) / 80 - 117 (loaded)", "off, unloaded, loaded", "30 - 93"
        ],
    })


@pytest.fixture
def sample_sensor_df():
    """Create a minimal sensor DataFrame for preprocessing tests."""
    timestamps = pd.date_range("2024-01-15 00:00", periods=10, freq="1min")
    return pd.DataFrame({
        "timestamp": timestamps,
        "compressor_1_pressure": [100.0, 101.0, 99.5, 100.2, 101.5, 100.8, 99.9, 100.1, 101.2, 100.5],
        "compressor_1_flow": [450.0, 455.0, 0.0, 460.0, 448.0, 452.0, 0.0, 458.0, 462.0, 445.0],
        "compressor_1_power": [95.0, 97.0, 0.0, 99.0, 93.0, 96.0, 0.0, 98.0, 100.0, 94.0],
        "compressor_1_activity": ["loaded", "loaded", "off", "loaded", "loaded", "loaded", "off", "loaded", "loaded", "loaded"],
        "compressor_1_oil_temp": [65.0, 66.0, 64.0, 67.0, 68.0, 69.0, 63.0, 70.0, 71.0, 72.0],
    })


@pytest.fixture
def sensor_df_with_issues():
    """Sensor DataFrame with quality issues: missing values, duplicates, out-of-order."""
    timestamps = pd.date_range("2024-01-15 00:00", periods=10, freq="1min")
    df = pd.DataFrame({
        "timestamp": timestamps,
        "compressor_1_pressure": [100.0, None, 99.5, 100.2, 101.5, 100.8, 99.9, 100.1, None, 100.5],
        "compressor_1_flow": [450.0, 455.0, None, 460.0, 448.0, 452.0, 0.0, 458.0, 462.0, 445.0],
        "compressor_1_power": [95.0, 97.0, 0.0, 99.0, 93.0, 96.0, 0.0, 98.0, 100.0, 94.0],
        "compressor_1_activity": ["loaded", "loaded", "off", "loaded", "loaded", "loaded", "off", "loaded", "loaded", "loaded"],
        "compressor_1_oil_temp": [65.0, 66.0, 64.0, 67.0, 68.0, 69.0, 63.0, 70.0, 71.0, 72.0],
    })
    # Add a duplicate timestamp row
    dup_row = df.iloc[[3]].copy()
    dup_row["compressor_1_pressure"] = 100.9
    df = pd.concat([df, dup_row], ignore_index=True)
    return df


# --- Tests for load_static_data ---

class TestLoadStaticData:
    def test_loads_successfully_with_default_paths(self):
        """Test that static data loads from the real data files."""
        specs, data_spec = load_static_data(
            comp_specs_data_path="data/compressor_specs.json",
            data_spec_path="data/data_specification.csv",
        )
        assert "compressors" in specs
        assert len(specs["compressors"]) == 4
        assert isinstance(data_spec, pd.DataFrame)
        assert "column_name" in data_spec.columns

    def test_raises_on_missing_specs_file(self):
        """Test FileNotFoundError when specs file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_static_data(comp_specs_data_path="nonexistent.json")

    def test_raises_on_missing_data_spec_file(self):
        """Test FileNotFoundError when data spec file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_static_data(
                comp_specs_data_path="data/compressor_specs.json",
                data_spec_path="nonexistent.csv",
            )


# --- Tests for validate_columns ---

class TestValidateColumns:
    def test_no_missing_columns(self, sample_sensor_df):
        """Returns empty list when all required columns are present."""
        required = ["timestamp", "compressor_1_pressure", "compressor_1_flow"]
        missing = validate_columns(sample_sensor_df, required)
        assert missing == []

    def test_detects_missing_columns(self, sample_sensor_df):
        """Returns list of columns not found in the DataFrame."""
        required = ["timestamp", "compressor_1_pressure", "nonexistent_column"]
        missing = validate_columns(sample_sensor_df, required)
        assert "nonexistent_column" in missing
        assert len(missing) == 1

    def test_all_columns_missing(self):
        """All required columns missing from an empty DataFrame."""
        df = pd.DataFrame({"a": [1], "b": [2]})
        required = ["x", "y", "z"]
        missing = validate_columns(df, required)
        assert set(missing) == {"x", "y", "z"}


# --- Tests for preprocess_sensor_data ---

class TestPreprocessSensorData:
    def test_timestamp_becomes_index(self, sample_sensor_df, sample_data_spec):
        """Timestamp column should become the DatetimeIndex after preprocessing."""
        result = preprocess_sensor_data(sample_sensor_df, sample_data_spec)
        assert isinstance(result.index, pd.DatetimeIndex)
        assert "timestamp" not in result.columns

    def test_output_has_1min_frequency(self, sample_sensor_df, sample_data_spec):
        """Preprocessed data should have consistent 1-minute frequency."""
        result = preprocess_sensor_data(sample_sensor_df, sample_data_spec)
        assert result.index.freq == "min" or result.index.freq == "T"

    def test_no_missing_values_after_preprocessing(self, sensor_df_with_issues, sample_data_spec):
        """Forward/backward fill should eliminate NaN values in specified columns."""
        result = preprocess_sensor_data(sensor_df_with_issues, sample_data_spec)
        for col in sample_data_spec["column_name"]:
            if col in result.columns:
                assert result[col].isna().sum() == 0, f"Column {col} still has NaN values"

    def test_duplicate_timestamps_removed(self, sensor_df_with_issues, sample_data_spec):
        """Duplicate timestamps should be resolved (keep last)."""
        result = preprocess_sensor_data(sensor_df_with_issues, sample_data_spec)
        assert not result.index.duplicated().any()

    def test_raises_without_timestamp_column(self, sample_data_spec):
        """Should raise ValueError if no timestamp column is present."""
        df = pd.DataFrame({"compressor_1_pressure": [100.0, 101.0]})
        with pytest.raises(ValueError, match="Missing required 'timestamp' column"):
            preprocess_sensor_data(df, sample_data_spec)

    def test_data_sorted_by_timestamp(self, sample_data_spec):
        """Output should be sorted by timestamp even if input is out of order."""
        timestamps = pd.to_datetime(["2024-01-15 00:05", "2024-01-15 00:01", "2024-01-15 00:03"])
        df = pd.DataFrame({
            "timestamp": timestamps,
            "compressor_1_pressure": [100.0, 101.0, 99.5],
            "compressor_1_flow": [450.0, 0.0, 460.0],
            "compressor_1_power": [95.0, 0.0, 99.0],
            "compressor_1_activity": ["loaded", "off", "loaded"],
            "compressor_1_oil_temp": [65.0, 30.0, 67.0],
        })
        result = preprocess_sensor_data(df, sample_data_spec)
        assert result.index.is_monotonic_increasing


# --- Tests for data_quality_checks ---

class TestDataQualityChecks:
    def test_clean_data_returns_empty_report(self, sample_data_spec):
        """In-spec data should produce an empty quality report."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=5, freq="1min")
        df = pd.DataFrame({
            "compressor_1_pressure": [100.0, 101.0, 99.5, 100.2, 101.5],
            "compressor_1_flow": [450.0, 455.0, 0.0, 460.0, 448.0],
            "compressor_1_power": [95.0, 97.0, 0.0, 99.0, 93.0],
            "compressor_1_activity": ["loaded", "loaded", "off", "loaded", "loaded"],
            "compressor_1_oil_temp": [65.0, 66.0, 64.0, 67.0, 68.0],
        }, index=timestamps)
        report = data_quality_checks(df, sample_data_spec)
        # No out-of-range values for the columns we have
        for col in ["compressor_1_pressure", "compressor_1_flow", "compressor_1_power", "compressor_1_oil_temp"]:
            assert col not in report, f"Unexpected quality issue in {col}"

    def test_detects_pressure_out_of_range(self, sample_data_spec):
        """Pressure values outside 98-103 PSI should be flagged."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=5, freq="1min")
        df = pd.DataFrame({
            "compressor_1_pressure": [100.0, 150.0, 50.0, 100.2, 101.5],  # 150 and 50 out of range
            "compressor_1_flow": [450.0, 455.0, 460.0, 460.0, 448.0],
            "compressor_1_power": [95.0, 97.0, 99.0, 99.0, 93.0],
            "compressor_1_activity": ["loaded", "loaded", "loaded", "loaded", "loaded"],
            "compressor_1_oil_temp": [65.0, 66.0, 64.0, 67.0, 68.0],
        }, index=timestamps)
        report = data_quality_checks(df, sample_data_spec)
        assert "compressor_1_pressure" in report
        assert report["compressor_1_pressure"]["affected_count"] == 2

    def test_detects_invalid_activity_state(self, sample_data_spec):
        """Unexpected activity values should be flagged."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=5, freq="1min")
        df = pd.DataFrame({
            "compressor_1_pressure": [100.0, 101.0, 99.5, 100.2, 101.5],
            "compressor_1_flow": [450.0, 455.0, 0.0, 460.0, 448.0],
            "compressor_1_power": [95.0, 97.0, 0.0, 99.0, 93.0],
            "compressor_1_activity": ["loaded", "INVALID_STATE", "off", "loaded", "broken"],
            "compressor_1_oil_temp": [65.0, 66.0, 64.0, 67.0, 68.0],
        }, index=timestamps)
        report = data_quality_checks(df, sample_data_spec)
        assert "compressor_1_activity" in report
        assert report["compressor_1_activity"]["affected_count"] == 2

    def test_detects_oil_temp_out_of_range(self, sample_data_spec):
        """Oil temperatures above 93°C should be flagged for compressor_1."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=5, freq="1min")
        df = pd.DataFrame({
            "compressor_1_pressure": [100.0, 101.0, 99.5, 100.2, 101.5],
            "compressor_1_flow": [450.0, 455.0, 0.0, 460.0, 448.0],
            "compressor_1_power": [95.0, 97.0, 0.0, 99.0, 93.0],
            "compressor_1_activity": ["loaded", "loaded", "off", "loaded", "loaded"],
            "compressor_1_oil_temp": [65.0, 95.0, 64.0, 96.0, 68.0],  # 95 and 96 > 93
        }, index=timestamps)
        report = data_quality_checks(df, sample_data_spec)
        assert "compressor_1_oil_temp" in report
        assert report["compressor_1_oil_temp"]["affected_count"] == 2

    def test_returns_dict(self, sample_data_spec):
        """Quality report should always be a dictionary."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=3, freq="1min")
        df = pd.DataFrame({
            "compressor_1_pressure": [100.0, 101.0, 99.5],
        }, index=timestamps)
        report = data_quality_checks(df, sample_data_spec)
        assert isinstance(report, dict)
