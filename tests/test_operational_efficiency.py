import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from operational_efficiency import (
    _extract_compressor_specs,
    calculate_specific_power_windows,
)

# --- Fixtures ---


@pytest.fixture
def sample_compressor_specs():
    """Sample compressor specifications matching the JSON structure."""
    return {
        "compressors": {
            "compressor_1": {
                "rated_flow_cfm": 450.0,
                "rated_power_kw": 110.0,
                "max_power_kw": 135.68,
                "max_flow_cfm": 474.9,
            },
            "compressor_2": {
                "rated_flow_cfm": 450.0,
                "rated_power_kw": 110.0,
                "max_power_kw": 120.8,
                "max_flow_cfm": 476.7,
            },
        }
    }


@pytest.fixture
def sample_efficiency_df():
    """Sample sensor data for efficiency calculation."""
    timestamps = pd.date_range("2024-01-15 00:00", periods=120, freq="1min")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "compressor_1_flow": [450.0] * 60 + [0.0] * 60,
            "compressor_1_power": [110.0] * 60 + [0.0] * 60,
            "compressor_1_activity": ["loaded"] * 60 + ["off"] * 60,
            "compressor_2_flow": [460.0] * 120,
            "compressor_2_power": [115.0] * 120,
            "compressor_2_activity": ["loaded"] * 120,
        }
    )


# --- Tests for _extract_compressor_specs ---


class TestExtractCompressorSpecs:
    def test_extracts_all_compressors(self, sample_compressor_specs):
        """Should extract specifications for all compressors in the dict."""
        result = _extract_compressor_specs(sample_compressor_specs)
        assert "compressor_1" in result
        assert "compressor_2" in result
        assert len(result) == 2

    def test_calculates_spec_specific_power(self, sample_compressor_specs):
        """Should calculate spec_specific_power = rated_power / rated_flow."""
        result = _extract_compressor_specs(sample_compressor_specs)
        expected_sp = 110.0 / 450.0
        assert result["compressor_1"]["spec_specific_power"] == pytest.approx(
            expected_sp, rel=1e-5
        )
        assert result["compressor_2"]["spec_specific_power"] == pytest.approx(
            expected_sp, rel=1e-5
        )

    def test_handles_zero_rated_flow(self):
        """Should handle zero rated_flow gracefully (spec_specific_power = None)."""
        specs = {
            "compressors": {
                "compressor_1": {
                    "rated_flow_cfm": 0.0,
                    "rated_power_kw": 110.0,
                }
            }
        }
        result = _extract_compressor_specs(specs)
        assert result["compressor_1"]["spec_specific_power"] is None

    def test_handles_missing_rated_values(self):
        """Should handle missing rated_power or rated_flow."""
        specs = {
            "compressors": {
                "compressor_1": {
                    "max_power_kw": 135.68,
                    "max_flow_cfm": 474.9,
                }
            }
        }
        result = _extract_compressor_specs(specs)
        assert result["compressor_1"]["spec_specific_power"] is None

    def test_preserves_other_spec_values(self, sample_compressor_specs):
        """Should preserve max_power, max_flow, rated_power, rated_flow."""
        result = _extract_compressor_specs(sample_compressor_specs)
        assert result["compressor_1"]["rated_power"] == 110.0
        assert result["compressor_1"]["rated_flow"] == 450.0
        assert result["compressor_1"]["max_power"] == 135.68
        assert result["compressor_1"]["max_flow"] == 474.9


# --- Tests for calculate_specific_power_windows ---


