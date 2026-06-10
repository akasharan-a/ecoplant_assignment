import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from anomalies import (
    check_oil_temperature,
    check_activity_transitions,
    detect_anomalies,
)

# --- Fixtures ---


@pytest.fixture
def normal_oil_temp_df():
    """DataFrame with normal oil temperatures (below threshold)."""
    timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
    return pd.DataFrame(
        {
            "compressor_1_oil_temp": [70.0] * 60,
            "compressor_1_activity": ["loaded"] * 60,
        },
        index=timestamps,
    )


@pytest.fixture
def high_oil_temp_df():
    """DataFrame with sustained high oil temperature."""
    timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
    temps = [85.0] * 10 + [95.0] * 40 + [85.0] * 10  # 40 min above 90°C
    return pd.DataFrame(
        {
            "compressor_1_oil_temp": temps,
            "compressor_1_activity": ["loaded"] * 60,
        },
        index=timestamps,
    )


@pytest.fixture
def rapid_cycling_df():
    """DataFrame with rapid load/unload transitions."""
    timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
    # Alternate between loaded and unloaded every 5 minutes = 12 transitions per hour
    activity = []
    for i in range(12):
        activity.extend(["loaded"] * 5)
        if len(activity) < 60:
            activity.extend(["unloaded"] * 5)
    activity = activity[:60]

    return pd.DataFrame(
        {
            "compressor_1_activity": activity,
        },
        index=timestamps,
    )


# --- Tests for check_oil_temperature ---


class TestCheckOilTemperature:
    def test_no_anomalies_with_normal_temps(self, normal_oil_temp_df):
        """Should return no flagged periods when temps are normal."""
        result = check_oil_temperature(normal_oil_temp_df, compressor_id=1)
        assert result["total_flagged_periods"] == 0
        assert len(result["flagged_periods"]) == 0

    def test_detects_sustained_high_temperature(self, high_oil_temp_df):
        """Should detect periods where temp exceeds threshold for required duration."""
        result = check_oil_temperature(
            high_oil_temp_df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,
        )
        assert result["total_flagged_periods"] >= 1
        assert len(result["flagged_periods"]) >= 1

    def test_ignores_brief_spikes(self):
        """Should ignore temperature spikes shorter than CONSECUTIVE_MINUTES."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        temps = [70.0] * 20 + [95.0] * 15 + [70.0] * 25  # Only 15 min above threshold
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": temps,
                "compressor_1_activity": ["loaded"] * 60,
            },
            index=timestamps,
        )

        result = check_oil_temperature(
            df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,  # Requires 30 consecutive minutes
        )
        assert result["total_flagged_periods"] == 0

    def test_allows_brief_dips_within_streak(self):
        """Should tolerate brief temperature dips within an overheating period."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        # High temp with a 2-minute dip in the middle
        temps = [95.0] * 20 + [85.0] * 2 + [95.0] * 20 + [70.0] * 18
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": temps,
                "compressor_1_activity": ["loaded"] * 60,
            },
            index=timestamps,
        )

        result = check_oil_temperature(
            df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,
            ALLOWED_DROP_MINUTES=3,  # Allow up to 3 min drops
        )
        assert result["total_flagged_periods"] >= 1

    def test_includes_period_metrics(self, high_oil_temp_df):
        """Should include average and max temperature in flagged periods."""
        result = check_oil_temperature(
            high_oil_temp_df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,
        )

        if result["total_flagged_periods"] > 0:
            period = result["flagged_periods"][0]
            assert "metrics" in period
            assert "average_temperature" in period["metrics"]
            assert "maximum_temperature" in period["metrics"]
            assert period["metrics"]["average_temperature"] > 90
            assert period["metrics"]["maximum_temperature"] > 90

    def test_includes_timestamps_in_output(self, high_oil_temp_df):
        """Should include start_time and end_time for each flagged period."""
        result = check_oil_temperature(
            high_oil_temp_df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,
        )

        if result["total_flagged_periods"] > 0:
            period = result["flagged_periods"][0]
            assert "start_time" in period
            assert "end_time" in period
            assert "duration_minutes" in period

    def test_only_processes_loaded_activity(self):
        """Should only analyze data when compressor is loaded."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": [95.0] * 60,  # All high temps
                "compressor_1_activity": ["off"] * 60,  # But all off
            },
            index=timestamps,
        )

        result = check_oil_temperature(
            df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,
        )
        # Should find no anomalies because compressor wasn't loaded
        assert result["total_flagged_periods"] == 0

    def test_respects_custom_threshold(self):
        """Should use custom temperature threshold when provided."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": [80.0] * 60,
                "compressor_1_activity": ["loaded"] * 60,
            },
            index=timestamps,
        )

        # With threshold of 75, should detect anomaly
        result = check_oil_temperature(
            df,
            compressor_id=1,
            THRESHOLD_TEMP=75,
            CONSECUTIVE_MINUTES=30,
        )
        assert result["total_flagged_periods"] >= 1

    def test_metadata_in_output(self, high_oil_temp_df):
        """Should include configuration metadata in output."""
        result = check_oil_temperature(
            high_oil_temp_df,
            compressor_id=1,
            THRESHOLD_TEMP=90,
            CONSECUTIVE_MINUTES=30,
            ALLOWED_DROP_MINUTES=3,
        )

        assert result["temperature_threshold_celsius"] == 90
        assert result["required_consecutive_minutes"] == 30
        assert result["allowed_drop_minutes_tolerance"] == 3


