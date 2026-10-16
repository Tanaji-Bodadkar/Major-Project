# Carbon Intelligence Platform — Architecture

## System Overview

```
                         USER COMPUTER (Windows 10/11)
                                    │
                                    ▼
                       ┌────────────────────────┐
                       │   Windows Telemetry    │
                       │   (psutil + WMI)       │
                       │                        │
                       │  CPU util / freq       │
                       │  RAM used / avail      │
                       │  Disk read/write rate  │
                       │  Network sent/recv     │
                       │  GPU util (optional)   │
                       │  Process list          │
                       └───────────┬────────────┘
                                   │ raw telemetry dict
                                   ▼
                       ┌────────────────────────┐
                       │  Feature Engineering   │
                       │  (Pandas / NumPy)      │
                       │  saved preprocessing   │
                       │  pipeline (.pkl)       │
                       └───────────┬────────────┘
                                   │ feature vector
                                   ▼
                       ┌────────────────────────┐
                       │   ML Power Estimator   │
                       │   (scikit-learn)       │
                       │   Random Forest /      │
                       │   Gradient Boosting    │
                       │   power_model.pkl      │
                       └───────────┬────────────┘
                                   │ predicted_power_w
                                   ▼
                       ┌────────────────────────┐
                       │  Energy Calculator     │
                       │  Wh = P×Δt/3600        │
                       │  session accumulation  │
                       └───────────┬────────────┘
                                   │ energy_wh / energy_kwh
                                   ▼
              ┌───────────────────────────────────────┐
              │    Carbon Intensity Provider           │
              │    ElectricityMapsProvider             │
              │    ClimatiqProvider (fallback)         │
              │    FallbackProvider (static, labeled)  │
              └──────────────────┬────────────────────┘
                                 │ gCO₂e/kWh + source
                                 ▼
                       ┌────────────────────────┐
                       │   CO₂e Calculator      │
                       │   CO₂e = E(kWh) × CI   │
                       └───────────┬────────────┘
                                   │ co2e_g / co2e_kg
                                   ▼
                  ┌─────────────────────────────────────┐
                  │    Analytics & Session Engine       │
                  │    SessionManager                   │
                  │    WorkloadAnalytics                │
                  │    HistoricalComparison             │
                  │    WhatIfEngine                     │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │    Recommendation Engine            │
                  │    Rule-based, evidence-driven      │
                  │    Background / High-impact /       │
                  │    Carbon-aware / Critical WL       │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                       ┌────────────────────────┐
                       │   Flask Backend        │
                       │   REST API             │
                       │   /api/...             │
                       └───────────┬────────────┘
                                   │ JSON
                                   ▼
                       ┌────────────────────────┐
                       │   Web Dashboard        │
                       │   Jinja2 templates     │
                       │   Chart.js             │
                       │   JS polling (5s)      │
                       └───────────┬────────────┘
                                   │
                                   ▼
                            USER DECISION
```

---

## Layer Descriptions

### Layer 1 — Telemetry
**Files:** `app/telemetry/`

- `base.py` — Abstract `TelemetryProvider` interface
- `windows.py` — Windows orchestrator, calls sub-collectors
- `cpu.py` — CPU utilization, frequency, user/idle/privileged times
- `memory.py` — RAM total, available, used, utilization%
- `disk.py` — Disk read/write bytes per second
- `network.py` — Network bytes sent/received per second
- `gpu.py` — GPU utilization and memory (graceful N/A handling)
- `processes.py` — Top processes by CPU/memory

**Output:** Typed dict with all available fields, `gpu_available: bool`

### Layer 2 — Feature Engineering
**Files:** `app/ml/preprocessing.py`

- Selects and orders features matching training dataset columns
- Applies saved `preprocessing.pkl` (median imputer and StandardScaler)
- Preserves missing values and uses the fitted training imputer for unavailable signals; the API flags those estimates as reduced-evidence
- Same pipeline used in training and live inference

### Layer 3 — ML Model
**Files:** `app/ml/`

- `train.py` — Validates dataset, fits training-only preprocessing, compares three regressors
- `evaluate.py` — Calculates MAE, RMSE, R², generates plots
- `predict.py` — Loads saved model + pipeline, runs live inference
- `model_loader.py` — Singleton loader with error handling
- **Saved artifacts:** `models/power_model.pkl`, `models/preprocessing.pkl`, `models/metadata.json`; current artifacts are trained on synthetic targets only

