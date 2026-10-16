"""
Carbon Intelligence Platform — ML Training Script

Trains power estimation models on the processed dataset.

Usage:
    python -m app.ml.train

The script:
1. Loads the processed dataset from data/processed/training_data.csv
2. Prepares features using the canonical FEATURE_COLUMNS
3. Uses a seeded random 80/20 split for the timestamp-free IID prototype dataset
4. Trains Linear Regression, Random Forest, and Gradient Boosting
5. Evaluates each on the test set
6. Selects the best model by RMSE
7. Saves model, preprocessing pipeline, and metadata to models/

The prototype dataset must exist at data/processed/training_data.csv before running.
See docs/dataset.md for its synthetic provenance and candidate dataset limitations.
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Add project root to path when running as module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.ml.preprocessing import FEATURE_COLUMNS, prepare_training_features
from config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

TARGET_COLUMN = "measured_power_w"


def load_dataset(data_path: str) -> pd.DataFrame:
    """Load and perform basic validation on the training dataset."""
    logger.info(f"Loading dataset from: {data_path}")
    if not os.path.isfile(data_path):
        raise FileNotFoundError(
            f"Training dataset not found: {data_path}\n"
            f"See docs/dataset.md for instructions on obtaining the dataset."
        )
    df = pd.read_csv(data_path)
    logger.info(f"Dataset loaded: {df.shape[0]} rows × {df.shape[1]} columns")
    logger.info(f"Columns: {list(df.columns)}")
    required = [*FEATURE_COLUMNS, TARGET_COLUMN]
    missing = [column for column in required if column not in df]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    values = df[required].apply(pd.to_numeric, errors="coerce")
    target = values[TARGET_COLUMN]
    if target.isna().any() or not np.isfinite(target).all():
        raise ValueError("Dataset target contains missing or non-finite values")
    if (target < 0).any():
        raise ValueError("Dataset target contains negative power values")
    if values[FEATURE_COLUMNS].isna().all(axis=1).any():
        raise ValueError("Dataset contains rows with every feature missing")
    if np.isinf(values[FEATURE_COLUMNS].to_numpy(dtype=float)).any():
        raise ValueError("Dataset features contain non-finite values")
    duplicates = int(values.duplicated().sum())
    if duplicates:
        logger.warning("Dataset contains %d duplicate feature/target rows", duplicates)
    logger.info("Missing feature values by column: %s", values[FEATURE_COLUMNS].isna().sum().to_dict())
    return values


def evaluate_model(model, X_test: np.ndarray, y_test: np.ndarray, name: str) -> dict:
    """Calculate MAE, RMSE, R² for a model on the test set."""
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    logger.info(f"{name}: MAE={mae:.3f}W  RMSE={rmse:.3f}W  R²={r2:.4f}")
    return {
        "model_name": name,
        "mae_w": round(float(mae), 4),
        "rmse_w": round(float(rmse), 4),
        "r2": round(float(r2), 4),
        "predictions": y_pred,
    }


def train():
    """Main training pipeline."""
    cfg = get_config()

    # ----------------------------------------------------------------
    # 1. Load dataset
    # ----------------------------------------------------------------
    data_path = os.path.join(cfg.DATA_DIR, "processed", "training_data.csv")
    df = load_dataset(data_path)

    # ----------------------------------------------------------------
    # 2. Validate target column
    # ----------------------------------------------------------------
    if TARGET_COLUMN not in df.columns:
        raise ValueError(
            f"Target column '{TARGET_COLUMN}' not found in dataset. "
            f"Available columns: {list(df.columns)}\n"
            f"The preprocessing script should have created this column. "
            f"See notebooks/eda_and_preprocessing.ipynb."
        )

    # ----------------------------------------------------------------
    # 3. Prepare features and target
    # ----------------------------------------------------------------
    X_df = prepare_training_features(df)
    y = df[TARGET_COLUMN].values.astype(float)

    # Remove rows where target is NaN
    valid_mask = ~np.isnan(y)
    X_df = X_df[valid_mask]
    y = y[valid_mask]
    logger.info(f"After removing NaN targets: {len(y)} valid samples")

    if len(y) < 100:
        logger.warning(
            f"Only {len(y)} training samples available. "
            f"Model quality may be poor. Verify dataset preparation."
        )

    # ----------------------------------------------------------------
    # 4. Deterministic random holdout: the generated dataset is IID synthetic
    # and has no timestamps or independent workload/hardware identifiers.
    # ----------------------------------------------------------------
    from sklearn.model_selection import train_test_split
    X_train_df, X_test_df, y_train, y_test = train_test_split(
        X_df, y, test_size=0.2, random_state=42
    )

    # ----------------------------------------------------------------
    # 5. Preprocessing pipeline (StandardScaler)
    # Fit ONLY on training data
    # ----------------------------------------------------------------
    scaler = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    X_train = scaler.fit_transform(X_train_df)
    X_test = scaler.transform(X_test_df)  # transform with training statistics

    # Save the scaler as the preprocessing pipeline
    joblib.dump(scaler, cfg.PREPROCESSING_FILE)
    logger.info(f"Preprocessing pipeline saved: {cfg.PREPROCESSING_FILE}")

    # ----------------------------------------------------------------
    # 6. Train models
    # ----------------------------------------------------------------
    models_to_train = [
        ("LinearRegression", LinearRegression()),
        ("RandomForestRegressor", RandomForestRegressor(
            n_estimators=100, random_state=42, n_jobs=-1
        )),
        ("GradientBoostingRegressor", GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=4, random_state=42
        )),
    ]

    results = []
    trained_models = {}

    for name, model in models_to_train:
        logger.info(f"Training {name}...")
        model.fit(X_train, y_train)
        result = evaluate_model(model, X_test, y_test, name)
        results.append(result)
        trained_models[name] = (model, result)

    # ----------------------------------------------------------------
    # 7. Model comparison table
    # ----------------------------------------------------------------
    logger.info("\n" + "="*60)
    logger.info("MODEL COMPARISON")
    logger.info("="*60)
    logger.info(f"{'Model':<35} {'MAE (W)':>10} {'RMSE (W)':>10} {'R²':>8}")
    logger.info("-"*60)
    for r in results:
        logger.info(
            f"{r['model_name']:<35} {r['mae_w']:>10.3f} {r['rmse_w']:>10.3f} {r['r2']:>8.4f}"
        )
    logger.info("="*60)

    # ----------------------------------------------------------------
    # 8. Select best model (lowest RMSE)
    # ----------------------------------------------------------------
    best_result = min(results, key=lambda r: r["rmse_w"])
    best_name = best_result["model_name"]
    best_model = trained_models[best_name][0]

    logger.info(f"\nSelected model: {best_name} (RMSE={best_result['rmse_w']:.3f} W)")

    # ----------------------------------------------------------------
    # 9. Save best model
    # ----------------------------------------------------------------
    joblib.dump(best_model, cfg.MODEL_FILE)
    logger.info(f"Best model saved: {cfg.MODEL_FILE}")

    # ----------------------------------------------------------------
    # 10. Save metadata
    # ----------------------------------------------------------------
    # Load dataset metadata if available
    dataset_md_path = os.path.join(cfg.BASE_DIR, "docs", "dataset.md")
    dataset_citation = "See docs/dataset.md"

    metadata = {
        "model_name": best_name,
        "features": FEATURE_COLUMNS,
        "target": TARGET_COLUMN,
        "training_dataset": "See docs/dataset.md",
        "dataset_citation": dataset_citation,
        "dataset_source": "Locally generated by notebooks/generate_training_data.py; no measured source data",
        "dataset_measurement_methodology": "No electrical measurement; formula-generated target with additive Gaussian noise",
        "train_test_split": "random_80_20_seed_42_iid_synthetic_rows",
        "training_samples": int(len(y_train)),
        "test_samples": int(len(y_test)),
        "metrics": {
            "mae_w": best_result["mae_w"],
            "rmse_w": best_result["rmse_w"],
            "r2": best_result["r2"],
        },
        "all_model_results": [
            {k: v for k, v in r.items() if k != "predictions"}
            for r in results
        ],
        "training_date": datetime.now(timezone.utc).isoformat(),
        "preprocessing": "Median SimpleImputer then StandardScaler; both fit on training data only",
        "dataset_type": "synthetic_model_generated",
        "target_is_direct_electrical_measurement": False,
        "hardware_validation_performed": False,
        "feature_units": {
            "cpu_utilization_pct": "%", "cpu_frequency_mhz": "MHz",
            "ram_utilization_pct": "%", "ram_used_mb": "MB",
            "disk_read_mb_s": "MB/s", "disk_write_mb_s": "MB/s",
            "network_sent_mb_s": "MB/s", "network_recv_mb_s": "MB/s",
            "gpu_utilization_pct": "%",
        },
        "target_unit": "W",
        "limitations": [
            "Synthetic target is generated from fixed mathematical power curves plus noise, not measured watts.",
            "Held-out metrics describe fit to the generator only, not real-world accuracy.",
            "No independent hardware validation was performed.",
            "Unavailable GPU telemetry is median-imputed by the training pipeline; live estimates with missing GPU data are lower-confidence and remain unvalidated against real power readings.",
        ],
        "hardware_workload_coverage": "Simulated feature ranges; no actual hardware or workload runs",
    }

    with open(cfg.METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved: {cfg.METADATA_FILE}")

    # ----------------------------------------------------------------
    # 11. Generate evaluation plots
    # ----------------------------------------------------------------
    try:
        from app.ml.evaluate import generate_evaluation_plots
        generate_evaluation_plots(
            models_to_train=[(name, trained_models[name][0]) for name, _ in models_to_train],
            X_test=X_test,
            y_test=y_test,
            results=results,
            best_name=best_name,
            config=cfg,
        )
    except Exception as e:
        logger.warning(f"Plot generation failed (non-fatal): {e}")

    logger.info("\nTraining complete.")
    logger.info(f"Best model: {best_name}")
    logger.info(f"MAE:  {best_result['mae_w']:.3f} W")
    logger.info(f"RMSE: {best_result['rmse_w']:.3f} W")
    logger.info(f"R²:   {best_result['r2']:.4f}")

    return metadata


if __name__ == "__main__":
    train()

