import json
import os
import pandas as pd


def load_static_data(comp_specs_data_path: str = "data/compressor_specs.json",
               data_spec_path: str = "data/data_specification.csv") :
    
    if not os.path.exists(comp_specs_data_path):
        raise FileNotFoundError(f"Specs file not found at {comp_specs_data_path}")
    with open(comp_specs_data_path, 'r') as f:
        comp_specs_data =  json.load(f)
    
    if not os.path.exists(data_spec_path):
        raise FileNotFoundError(f"Data spec file not found at {data_spec_path}")
    data_spec = pd.read_csv(data_spec_path)
    
    return comp_specs_data, data_spec

def validate_columns(df: pd.DataFrame, required_columns: list) -> list:
    missing_cols = [col for col in required_columns if col not in df.columns]
    return missing_cols

# Helper to automatically preprocess data
def preprocess_sensor_data(df: pd.DataFrame,DATA_SPECIFICATION: pd.DataFrame) -> pd.DataFrame:
    # Convert timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df['timestamp'] = df['timestamp'].dt.round('min')
    else:
        raise ValueError("Missing required 'timestamp' column for preprocessing.")
    
    df = df.drop_duplicates(keep="last",subset=['timestamp']).reset_index(drop=True)
    # Ensure numeric types and handle missing values (Imputation with median)
    for col, dtype in zip(DATA_SPECIFICATION["column_name"],DATA_SPECIFICATION["type"]):
        if col in df.columns:
            if dtype == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce")
                # Fill missing values with the median of that column
            df[col] = df[col].ffill().bfill()
    # Drop rows where critical timestamp failed to parse
    # df = df.dropna(subset=["timestamp"])
    return df


def data_quality_checks(df_sensor: pd.DataFrame, DATA_SPECIFICATION: pd.DataFrame) -> dict:
    quality_report = {}
    numerical_bounds = {
    'compressor_1_pressure':     lambda x: (x >= 98) & (x <= 103),
    'compressor_1_flow':         lambda x: (x == 0) | ((x >= 422) & (x <= 475)),
    'compressor_1_power':        lambda x: (x == 0) | ((x >= 80) & (x <= 117)),
    'compressor_1_oil_temp':     lambda x: (x >= 30) & (x <= 93),
    
    'compressor_2_pressure':     lambda x: (x >= 98) & (x <= 103),
    'compressor_2_flow':         lambda x: (x == 0) | ((x >= 417) & (x <= 477)),
    'compressor_2_power':        lambda x: (x == 0) | ((x >= 80) & (x <= 121)),
    'compressor_2_oil_temp':     lambda x: (x >= 30) & (x <= 103),
    
    'compressor_3_pressure':     lambda x: (x >= 106) & (x <= 110),
    'compressor_3_flow':         lambda x: (x >= 56) & (x <= 374),
    'compressor_3_power':        lambda x: (x >= 24) & (x <= 92),
    'compressor_3_oil_temp':     lambda x: (x >= 31) & (x <= 92),
    
    'compressor_4_pressure':     lambda x: (x >= 106) & (x <= 113),
    'compressor_4_flow':         lambda x: (x == 0) | ((x >= 161) & (x <= 566)),
    'compressor_4_power':        lambda x: (x == 0) | ((x >= 80) & (x <= 145)),
    'compressor_4_bov_position': lambda x: (x >= 0.0) & (x <= 0.62),
    'compressor_4_oil_temp':     lambda x: (x >= 30) & (x <= 88),
    
    'station_pressure':          lambda x: (x >= 90) & (x <= 120),
    'station_flow':              lambda x: (x >= 56) & (x <= 1791),
    'station_power':             lambda x: (x >= 24) & (x <= 448),
    'station_specific_power':    lambda x: (x >= 0.235) & (x <= 0.556)
    }

    categorical_bounds = {
        'compressor_1_activity':     ['off', 'unloaded', 'loaded'],
        'compressor_1_availability': ['available'],
        'compressor_2_activity':     ['off', 'unloaded', 'loaded'],
        'compressor_2_availability': ['available', 'in_maintenance'],
        'compressor_3_activity':     ['loaded'],
        'compressor_3_availability': ['available'],
        'compressor_4_activity':     ['off', 'loaded'],
        'compressor_4_availability': ['available']
    }
    
    
    # Check Timestamp Range 
    if 'timestamp' in df_sensor.columns:
        ts_converted = df_sensor['timestamp'].copy()
        start_date = pd.to_datetime('2024-01-15 00:00:00') 
        end_date = pd.to_datetime('2024-01-21 23:58:53')
        
        # Out of bounds mask
        out_of_dates = ts_converted[(ts_converted < start_date) | (ts_converted > end_date) | (ts_converted.isna())]
        if not out_of_dates.empty:
            quality_report['timestamp'] = {
                'issue': 'Out of date window or non-parseable datetime',
                'count_affected_indices': len(out_of_dates.index.tolist())
            }

    # Check Numerical Columns 
    for col, validation_func in numerical_bounds.items():
        if col in df_sensor.columns:
            # Ensure series numeric conversion
            series_numeric = pd.to_numeric(df_sensor[col], errors='coerce')
            
            # Identify values that are missing or fail range criteria
            is_valid = validation_func(series_numeric)
            invalid_mask = ~is_valid | series_numeric.isna()
            
            out_of_range = df_sensor[invalid_mask]
            if not out_of_range.empty:
                quality_report[col] = {
                    'issue': f"Values outside spec range: {DATA_SPECIFICATION.loc[DATA_SPECIFICATION['column_name']==col, 'normal_range'].values[0]}",
                    'affected_count': len(out_of_range),
                }
                
    # Check Categorical Columns 
    for col, allowed_categories in categorical_bounds.items():
        if col in df_sensor.columns:
            # Drop strings clean of spaces for robust categorization checks
            cleaned_series = df_sensor[col].astype(str).str.strip()
            invalid_mask = ~cleaned_series.isin(allowed_categories) & df_sensor[col].notna()
            
            out_of_cat = df_sensor[invalid_mask]
            if not out_of_cat.empty:
                quality_report[col] = {
                    'issue': f"Unexpected status state. Allowed values: {allowed_categories}", 
                    'affected_count': len(out_of_cat),
                }
                
  
    return quality_report   
    