# Compressed Air Operations Intelligence 
---
### The solution addresses the problem statement by incorporating data ingestion, quality validation, operational efficiency analysis, and anomaly detection. The logic are exposed through an API built with FastAPI. Tests are also implemented to verify core logics.
---

## Approach

### 1. Data Ingestion

- Verify that all expected columns from the data specification file are present before processing.
- Parse the timestamps then convert to minute precision for consistency
- Impute the missing data using forward and backward filling due to the data's temporal nature.

### 2. Operational Efficiency

- Uses specific power as primary efficiency parameter.
- Compare obsereved specific power against spec - specific power for each compressor.
- Aggregate into configurable time windows and comapare how far they vary (Generates visualisation as well).

### 3. Anomaly Detection

I focused on oil temperature and activity transitions to flag the anomalies using statistical methods

#### **A. Oil Temperature Monitoring**

**Detection Logic:**
- Monitor for temperature exceeding 90°C threshold.
- Require sustained elevation for a provided window size with tolerance to account of intermediate sensor drops.
- Only analyze loaded compressor periods.
- Report average and maximum temperature for each flagged period
 anomalies.

#### **B. Monitoring Activity transitions (FSD Compressors Only)**
 Very frquent load/unload transitions indicate pressure control issues. This causes mechanical stress and reduces equipment lifespan. Implemted only for FSD compressors 1 and 2.

**Detection Logic:**
- Count load / unload transitions per hour for each compressors.
- Establish baseline using 95th percentile of hourly transition counts to get to know the expected transtion states per window
- Flag hours exceeding baseline.

### 4. API's

Uses FASTAPI to expose the fucntions as endpoint:

**Endpoints:**
- `POST /upload` - Upload sensor data CSV, preprocess, and store in application state
- `GET /data-quality` - Retrieve comprehensive data quality report
- `GET /windowed-efficiency` - Calculate efficiency metrics with configurable windows, return both JSON metadata and HTML visualization
- `GET /abnormal-data` - Run anomaly detection and return flagged events

---

## My Assumptions

1.  Used the provided normal ranges from `data_specification.csv` for plausibibily checks but not as hard filters.

2. Data is stationary and contains no seasonal effect.

3.  Assumed compressors 1 & 2 are FSD (based on uniform power consumption), compressor 3 is VSD and compressor 4 iscentrifugal (based on BOV position sensor).

4. Used statistical baselines (e.g., 95th percentile for monitoring activity transitions), assuming the dataset represents mostly normal operation with occasional anomalies.


---

## What I'd Do Differently With More Time
1. **Imputation:**
    - Use alternate imputation strategies like interpolation rather than filling with last available data to deal with gradual variation in data.

2. **Operational efficiency:**
   - Explore alternate approach - Rather than comparing the observed specific power with rated one, compare if specific power varies for same output flow due to inefficiencies.


3. **Additional Anomaly Detectors:**
   - **Creeping power:** Track gradual increases in power draw at constant output

   - **Machine Learning:** Use machine learning approaches like isolation forest to flag anomalies than wasnt captured by logical approaches

4. **Deeper Analytics on data:**

   - Train predictive models for remaining useful life (RUL) estimation
   - Use isolation forests or autoencoders for multivariate anomaly detection
   - Predict optimal compressor sequencing strategies based on demand forecast


##  Business Questions

### 1. "Is my station operating efficiently?"
**Answer:** The provided functionality `/windowed-efficiency` endpoint compares actual vs. specification specific power.
It gives idea on the efficiency

### 2. "Compressor #2 is causing problems. Can you notify me before it breaks?"
**Answer:** `/abnormal-data` endpoint detects precursor signals like oil temperature and transition activity that could point to a potential problem.

But a proper approach would be using ML based Predictive Maintainance Solution trained on recorded past failures to forecast a approaching failure or Remaining useful life in days.



### 3. "How can I save more money?"
**Answer:** Efficiency analysis could reveals:
- Which compressors operate below expected specification
- Time periods of inefficient operation (opportunities for operational changes)
- Implementing changes based on these telemetry could improve operation eficiency thereby saving cost

- Also : Building an simulation based optimiser for optimized control of VSD and Centrifugal or other controllable params to ensure ideal output with reduced operating costs.

---
