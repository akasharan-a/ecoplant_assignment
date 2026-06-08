import pandas as pd
import numpy as np


def _extract_compressor_specs(compressor_specs: dict) -> dict:
    """
    Extract and normalize compressor specifications into a lookup dictionary.

    Returns dict mapping compressor_id -> {spec_specific_power, max_power, max_flow, ...}
    """
    specs_lookup = {}
    compressors = compressor_specs.get("compressors", {})

    for comp_id, specs in compressors.items():
        rated_flow = specs.get("rated_flow_cfm")
        rated_power = specs.get("rated_power_kw")

        spec_specific_power = None
        if rated_flow and rated_power and rated_flow > 0:
            spec_specific_power = rated_power / rated_flow

        specs_lookup[comp_id] = {
            "spec_specific_power": spec_specific_power,
            "rated_power": rated_power,
            "rated_flow": rated_flow,
            "max_power": specs.get("max_power_kw"),
            "max_flow": specs.get("max_flow_cfm"),
        }

    return specs_lookup


def calculate_specific_power_windows(
    df: pd.DataFrame,
    compressor_specs: dict,
    window_minutes: int = 60,
) -> pd.DataFrame:
    """
    Calculate specific power (kW/CFM) for each compressor in time windows.

    Only considers loaded compressors with positive flow.
    Compares actual specific power against the specification specific power.

    Parameters:
    - df: Preprocessed sensor data with timestamp and per-compressor columns
    - compressor_specs: Dict with compressor specifications (from JSON)
    - window_minutes: Size of time window for aggregation (default 60 = hourly)

    Returns:
    - DataFrame with per-window-per-compressor efficiency metrics
    """
    if df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    specs_lookup = _extract_compressor_specs(compressor_specs)
    results = []

    # Create time windows
    df["window"] = df["timestamp"].dt.floor(f"{window_minutes}min")

    for comp_id, spec_info in specs_lookup.items():
        flow_col = f"{comp_id}_flow"
        power_col = f"{comp_id}_power"
        activity_col = f"{comp_id}_activity"

        # Skip if columns don't exist
        if not all(col in df.columns for col in [flow_col, power_col, activity_col]):
            continue

        # Prepare data for this compressor
        comp_df = df[["timestamp", "window", flow_col, power_col, activity_col]].copy()
        comp_df.columns = ["timestamp", "window", "flow", "power", "activity"]
        comp_df["compressor_id"] = comp_id

        # Only process loaded compressor records with positive flow
        loaded_mask = (comp_df["activity"].astype(str).str.lower() == "loaded") & (
            comp_df["flow"] > 0
        )
        comp_df["is_loaded"] = loaded_mask

        # Calculate actual specific power for loaded states
        comp_df["actual_specific_power"] = None
        comp_df.loc[loaded_mask, "actual_specific_power"] = (
            comp_df.loc[loaded_mask, "power"] / comp_df.loc[loaded_mask, "flow"]
        )

        # Set spec specific power
        spec_sp = spec_info["spec_specific_power"]
        comp_df["spec_specific_power"] = spec_sp

        # Mark if above spec (only when loaded with valid actual SP)
        comp_df["above_spec"] = np.where(
            comp_df["actual_specific_power"].notna(),
            comp_df["actual_specific_power"] > spec_sp,
            False,
        )

        # Aggregate by window
        windowed = (
            comp_df.groupby(["compressor_id", "window"])
            .agg(
                {
                    "is_loaded": "sum",  # Count of loaded records
                    "actual_specific_power": ["mean", "min", "max", "std"],
                    "flow": ["mean", "sum"],
                    "power": ["mean", "sum"],
                    "above_spec": "sum",
                }
            )
            .reset_index()
        )

        # Flatten column names
        windowed.columns = [
            "compressor_id",
            "window",
            "loaded_records",
            "actual_sp_mean",
            "actual_sp_min",
            "actual_sp_max",
            "actual_sp_std",
            "flow_mean",
            "flow_total",
            "power_mean",
            "power_total",
            "records_above_spec",
        ]

        windowed["spec_specific_power"] = spec_sp
        windowed["status"] = np.where(
            windowed["loaded_records"] > 0,
            np.where(windowed["records_above_spec"] > 0, "Above Spec", "Within Spec"),
            "Not Loaded",
        )

        windowed["window_minutes"] = window_minutes
        results.append(windowed)

    if results:
        return pd.concat(results, ignore_index=True)

    return pd.DataFrame()


def estimate_operational_efficiency(df: pd.DataFrame, compressor_specs: dict) -> dict:
    """
    Comprehensive operational efficiency analysis comparing sensor data to compressor specs.

    Returns summary statistics and per-compressor health assessment.
    """
    specs_lookup = _extract_compressor_specs(compressor_specs)
    summary = {}

    compressor_metrics = []

    for comp_id, spec_info in specs_lookup.items():
        flow_col = f"{comp_id}_flow"
        power_col = f"{comp_id}_power"
        activity_col = f"{comp_id}_activity"

        if not all(col in df.columns for col in [flow_col, power_col, activity_col]):
            continue

        # Get loaded records with positive flow
        loaded_mask = (df[activity_col].astype(str).str.lower() == "loaded") & (
            df[flow_col] > 0
        )
        loaded_data = df[loaded_mask].copy()

        if loaded_data.empty:
            compressor_metrics.append(
                {
                    "compressor_id": comp_id,
                    "loaded_records": 0,
                    "avg_specific_power": None,
                    "spec_specific_power": spec_info["spec_specific_power"],
                    "min_specific_power": None,
                    "max_specific_power": None,
                    "records_above_spec": 0,
                    "percent_above_spec": 0.0,
                    "status": "No loaded data",
                }
            )
            continue

        # Calculate specific power for loaded records
        specific_power = loaded_data[power_col] / loaded_data[flow_col]
        avg_sp = specific_power.mean()

        spec_sp = spec_info["spec_specific_power"]
        above_spec = (specific_power > spec_sp).sum() if spec_sp else 0

        compressor_metrics.append(
            {
                "compressor_id": comp_id,
                "loaded_records": len(loaded_data),
                "avg_specific_power": (
                    round(float(avg_sp), 4) if not pd.isna(avg_sp) else None
                ),
                "spec_specific_power": round(float(spec_sp), 4) if spec_sp else None,
                "min_specific_power": (
                    round(float(specific_power.min()), 4)
                    if not pd.isna(specific_power.min())
                    else None
                ),
                "max_specific_power": (
                    round(float(specific_power.max()), 4)
                    if not pd.isna(specific_power.max())
                    else None
                ),
                "records_above_spec": int(above_spec),
                "percent_above_spec": (
                    round((above_spec / len(loaded_data)) * 100, 2)
                    if len(loaded_data) > 0
                    else 0.0
                ),
                "status": "Above Spec" if above_spec > 0 else "Within Spec",
            }
        )

    summary["compressor_efficiency"] = compressor_metrics

    # Station-level specific power if available
    if "station_specific_power" in df.columns:
        station_sp = df["station_specific_power"].mean()
        summary["station_avg_specific_power"] = (
            round(float(station_sp), 4) if not pd.isna(station_sp) else None
        )
        summary["station_sp_range"] = "0.235 - 0.556 kW/CFM (lower is better)"

    return summary
