# Carbon Intelligence Platform

> **A Web-Based System for Tracking, Predicting and Visualizing Digital Carbon Emissions**

An AI-driven Green Computing platform that collects Windows system telemetry, estimates
power with machine learning, calculates energy consumption, estimates operational CO₂e
using carbon-intensity data, and provides context-aware decision support. Its current
live model is a synthetic-data prototype; a meter-based validation workflow is provided
separately and no real-world accuracy claim is made yet.

**Central principle: MEASURE → PREDICT → UNDERSTAND → RECOMMEND → REDUCE**

---

## Problem Statement

Modern computing systems consume significant electrical energy. This platform explores
whether observable OS telemetry can support useful power estimates and carbon-aware
decision support. Direct power-meter readings are needed to validate those estimates.

---

## Solution Architecture

```
Windows Telemetry (psutil/WMI)
        ↓
Feature Engineering
        ↓
ML Power Estimator (prototype trained on synthetic targets)
        ↓
Estimated Power (W) → Energy (Wh/kWh)
        ↓
Carbon Intensity (Electricity Maps API)
        ↓
Estimated CO₂e
        ↓
Analytics + Recommendations + What-If
        ↓
Flask Web Dashboard + PDF Reports
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.9+, Flask 2.x |
| ML | scikit-learn (Gradient Boosting, Random Forest, Linear Regression) |
| Telemetry | psutil, WMI |
| Carbon APIs | Electricity Maps v3, Climatiq |
| Charts | Chart.js 4.x |
| Reports | ReportLab |
| Data Storage | CSV + JSON (file-based) |
| Testing | pytest |

---

## Installation

### 1. Clone / extract the project

```powershell
cd "e:\MIT\Major Project\CORE\carbon-intelligence-platform"
```

### 2. Create virtual environment (recommended)

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` and add your API keys:

```env
ELECTRICITY_MAPS_API_KEY=your_key_here
CLIMATIQ_API_KEY=your_key_here        # optional fallback
CARBON_ZONE=IN-WE                     # your grid zone
SECRET_KEY=change-this-to-random
```

Get a free Electricity Maps API key: https://www.electricitymaps.com/free-tier-api

---

## Dataset and ML Training

The default live model below is still a **synthetic-data prototype**. To validate with
power readings, follow [docs/measured-validation.md](docs/measured-validation.md).
The workflow aligns timestamped readings with app telemetry, holds out complete
sessions for evaluation, compares against a baseline, and saves an inactive candidate
model plus actual-versus-predicted and residual plots. It supports HWiNFO CPU Package
Power and Total System Power when no plug-in meter is available. Those platform sensors
are not external wall-input measurements and do not establish wall-power accuracy.

### Step 1: Generate training dataset

```powershell
python notebooks/generate_training_data.py
```

This generates synthetic prototype rows. Target watts are produced by a formula,
not measured by an electrical meter. Do not use its metrics as real-world accuracy.
See `docs/dataset.md` for dataset candidate findings and limitations.

### Step 2: Run EDA (optional)

```powershell
python notebooks/eda_and_preprocessing.py
```

Saves analysis plots to `reports/figures/`.

### Step 3: Train ML models

```powershell
python -m app.ml.train
```

Trains Linear Regression, Random Forest, and Gradient Boosting Regressors.
Selects the best model by RMSE and saves:
- `models/power_model.pkl` — trained model
- `models/preprocessing.pkl` — fitted median imputer and StandardScaler
- `models/metadata.json` — metrics and provenance

The training command writes current held-out metrics to `models/metadata.json`.
They describe fit to synthetic generated targets only and are not a real-world
accuracy claim. Retrain with the documented seed and split to reproduce them.

---

## Running the Application

```powershell
python app.py
```

Open: **http://127.0.0.1:5000**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/telemetry/current` | Live telemetry snapshot |
| GET | `/api/telemetry/status` | Telemetry service status |
| GET | `/api/prediction/current` | Latest ML power prediction |
| GET | `/api/energy/current` | Current session energy state |
| GET | `/api/model/status` | ML model loading status |
| GET | `/api/carbon/current` | Carbon intensity + CO₂e |
| GET | `/api/session/current` | Active session summary |
| GET | `/api/sessions` | All completed sessions |
| GET | `/api/analytics` | Analytics data for charts |
| GET | `/api/recommendations` | Current recommendations |
| POST | `/api/session/start` | Start a monitoring session |
| POST | `/api/session/stop` | Stop the active session |
| POST | `/api/what-if` | What-if analysis |
| GET | `/api/report/<session_id>` | Download PDF report |

