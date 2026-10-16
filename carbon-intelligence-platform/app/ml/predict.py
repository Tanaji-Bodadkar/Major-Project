"""
Carbon Intelligence Platform — Live Power Prediction

Connects live telemetry → feature engineering → saved pipeline → saved model → predicted watts.
"""

import logging
import numpy as np
from datetime import datetime, timezone
from typing import Optional

from app.telemetry.base import TelemetrySnapshot
from app.ml.preprocessing import snapshot_to_features
from app.ml import model_loader

logger = logging.getLogger(__name__)


def predict_power(snapshot: TelemetrySnapshot, config=None) -> dict:
    """
    Predict system power consumption from a telemetry snapshot.

    Pipeline:
        TelemetrySnapshot
            → feature DataFrame (snapshot_to_features)
            → preprocessing pipeline transform
            → model predict
            → predicted_power_w

    Returns:
        dict with keys:
          - predicted_power_w: float or None
          - model_name: str
          - model_ready: bool
          - error: str or None
          - timestamp: ISO-8601 string
          - features_used: list of feature names
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if not model_loader.is_model_ready():
        # Try loading if not yet attempted with config
        if config is not None:
            model_loader.load_model(config)

    if not model_loader.is_model_ready():
        error = model_loader.get_load_error() or "Model not loaded."
        return {
            "predicted_power_w": None,
            "model_name": None,
            "model_ready": False,
            "error": error,
            "timestamp": timestamp,
            "features_used": [],
            "dataset_type": None,
        }

    try:
        model = model_loader.get_model()
        pipeline = model_loader.get_pipeline()
        metadata = model_loader.get_metadata() or {}

        # Prepare features using the same function as training
        features_df = snapshot_to_features(snapshot)
        features_df = features_df.replace([np.inf, -np.inf], np.nan)

        # The training pipeline owns missing-value imputation. Never replace an
        # unavailable GPU reading with zero: pass it as NaN so the fitted imputer
        # uses its training-only median, and disclose that reduced-evidence path.
        non_finite = ~np.isfinite(features_df.to_numpy(dtype=float))
        missing_features = features_df.columns[non_finite.any(axis=0)].tolist()

        # Apply the fitted preprocessing pipeline (e.g. StandardScaler)
        features_scaled = pipeline.transform(features_df)

        # Model prediction
        raw_prediction = model.predict(features_scaled)[0]
        if not np.isfinite(raw_prediction):
            raise ValueError("Model returned a non-finite power estimate")

        # Clamp to physically plausible range (≥ 0 W, ≤ 2000 W for a desktop/laptop)
        predicted_power_w = float(max(0.0, min(raw_prediction, 2000.0)))

        logger.debug(
            f"Power prediction: {predicted_power_w:.2f} W "
            f"(raw={raw_prediction:.2f} W)"
        )

        warnings = []
        if missing_features:
            warnings.append(
                "Some telemetry is unavailable; the model used training-set median "
                f"imputation for {', '.join(missing_features)}. Treat this as a lower-confidence estimate."
            )
        if metadata.get("dataset_type") == "synthetic_model_generated":
            warnings.append(
                "Prototype model trained on synthetic targets; real-world power accuracy is unknown."
            )

        return {
            "predicted_power_w": round(predicted_power_w, 2),
            "model_name": metadata.get("model_name", "unknown"),
            "model_ready": True,
            "error": None,
            "timestamp": timestamp,
            "features_used": metadata.get("features", []),
            "dataset_type": metadata.get("dataset_type", "legacy_unknown"),
            "imputed_features": missing_features,
            "warnings": warnings,
            "estimate_quality": "reduced" if missing_features else "prototype",
        }

    except Exception as e:
        error_msg = f"Prediction failed: {e}"
        logger.error(error_msg)
        return {
            "predicted_power_w": None,
            "model_name": None,
            "model_ready": False,
            "error": error_msg,
            "timestamp": timestamp,
            "features_used": [],
            "dataset_type": None,
        }