### Layer 4 — Energy Service
**Files:** `app/services/energy_service.py`

- Maintains running energy accumulator per session
- `energy_wh += predicted_power_w × elapsed_s / 3600`
- Provides: current_power, session_energy_wh, session_energy_kwh

### Layer 5 — Carbon Intensity Service
**Files:** `app/carbon/`

- `electricity_maps.py` — Electricity Maps API v3 integration
- `climatiq.py` — Climatiq API integration (fallback)
- `fallback.py` — Static regional factors with explicit labeling
- `app/services/carbon_service.py` — Orchestrates provider selection

### Layer 6 — CO₂e Calculator
**Files:** `app/services/carbon_service.py`

- `co2e_g = energy_kwh × carbon_intensity_g_per_kwh`
- Stores per-interval and cumulative CO₂e

### Layer 7 — Analytics & Session Management
**Files:** `app/services/`

- `analytics_service.py` — Trends, averages, peaks, comparisons
- Session stored in `data/emissions/sessions.json`

### Layer 8 — Recommendation Engine
**Files:** `app/services/recommendation_service.py`

- Rule-based, reads from live analytics state
- Returns structured recommendation objects with reason + evidence

### Layer 9 — Flask API
**Files:** `app/routes/`, `app.py`

- Thin route handlers delegating to service layer
- JSON responses with consistent structure

### Layer 10 — Web UI
**Files:** `app/templates/`, `app/static/`

- Jinja2 templates
- Chart.js for all charts
- 5-second JS polling for live data updates

---

## Data Flow Diagram

```
TelemetryService.collect()
    → WindowsTelemetryProvider.get_snapshot()
    → TelemetryRecord (timestamp, cpu, memory, disk, network, gpu)
    → saved to data/telemetry/telemetry_YYYYMMDD.csv

PredictionService.predict(TelemetryRecord)
    → FeatureEngineer.prepare(TelemetryRecord)
    → MLModel.predict(feature_vector)
    → PredictionRecord (timestamp, predicted_power_w, model_name)
    → saved to data/predictions/

EnergyService.update(predicted_power_w, elapsed_s)
    → energy_wh += predicted_power_w × elapsed_s / 3600
    → session_energy_kwh = session_energy_wh / 1000

CarbonService.get_co2e(energy_kwh)
    → CarbonIntensityProvider.get_intensity(region)
    → co2e_g = energy_kwh × intensity_g_per_kwh
    → EmissionRecord (timestamp, energy_kwh, intensity, co2e_g, source)
    → saved to data/emissions/

SessionManager.get_session_state()
    → aggregated SessionRecord
    → saved to data/emissions/sessions.json
```

---

## API Contract Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/telemetry/current` | Live telemetry snapshot |
| GET | `/api/prediction/current` | Latest power prediction |
| GET | `/api/energy/current` | Current energy state |
| GET | `/api/carbon/current` | Carbon intensity + CO₂e |
| GET | `/api/session/current` | Active session summary |
| GET | `/api/sessions` | All sessions list |
| GET | `/api/analytics` | Analytics data |
| GET | `/api/recommendations` | Current recommendations |
| POST | `/api/session/start` | Start monitoring session |
| POST | `/api/session/stop` | Stop monitoring session |
| POST | `/api/what-if` | What-if calculation |
| GET | `/api/report/<session_id>` | Download PDF report |

`GET /api/prediction/current` returns a nested `prediction` result and `energy` state. A model-load or inference failure has `prediction.predicted_power_w: null` and an explanatory `error`; the energy accumulator is not updated for that interval. Missing finite telemetry is passed to the fitted median imputer and reported in `prediction.imputed_features` and `prediction.warnings`; estimates using imputed features are marked reduced-evidence. The returned model metadata and dashboard identify the current synthetic model and its unvalidated status.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.9+, Flask 2.x |
| Templating | Jinja2 |
| ML | scikit-learn, pandas, numpy |
| Telemetry | psutil, WMI (pywin32/wmi) |
| Charts | Chart.js 4.x |
| Carbon API | Electricity Maps v3, Climatiq |
| Reports | ReportLab |
| Storage | CSV + JSON (file-based) |
| Config | python-dotenv |
| Testing | pytest |

