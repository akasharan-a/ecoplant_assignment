import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots


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
    window: str = "D",
) -> pd.DataFrame:
    """
    Calculate specific power (kW/CFM) for each compressor in time windows.

    Only considers loaded compressors with positive flow.
    Compares actual specific power against the specification specific power.

    Parameters:
    - df: Preprocessed sensor data with timestamp and per-compressor columns
    - compressor_specs: Dict with compressor specifications (from JSON)
    - window: Size of time window for aggregation (default "H" = hourly)

    Returns:
    - DataFrame with per-window-per-compressor efficiency metrics
    """

    df = df.reset_index()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    specs_lookup = _extract_compressor_specs(compressor_specs)
    results = {}

    # Normalize hourly frequency strings for pandas, but preserve other valid window codes
    window = str(window)
    if window.upper() == "H":
        window = "h"
    df["window"] = df["timestamp"].dt.floor(window)

    for comp_id, spec_info in specs_lookup.items():
        results[comp_id] = {}
        results[comp_id]["spec_specific_power"] = spec_info["spec_specific_power"]
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

        spec_sp = spec_info["spec_specific_power"]

        comp_df["spec_specific_power"] = spec_sp
        results[comp_id]["spec_specific_power"] = spec_sp

        # Mark if above spec (only when loaded with valid actual SP)
        comp_df["above_spec"] = np.where(
            comp_df["actual_specific_power"].notna(),
            comp_df["actual_specific_power"] > spec_sp,
            False,
        )

        # Aggregate by window
        windowed = (
            comp_df.groupby(["window"])
            .agg(
                {
                    "is_loaded": "sum",  # Count of loaded records
                    "actual_specific_power": "mean",
                    "flow": "mean",
                    "power": "mean",
                    "above_spec": "sum",
                }
            )
            .reset_index()
        )

        windowed = windowed.loc[windowed["is_loaded"] > 0, :].copy()
        results[comp_id]["windowed"] = windowed

    plot_efficiency_trends(results)
    results_json = {}
    for comp_id, comp_data in results.items():
        results_json[comp_id] = {
            "spec_specific_power": comp_data["spec_specific_power"]
        }
        if "windowed" in comp_data:
            comp_data["windowed"]["window"] = comp_data["windowed"][
                "window"
            ].dt.strftime("%Y-%m-%d %H:%M")
            results_json[comp_id] = {
                "spec_specific_power": comp_data["spec_specific_power"],
                "windowed": comp_data["windowed"].to_dict(orient="records"),
            }
    return results_json


def plot_efficiency_trends(windowed_results: dict):

    fig = make_subplots(
        rows=len(windowed_results),
        cols=1,
        shared_xaxes=True,
        subplot_titles=list(windowed_results.keys()),
    )
    for i, (comp_id, comp_data) in enumerate(windowed_results.items(), start=1):
        if "windowed" in comp_data:
            df = comp_data["windowed"]
            fig.add_trace(
                go.Bar(
                    x=df["window"],
                    y=df["actual_specific_power"],
                    name=f"{comp_id} Actual SP",
                ),
                row=i,
                col=1,
            )
            fig.add_hline(
                y=comp_data["spec_specific_power"],
                line_dash="dash",
                line_color="red",
                annotation_text=comp_data["spec_specific_power"],
                row=i,
                col=1,
            )
            fig.update_yaxes(title_text="Specific Power (kW/CFM)", row=i, col=1)
    fig.update_layout(
        height=300 * len(windowed_results),
        title_text="Operational Efficiency Trends by Compressor",
        showlegend=False,
    )
    fig.write_html("temp/opr_eff.html")  # Save the plot as an HTML file
