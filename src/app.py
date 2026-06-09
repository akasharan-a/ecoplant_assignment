import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn
import json
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
    
    calculate_specific_power_windows,
)
from anomalies import  detect_anomalies

app = FastAPI(
    title="Compressed Air Operations Intelligence", version="0.1", docs_url="/"
)

# 1. Load Static Data
COMPRESSOR_SPECS, DATA_SPECIFICATION = load_static_data()


@app.get("/status")
def read_root():
    return {"message": "OK"}


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



# 4. API - Output Windowed operational efficiency
@app.get("/windowed-efficiency")
def get_windowed_efficiency(window: str = 'D'):
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
    window_efficiency = calculate_specific_power_windows(
        df, COMPRESSOR_SPECS, window=window
    )

    if window_efficiency:
        file_content = open("temp/opr_eff.html", "r").read().encode("utf-8")
        file_like = io.BytesIO(file_content)
        metadata_json = json.dumps(window_efficiency)
        # Custom headers hold your string metadata while the body delivers the file binary
        headers = {
            "X-Message-Metadata": metadata_json,  # Embed the efficiency results in a custom header
            "Content-Disposition": "attachment; filename=operational_efficiency.html"  # Suggests a filename for download
        }
        
        return StreamingResponse(file_like, media_type="text/html", headers=headers)
    else:
        return {"message": "No valid compressor data found for windowed efficiency analysis."}


# 5. API - Output Abnormal Data
@app.get("/abnormal-data")
def get_abnormal_data():
    if not hasattr(app.state, "df"):
        raise HTTPException(
            status_code=400, detail="No data uploaded yet. Please use /upload first."
        )

    df = app.state.df

    anomalies = detect_anomalies(df)
    return anomalies

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