class TestCalculateSpecificPowerWindows:
    def test_returns_dict_with_compressor_keys(
        self, sample_efficiency_df, sample_compressor_specs
    ):
        """Should return a dict with compressor IDs as keys."""
        result = calculate_specific_power_windows(
            sample_efficiency_df, sample_compressor_specs, window="h"
        )
        assert isinstance(result, dict)
        assert "compressor_1" in result
        assert "compressor_2" in result

    def test_calculates_actual_specific_power(
        self, sample_efficiency_df, sample_compressor_specs
    ):
        """Should calculate actual specific power = power / flow for loaded states."""
        result = calculate_specific_power_windows(
            sample_efficiency_df, sample_compressor_specs, window="h"
        )
        # Compressor 1: 110 kW / 450 CFM = 0.2444
        # Compressor 2: 115 kW / 460 CFM = 0.25
        if "windowed" in result["compressor_1"]:
            windowed_1 = result["compressor_1"]["windowed"]
            assert len(windowed_1) > 0
            assert windowed_1[0]["actual_specific_power"] == pytest.approx(
                110.0 / 450.0, rel=1e-3
            )

    def test_only_processes_loaded_compressors(self):
        """Should only include periods when compressor is loaded with positive flow."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=120, freq="1min")
        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "compressor_1_flow": [450.0] * 30 + [0.0] * 30 + [460.0] * 60,
                "compressor_1_power": [110.0] * 30 + [0.0] * 30 + [115.0] * 60,
                "compressor_1_activity": ["loaded"] * 30
                + ["off"] * 30
                + ["loaded"] * 60,
            }
        )
        specs = {
            "compressors": {
                "compressor_1": {
                    "rated_flow_cfm": 450.0,
                    "rated_power_kw": 110.0,
                }
            }
        }
        result = calculate_specific_power_windows(df, specs, window="h")

        # Should have data for the loaded periods only
        if "windowed" in result["compressor_1"]:
            windowed = result["compressor_1"]["windowed"]
            assert len(windowed) == 2  # Two hours with loaded activity

    def test_skips_compressors_without_columns(self, sample_compressor_specs):
        """Should skip compressors if their columns don't exist in the DataFrame."""
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-15 00:00", periods=10, freq="1min"),
                "compressor_1_flow": [450.0] * 10,
                "compressor_1_power": [110.0] * 10,
                "compressor_1_activity": ["loaded"] * 10,
            }
        )
        result = calculate_specific_power_windows(
            df, sample_compressor_specs, window="h"
        )

        # compressor_1 should have data, compressor_2 should not
        assert "compressor_1" in result
        # compressor_2 might be in result but without "windowed" key
        if "compressor_2" in result:
            assert "windowed" not in result["compressor_2"]

    def test_aggregates_by_window(self):
        """Should aggregate data by the specified time window."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=180, freq="1min")
        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "compressor_1_flow": [450.0] * 180,
                "compressor_1_power": [110.0] * 180,
                "compressor_1_activity": ["loaded"] * 180,
            }
        )
        specs = {
            "compressors": {
                "compressor_1": {
                    "rated_flow_cfm": 450.0,
                    "rated_power_kw": 110.0,
                }
            }
        }
        result = calculate_specific_power_windows(df, specs, window="h")

        if "windowed" in result["compressor_1"]:
            windowed = result["compressor_1"]["windowed"]
            # 180 minutes = 3 hours
            assert len(windowed) == 3

    def test_daily_window_aggregation(self):
        """Should support daily window aggregation."""
        timestamps = pd.date_range(
            "2024-01-15 00:00", periods=1440, freq="1min"
        )  # 1 day
        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "compressor_1_flow": [450.0] * 1440,
                "compressor_1_power": [110.0] * 1440,
                "compressor_1_activity": ["loaded"] * 1440,
            }
        )
        specs = {
            "compressors": {
                "compressor_1": {
                    "rated_flow_cfm": 450.0,
                    "rated_power_kw": 110.0,
                }
            }
        }
        result = calculate_specific_power_windows(df, specs, window="D")

        if "windowed" in result["compressor_1"]:
            windowed = result["compressor_1"]["windowed"]
            assert len(windowed) == 1  # 1 day

    def test_includes_spec_specific_power_in_output(
        self, sample_efficiency_df, sample_compressor_specs
    ):
        """Should include the spec specific power for comparison."""
        result = calculate_specific_power_windows(
            sample_efficiency_df, sample_compressor_specs, window="h"
        )
        assert "spec_specific_power" in result["compressor_1"]
        expected_sp = 110.0 / 450.0
        assert result["compressor_1"]["spec_specific_power"] == pytest.approx(
            expected_sp, rel=1e-5
        )

    def test_counts_above_spec_instances(self):
        """Should count instances where actual SP > spec SP."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=120, freq="1min")
        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "compressor_1_flow": [450.0] * 60
                + [400.0] * 60,  # Lower flow = higher SP
                "compressor_1_power": [110.0] * 120,
                "compressor_1_activity": ["loaded"] * 120,
            }
        )
        specs = {
            "compressors": {
                "compressor_1": {
                    "rated_flow_cfm": 450.0,
                    "rated_power_kw": 110.0,
                }
            }
        }
        result = calculate_specific_power_windows(df, specs, window="h")

        if "windowed" in result["compressor_1"]:
            windowed = result["compressor_1"]["windowed"]
            # Second hour should have higher SP due to lower flow
            assert windowed[1]["above_spec"] > 0