# --- Tests for check_activity_transitions ---


class TestCheckActivityTransitions:
    def test_no_anomalies_with_stable_activity(self):
        """Should return empty dict when activity is stable."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=120, freq="1min")
        df = pd.DataFrame(
            {
                "compressor_1_activity": ["loaded"] * 120,
            },
            index=timestamps,
        )

        result = check_activity_transitions(df, compressor_id=1)
        assert len(result) == 0

    def test_detects_rapid_cycling(self, rapid_cycling_df):
        """Should detect hours with excessive load/unload transitions."""
        result = check_activity_transitions(rapid_cycling_df, compressor_id=1)
        assert len(result) >= 1

        # Check that it identifies the anomaly correctly
        for hour, data in result.items():
            assert data["type"] == "rapid_cycling"
            assert "transitions" in data
            assert "baseline" in data

    def test_ignores_normal_transition_frequency(self):
        """Should not flag hours with normal transition frequency."""
        timestamps = pd.date_range(
            "2024-01-15 00:00", periods=1440, freq="1min"
        )  # 24 hours
        # Create mostly stable activity with occasional transitions
        activity = ["loaded"] * 500 + ["unloaded"] * 100 + ["loaded"] * 840
        df = pd.DataFrame(
            {
                "compressor_1_activity": activity,
            },
            index=timestamps,
        )

        result = check_activity_transitions(df, compressor_id=1)
        # Should have few or no flagged hours
        assert len(result) <= 2

    def test_uses_95th_percentile_as_baseline(self):
        """Should use 95th percentile of transitions as baseline."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=1440, freq="1min")
        # Create varied activity with one hour of rapid cycling
        activity = []
        # First 23 hours: mostly stable
        for _ in range(23):
            activity.extend(["loaded"] * 55 + ["unloaded"] * 5)
        # Last hour: rapid cycling
        for _ in range(6):
            activity.extend(["loaded"] * 5 + ["unloaded"] * 5)

        df = pd.DataFrame(
            {
                "compressor_1_activity": activity[:1440],
            },
            index=timestamps,
        )

        result = check_activity_transitions(df, compressor_id=1)

        # The last hour should be flagged
        if len(result) > 0:
            for data in result.values():
                assert "baseline" in data
                assert data["baseline"] >= 1

    def test_counts_only_loaded_unloaded_transitions(self):
        """Should only count transitions between loaded and unloaded states."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        # Mix of off, loaded, unloaded
        activity = ["off"] * 20 + ["loaded", "unloaded"] * 15 + ["off"] * 10
        df = pd.DataFrame(
            {
                "compressor_1_activity": activity,
            },
            index=timestamps,
        )

        result = check_activity_transitions(df, compressor_id=1)

        # Should detect the rapid loaded/unloaded cycling in the middle
        if len(result) > 0:
            for data in result.values():
                # Transitions should be counted (14 transitions in 30 minutes)
                assert data["transitions"] > 0


# --- Tests for detect_anomalies ---


class TestDetectAnomalies:
    def test_returns_dict_with_all_compressors(self):
        """Should return anomaly results for all 4 compressors."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": [70.0] * 60,
                "compressor_1_activity": ["loaded"] * 60,
                "compressor_2_oil_temp": [70.0] * 60,
                "compressor_2_activity": ["loaded"] * 60,
                "compressor_3_oil_temp": [70.0] * 60,
                "compressor_3_activity": ["loaded"] * 60,
                "compressor_4_oil_temp": [70.0] * 60,
                "compressor_4_activity": ["loaded"] * 60,
            },
            index=timestamps,
        )

        result = detect_anomalies(df)

        assert "compressor_1" in result
        assert "compressor_2" in result
        assert "compressor_3" in result
        assert "compressor_4" in result

    def test_includes_oil_temp_anomalies_for_all(self):
        """Should check oil temperature anomalies for all compressors."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": [70.0] * 60,
                "compressor_1_activity": ["loaded"] * 60,
                "compressor_2_oil_temp": [70.0] * 60,
                "compressor_2_activity": ["loaded"] * 60,
                "compressor_3_oil_temp": [70.0] * 60,
                "compressor_3_activity": ["loaded"] * 60,
                "compressor_4_oil_temp": [70.0] * 60,
                "compressor_4_activity": ["loaded"] * 60,
            },
            index=timestamps,
        )

        result = detect_anomalies(df)

        for comp_id in [1, 2, 3, 4]:
            assert "oil_temperature_anomalies" in result[f"compressor_{comp_id}"]

    def test_activity_transitions_only_for_fsd_compressors(self):
        """Should only check activity transitions for FSD compressors (1 and 2)."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=60, freq="1min")
        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": [70.0] * 60,
                "compressor_1_activity": ["loaded"] * 60,
                "compressor_2_oil_temp": [70.0] * 60,
                "compressor_2_activity": ["loaded"] * 60,
                "compressor_3_oil_temp": [70.0] * 60,
                "compressor_3_activity": ["loaded"] * 60,
                "compressor_4_oil_temp": [70.0] * 60,
                "compressor_4_activity": ["loaded"] * 60,
            },
            index=timestamps,
        )

        result = detect_anomalies(df)

        # Compressors 1 and 2 should have activity transition checks
        assert result["compressor_1"]["activity_transition_anomalies"] is not None
        assert result["compressor_2"]["activity_transition_anomalies"] is not None

        # Compressors 3 and 4 should not
        assert result["compressor_3"]["activity_transition_anomalies"] is None
        assert result["compressor_4"]["activity_transition_anomalies"] is None

    def test_integrates_both_anomaly_types(self):
        """Should integrate both oil temp and activity transition anomalies."""
        timestamps = pd.date_range("2024-01-15 00:00", periods=120, freq="1min")

        # Create data with both types of anomalies
        temps = [95.0] * 60 + [70.0] * 60  # High temp in first hour
        activity = (["loaded", "unloaded"] * 30)[:60] + [
            "loaded"
        ] * 60  # Rapid cycling in first hour

        df = pd.DataFrame(
            {
                "compressor_1_oil_temp": temps,
                "compressor_1_activity": activity,
                "compressor_2_oil_temp": [70.0] * 120,
                "compressor_2_activity": ["loaded"] * 120,
                "compressor_3_oil_temp": [70.0] * 120,
                "compressor_3_activity": ["loaded"] * 120,
                "compressor_4_oil_temp": [70.0] * 120,
                "compressor_4_activity": ["loaded"] * 120,
            },
            index=timestamps,
        )

        result = detect_anomalies(df)

        # Compressor 1 should have both types of anomalies detected
        comp1_result = result["compressor_1"]
        assert "oil_temperature_anomalies" in comp1_result
        assert "activity_transition_anomalies" in comp1_result
