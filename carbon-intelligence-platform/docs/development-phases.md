# Carbon Intelligence Platform — Development Phases

## Phase Completion Log

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Documentation & Architecture | ✅ Complete | requirements, architecture, telemetry-spec, ml-methodology, carbon-methodology |
| 2 | Project Structure | ✅ Complete | Full directory and package skeleton |
| 3-4 | Telemetry Engine | ✅ Complete | CPU, RAM, disk, network, GPU (graceful), processes |
| 5 | Telemetry Viewer | ✅ Complete | /api/telemetry/current working |
| 6 | Dataset Acquisition | ✅ Complete | docs/dataset.md created |
| 7-8 | EDA + Feature Engineering | ✅ Complete | Notebook + preprocessing pipeline |
| 9-10 | ML Training & Evaluation | ✅ Complete | Models trained, metrics calculated, artifacts saved |
| 11-14 | Prediction + Energy + Carbon + CO₂e | ✅ Complete | Full pipeline connected |
| 15-18 | Sessions + Analytics + Recommendations + What-If | ✅ Complete | All services implemented |
| 19 | Flask API | ✅ Complete | All routes implemented |
| 20-24 | Web Dashboard + Charts + UI | ✅ Complete | Full dashboard with all views |
| 25 | PDF Reports | ✅ Complete | ReportLab report generation |
| 26-27 | Error Handling + Security | ✅ Complete | .env, error pages, graceful failures |
| 28-29 | Unit + Integration Tests | ✅ Complete | pytest suite passing |
| 31-33 | Documentation + Commands | ✅ Complete | README, startup instructions |
| 35 | Final Validation | Pending | Checklist in progress |

---

## Phase 1 — Documentation

### Completed
- `docs/requirements.md` — Functional and non-functional requirements
- `docs/architecture.md` — System architecture with data flow diagrams
- `docs/telemetry-specification.md` — Telemetry fields, sources, schema
- `docs/ml-methodology.md` — ML approach, features, target, evaluation
- `docs/carbon-methodology.md` — Energy, carbon intensity, CO₂e formulas

### Key Decisions Made
- Primary power estimation: supervised regression on measured dataset
- TDP×CPU% rejected as primary methodology
- Carbon intensity: Electricity Maps API (primary), Climatiq (secondary), static fallback (labeled)
- Storage: CSV for telemetry, JSON for sessions/emissions
- No Docker, Redis, PostgreSQL in v1

---

## Phase 2 — Project Structure

### Directory Layout
```
carbon-intelligence-platform/
├── app.py                      # Flask entry point
├── config.py                   # Configuration
├── requirements.txt            # Dependencies
├── README.md                   # Project documentation
├── .env.example                # Environment variable template
├── .gitignore
├── app/
│   ├── __init__.py
│   ├── routes/                 # Flask blueprints
│   ├── services/               # Business logic
│   ├── telemetry/              # Telemetry collectors
│   ├── ml/                     # ML pipeline
│   ├── carbon/                 # Carbon intensity providers
│   ├── templates/              # Jinja2 templates
│   └── static/                 # CSS, JS, images
├── data/
│   ├── raw/                    # Raw downloaded datasets
│   ├── processed/              # Cleaned/processed datasets
│   ├── telemetry/              # Live telemetry CSVs
│   ├── predictions/            # Prediction logs
│   └── emissions/              # Session and CO₂e records
├── models/                     # Trained model artifacts
├── reports/figures/            # EDA and evaluation plots
├── notebooks/                  # Jupyter EDA notebooks
├── tests/                      # pytest test suite
└── docs/                       # This directory
```

---

## Design Constraints (Reaffirmed)

1. No hard-coded power values in production paths
2. No randomly generated telemetry
3. No invented ML metrics
4. TDP×CPU% is comparison only
5. GPU unavailability → graceful degradation, not crash
6. API unavailability → labeled fallback, not silent fake data
7. All estimated values labeled as such in UI
8. Preprocessing pipeline identical between training and inference

