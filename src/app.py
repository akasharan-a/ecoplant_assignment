import os
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
import pandas as pd
import io
from typing import Dict, Any
from data_ingestion import (
    load_static_data,
    validate_columns,
    preprocess_sensor_data,
    data_quality_checks,
)
from operational_efficiency import (
    estimate_operational_efficiency,
    calculate_specific_power_windows,
)

app = FastAPI(
    title="Compressed Air Operations Intelligence", version="0.1", docs_url="/"
)

# 1. Load Static Data
COMPRESSOR_SPECS, DATA_SPECIFICATION = load_static_data()


@app.get("/")
def read_root():
    return {"message": "App running"}


# 1. Upload station_sensor_data & Provide Insights
@app.post("/upload")
async def upload_sensor_data(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Invalid file format. Please upload a CSV."
        )

    contents = await file.read()
    try:
        raw_df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")

    # Validate columns
    missing_cols = validate_columns(raw_df, DATA_SPECIFICATION["column_name"])
    if missing_cols:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing_cols}. Expected: {DATA_SPECIFICATION['required_columns']}",
        )

    # Impute missing values and preprocess data
    processed_df = preprocess_sensor_data(raw_df, DATA_SPECIFICATION)

    # Store in app state for access by other endpoints
    app.state.df = processed_df

    # Generate initial insights
    insights = {
        "filename": file.filename,
        "rows_received": len(raw_df),
        "rows_after_preprocessing": len(processed_df),
        "missing_values_per_column": raw_df.isnull().sum().to_dict(),
    }
    print(insights)

    return {
        "message": "Data uploaded and preprocessed successfully.",
        "insights": insights,
    }


# # 2. Return Data Quality
@app.get("/data-quality")
def get_data_quality():
    if not hasattr(app.state, "df"):
        raise HTTPException(
            status_code=400, detail="No data uploaded yet. Please use /upload first."
        )

    df = app.state.df

    data_quality_checks_results = data_quality_checks(df, DATA_SPECIFICATION)
    print(data_quality_checks_results)
    return data_quality_checks_results


# 3. API - Output Operation Efficiency
@app.get("/operational-efficiency")
def get_operational_efficiency():
    if not hasattr(app.state, "df"):
        raise HTTPException(
            status_code=400, detail="No data uploaded yet. Please use /upload first."
        )

    df = app.state.df

    # Calculate overall efficiency metrics (compares sensor data to compressor specs)
    efficiency_summary = estimate_operational_efficiency(df, COMPRESSOR_SPECS)

    return efficiency_summary


# 4. API - Output Windowed Specific Power Analysis
@app.get("/windowed-efficiency")
def get_windowed_efficiency(window_minutes: int = 60):
    """
    Calculate specific power (kW/CFM) for each compressor in time windows.
    Compares actual specific power against rated spec specific power.

    Query parameter:
    - window_minutes: Size of time window for aggregation (default 60 = hourly)
    """
    if not hasattr(app.state, "df"):
        raise HTTPException(
            status_code=400, detail="No data uploaded yet. Please use /upload first."
        )

    df = app.state.df

    # Calculate windowed specific power analysis
    windowed_df = calculate_specific_power_windows(
        df, COMPRESSOR_SPECS, window_minutes=window_minutes
    )

    if windowed_df.empty:
        return {
            "message": "No windowed efficiency data available.",
            "window_minutes": window_minutes,
        }

    # Convert results to list of dicts for JSON serialization
    results = []
    for _, row in windowed_df.iterrows():
        results.append(
            {
                "compressor_id": row["compressor_id"],
                "window_start": (
                    row["window"].isoformat() if pd.notna(row["window"]) else None
                ),
                "loaded_records": int(row["loaded_records"]),
                "avg_specific_power_kw_per_cfm": (
                    round(row["actual_sp_mean"], 4)
                    if pd.notna(row["actual_sp_mean"])
                    else None
                ),
                "min_specific_power_kw_per_cfm": (
                    round(row["actual_sp_min"], 4)
                    if pd.notna(row["actual_sp_min"])
                    else None
                ),
                "max_specific_power_kw_per_cfm": (
                    round(row["actual_sp_max"], 4)
                    if pd.notna(row["actual_sp_max"])
                    else None
                ),
                "std_specific_power": (
                    round(row["actual_sp_std"], 4)
                    if pd.notna(row["actual_sp_std"])
                    else None
                ),
                "avg_flow_cfm": (
                    round(row["flow_mean"], 2) if pd.notna(row["flow_mean"]) else None
                ),
                "avg_power_kw": (
                    round(row["power_mean"], 2) if pd.notna(row["power_mean"]) else None
                ),
                "spec_specific_power_kw_per_cfm": (
                    round(row["spec_specific_power"], 4)
                    if pd.notna(row["spec_specific_power"])
                    else None
                ),
                "records_above_spec": int(row["records_above_spec"]),
                "status": row["status"],
            }
        )

    return {
        "window_minutes": window_minutes,
        "total_windows": len(windowed_df),
        "windows": results,
        "notes": "Specific power = Power (kW) / Flow (CFM). Lower is better. Only loaded compressors with positive flow are included.",
    }


# 5. API - Output Abnormal Data
@app.get("/abnormal-data")
def get_abnormal_data():
    if not hasattr(app.state, "df"):
        raise HTTPException(
            status_code=400, detail="No data uploaded yet. Please use /upload first."
        )

    df = app.state.df

    # Define anomalies based on constant compressor specs
    max_p = COMPRESSOR_SPECS["max_pressure_psi"]
    max_t = COMPRESSOR_SPECS["max_temp_celsius"]

    anomalies = df[
        (df["pressure"] > max_p)
        | (df["temperature"] > max_t)
        | (df["pressure"] < 0)
        | (df["temperature"] < 0)
    ]

    return {
        "total_abnormal_records": len(anomalies),
        "percentage_abnormal_data": round((len(anomalies) / len(df)) * 100, 2),
        "abnormal_records": anomalies.to_dict(orient="records"),
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