---

## Dashboard Features

- **Live telemetry:** CPU%, CPU frequency, RAM, disk I/O, network I/O, GPU (if available)
- **Estimated power:** ML-predicted Watts (labeled as estimated)
- **Session energy:** Accumulated Wh and kWh
- **CO₂e:** Calculated from energy × live carbon intensity
- **Carbon intensity:** Live from Electricity Maps with zone and source display
- **Charts:** Power timeline, CPU/RAM utilization, session comparison
- **Session management:** Start/stop sessions with automatic energy tracking
- **What-if analysis:** Project additional energy/CO₂e for hypothetical duration
- **Recommendations:** Evidence-based carbon-aware suggestions
- **Session history:** All completed sessions with PDF download

---

## Energy Calculation

```
Energy(Wh) = Σ [ Power_i(W) × Δt_i(s) / 3600 ]
Energy(kWh) = Energy(Wh) / 1000
```

---

## Carbon Calculation

```
CO₂e(gCO₂e) = Energy(kWh) × CarbonIntensity(gCO₂e/kWh)
```

Source priority: Electricity Maps → Climatiq → Static fallback (if configured)

---

## Recommendation Engine

Rule-based recommendations covering:
1. **High-impact workload detection** — sustained high CPU
2. **Background activity detection** — unnecessary resource usage
3. **Carbon-aware scheduling** — elevated grid intensity warnings
4. **Historical comparison** — session-to-session energy trends
5. **Critical workload awareness** — never recommends stopping required computation

---

## Testing

```powershell
python -m pytest tests/ -v
```

The suite covers energy calculations, carbon formulas, telemetry parsing,
feature engineering, session management, and recommendation rules. Run it to
see the current actual result.

---

## Limitations

- Power values are **estimated** by ML model, not direct electrical measurements
- Current model uses synthetic formula-generated targets; real-world accuracy is unknown
- Process-level power attribution is NOT supported by this methodology
- GPU power estimation requires WMI GPU performance counters (Win10+ with drivers)
- CO₂e covers Scope 2 (operational electricity) only — not Scope 3 (hardware manufacture)
- Carbon intensity granularity is ~15 minutes (Electricity Maps update frequency)
- No independent external power-meter validation has been completed yet

---

## Future Scope

- Complete external meter validation using the workflow in `docs/measured-validation.md`
- RAPL-based power reading on supported Intel CPUs (Linux)
- Time-series forecasting for carbon-aware workload scheduling
- Multi-machine monitoring
- Docker containerization for deployment

---

## Project Structure

```
carbon-intelligence-platform/
├── app.py                    # Flask entry point
├── config.py                 # Configuration
├── requirements.txt
├── README.md
├── .env.example
├── app/
│   ├── routes/               # Flask blueprints (thin — delegate to services)
│   ├── services/             # Business logic layer
│   ├── telemetry/            # Windows telemetry collectors
│   ├── ml/                   # ML training, inference, evaluation
│   ├── carbon/               # Carbon intensity providers
│   ├── templates/            # Jinja2 HTML templates
│   └── static/               # CSS, JS
├── data/
│   ├── processed/            # Training dataset
│   ├── telemetry/            # Live telemetry CSVs
│   ├── predictions/          # Prediction logs
│   └── emissions/            # Session and CO₂e records
├── models/                   # Trained model artifacts
├── reports/figures/          # EDA and evaluation plots
├── notebooks/                # Data generation and EDA scripts
├── tests/                    # pytest test suite
└── docs/                     # Architecture and methodology documentation
```

---

## Methodology Disclaimer

All power, energy, and CO₂e values produced by this system are **estimates**. Current
ML artifacts are trained on synthetic model-generated targets, not measured power;
real-world accuracy is unknown. They are not certified measurements. See `docs/ml-methodology.md` and
`docs/carbon-methodology.md` for full methodology details.

