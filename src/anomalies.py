import pandas as pd
import numpy as np
import json
import json
import pandas as pd


def check_oil_temperature(
    df: pd.DataFrame,compressor_id:int,
    THRESHOLD_TEMP=90,
    CONSECUTIVE_MINUTES=30,
    ALLOWED_DROP_MINUTES=3,
) -> dict:
    """Finds consecutive oil overheating periods, allowing for minor/brief data drops.

    Parameters:
    - ALLOWED_DROP_MINUTES: The maximum number of consecutive minutes the temperature
                            can dip below the threshold without resetting the streak.
    """
    # Create a copy so we do not mutate the original data frame unexpectedly
    df = df.loc[df[f'compressor_{compressor_id}_activity']=='loaded' ,:].copy()
    
    temp_col = df.columns[0]  # Assuming the oil temperature column is the first one in the DataFrame

    # 1. Identify rows breaching the threshold
    df["raw_above"] = df[temp_col] > THRESHOLD_TEMP

    # 2. Smooth fluctuations: Use a forward-fill rolling limit to ignore brief drops
    # It bridges gaps where temperature drops below threshold for <= ALLOWED_DROP_MINUTES
    df["above_threshold"] = (
        df["raw_above"]
        .rolling(window=f"{ALLOWED_DROP_MINUTES}min", min_periods=1)
        .max()
        .astype(bool)
    )

    # 3. Assign a unique ID to every contiguous block of matching rows
    df["block_id"] = (
        df["above_threshold"].ne(df["above_threshold"].shift()).cumsum()
    )

    flagged_periods = []

    # 4. Filter for True blocks and analyze them
    for group_id, group in df[df["above_threshold"]].groupby("block_id"):
        start_time = group.index.min()
        end_time = group.index.max()

        # Calculate total duration in minutes
        duration_minutes = (
            int((end_time - start_time).total_seconds() / 60) + 1
        )

        # Filter out brief spikes that don't last long enough
        if duration_minutes >= CONSECUTIVE_MINUTES:
            flagged_periods.append(
                {
                    "period_id": len(flagged_periods) + 1,
                    "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_minutes": duration_minutes,
                    "metrics": {
                        "average_temperature": round(
                            float(group[temp_col].mean()), 2
                        ),
                        "maximum_temperature": round(
                            float(group[temp_col].max()), 2
                        ),
                    },
                }
            )

    # 5. Wrap with metadata
    output_payload = {
                    "temperature_threshold_celsius": THRESHOLD_TEMP,
            "required_consecutive_minutes": CONSECUTIVE_MINUTES,
            "allowed_drop_minutes_tolerance": ALLOWED_DROP_MINUTES,
            "total_flagged_periods": len(flagged_periods),
        "flagged_periods": flagged_periods,
    }

    return output_payload

import pandas as pd
from typing import List, Dict


def check_activity_transitions(
    df: pd.DataFrame,compressor_id:int,
) -> List[Dict]:

        activity_col=f'compressor_{compressor_id}_activity'

        group = df.copy()
        # Detect loaded <-> unloaded transitions
        prev = group[activity_col].str.lower().shift()
        curr = group[activity_col].str.lower()
        group["is_transition"] = (
            (curr != prev)
            & curr.isin(["loaded", "unloaded"])
            & prev.isin(["loaded", "unloaded"])
        )

        # Count transitions per hour
        group["hour"] = group.index.to_series().dt.floor("h")
        hourly = group.groupby("hour")["is_transition"].sum()

        baseline = max(hourly.quantile(0.95), 1)

        rapid = hourly[hourly > baseline]
        results = {}
        for hour, count in rapid.items():
            results[str(hour)] = {
                "type": "rapid_cycling",
                "hour": hour,
                "transitions": int(count),
                "baseline": round(float(baseline), 1),
                "explanation": (
                    f"{int(count)} load/unload transitions in one hour "
                    f"(baseline: {round(float(baseline), 1)}). "
                    f"May indicate struggle to maintain pressure "
                    f"or unusual demand fluctuation. "
                    f"Puts mechanical stress on the machine."
                ),
            }

        return results

def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    compressors = [1, 2, 3, 4] #only 1 and 2 are FSD
    anomalies = {}
    for comp_id in compressors:
        comp_df = df[[f'compressor_{comp_id}_oil_temp',
                        f'compressor_{comp_id}_activity']].copy()
                                                                
        oil_check = check_oil_temperature(comp_df,comp_id)
        if comp_id in [1,2]:  # Only check activity transitions for FSD compressors
            activity_check = check_activity_transitions(df,comp_id)
        
        anomalies[f"compressor_{comp_id}"] = {
            "oil_temperature_anomalies": oil_check,
            "activity_transition_anomalies": activity_check if comp_id in [1,2] else None
        }
        
    return anomalies