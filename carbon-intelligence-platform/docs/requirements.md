# Carbon Intelligence Platform — Requirements

## Project Objective

Build a software platform that connects:

```
Windows System Activity
        ↓
Telemetry Collection
        ↓
ML-Based Power Estimation
        ↓
Energy Calculation
        ↓
Carbon Intensity (Live API)
        ↓
CO₂e Estimation
        ↓
Analytics & Session Management
        ↓
Decision Support & Recommendations
        ↓
Web Dashboard & PDF Reports
```

The central principle: **MEASURE → PREDICT → UNDERSTAND → RECOMMEND → REDUCE**

---

## Functional Requirements

### FR-01 — Telemetry Collection
- The system shall collect CPU utilization, CPU frequency, RAM usage, disk I/O rates, network I/O rates, and GPU metrics (where available) from the Windows operating system.
- Telemetry shall be collected using Windows-native OS performance interfaces (psutil, WMI).
- Collection interval shall default to 5 seconds and be configurable.
- Telemetry shall be stored as timestamped CSV files under `data/telemetry/`.

### FR-02 — ML Power Estimation
- The system shall use a trained supervised regression model to estimate system power consumption (Watts) from telemetry features.
- The model shall be trained on a real, documented, measured dataset.
- The model shall be saved along with its preprocessing pipeline and metadata.
- Live telemetry features shall pass through the same preprocessing pipeline used during training.

### FR-03 — Energy Calculation
- The system shall calculate cumulative energy consumption in Watt-hours (Wh) and kilowatt-hours (kWh).
- Energy shall be calculated as: `Energy(Wh) = Σ(Power_i × Δt_i / 3600)` for each sampling interval.

### FR-04 — Carbon Intensity
- The system shall fetch live grid carbon intensity from the Electricity Maps API (or Climatiq as fallback).
- If the API is unavailable, the system shall display a fallback status message — it shall NOT silently use invented values.
- Carbon intensity source, region, and timestamp shall be displayed in the UI.

### FR-05 — CO₂e Calculation
- The system shall calculate estimated CO₂e as: `CO₂e = Energy(kWh) × Carbon Intensity(kgCO₂e/kWh)`
- Units shall be consistent and clearly labeled throughout.

### FR-06 — Session Management
- The system shall support starting and stopping named monitoring sessions.
- Each session shall record: session_id, start_time, end_time, duration, avg power, peak power, total energy, total CO₂e.
- Sessions shall be stored in JSON format under `data/emissions/`.

### FR-07 — Analytics
- The system shall provide per-session and cross-session analytics.
- Analytics shall include: power trends, energy accumulation, CO₂e trends, resource utilization charts.
- Session comparison shall show energy and CO₂e across multiple sessions.

### FR-08 — Recommendation Engine
- The system shall provide rule-based, evidence-driven recommendations.
- Recommendations shall include: background activity detection, high-impact workload awareness, carbon-aware scheduling suggestions, historical comparison alerts.
- Recommendations shall NEVER claim process-level power attribution unless the methodology supports it.
- Critical workloads (ML training, rendering, simulation) shall receive awareness information, not interruption requests.

### FR-09 — What-If Analysis
- The system shall allow users to enter a hypothetical additional duration and calculate projected additional energy and CO₂e.
- What-if outputs shall be clearly labeled as projected estimates.

### FR-10 — Web Dashboard
- The system shall serve a web dashboard via Flask showing live telemetry, estimated power, energy, CO₂e, and charts.
- The dashboard shall refresh via periodic API polling (not full page reload).

### FR-11 — PDF Report Generation
- The system shall generate a PDF report per session using ReportLab.
- The report shall contain: session info, system info, power/energy/carbon summary, charts, observations, recommendations, methodology disclaimer.

### FR-12 — API
- The system shall expose a JSON REST API for all data access.
- Routes shall delegate to service classes; no business logic in route files.

---

## Non-Functional Requirements

### NFR-01 — Accuracy Transparency
- All estimated values (power, energy, CO₂e) shall be labeled as **Estimated** in the UI and reports.
- The system shall not claim direct electrical meter accuracy.

### NFR-02 — Graceful Degradation
- Missing GPU metrics shall be reported as unavailable, not substituted with invented values.
- API failures shall display a visible status — never silent fallback.

### NFR-03 — Security
- API keys shall be stored in `.env` files only.
- `.env` shall be in `.gitignore`.
- `.env.example` shall be provided.

### NFR-04 — Reproducibility
- The same preprocessing pipeline used for training shall be used for live inference.
- Model and pipeline shall be saved as `.pkl` files.
- Dataset source and citation shall be documented.

### NFR-05 — Maintainability
- Clear separation: Telemetry → ML → Energy → Carbon → Analytics → Web UI.
- No unnecessary infrastructure (no Docker, Redis, PostgreSQL, WebSockets in v1).

### NFR-06 — Performance
- Dashboard polling interval: 5 seconds.
- API response time target: <500ms for live endpoints.

### NFR-07 — Platform
- Primary platform: Windows 10/11.
- Python 3.9+.
- All Windows telemetry via psutil and WMI.

---

## Constraints

- No GUI scraping (no Task Manager automation).
- No hard-coded fake power, energy, or CO₂e values in production paths.
- No invented ML metrics.
- No random telemetry generation.
- TDP × CPU% may exist only as a documented comparison baseline, not as primary methodology.

