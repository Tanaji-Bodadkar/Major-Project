"""
Carbon Intelligence Platform — Prediction Service

Connects telemetry → feature engineering → ML model → predicted power.
Also manages the prediction log CSV.
"""

import os
import csv
import logging
import threading
import copy
from datetime import datetime, timezone
from typing import Optional

from app.ml import model_loader
from app.ml.predict import predict_power
from app.telemetry.base import TelemetrySnapshot

logger = logging.getLogger(__name__)

PREDICTION_CSV_COLUMNS = [
    "timestamp", "predicted_power_w", "model_name",
    "cpu_utilization_pct", "ram_utilization_pct", "gpu_utilization_pct",
]


class PredictionService:
    """
    Manages power predictions from live telemetry.

    Loads the ML model on first call and caches it.
    Logs predictions to CSV.
    """

    def __init__(self, config):
        self.config = config
        self.predictions_dir = config.PREDICTIONS_DIR
        self._model_initialized = False
        self._prediction_lock = threading.Lock()
        self._last_snapshot_timestamp = None
        self._last_snapshot_result = None

    def _ensure_model_loaded(self):
        """Lazily load the model on first prediction call."""
        if not self._model_initialized:
            model_loader.load_model(self.config)
            self._model_initialized = True

    def predict(self, snapshot: TelemetrySnapshot) -> dict:
        """
        Generate a power prediction from a telemetry snapshot.

        Args:
            snapshot: Current telemetry snapshot

        Returns:
            Prediction result dict
        """
        with self._prediction_lock:
            if snapshot.timestamp == self._last_snapshot_timestamp and self._last_snapshot_result is not None:
                return copy.deepcopy(self._last_snapshot_result)
            self._ensure_model_loaded()
            result = predict_power(snapshot, config=self.config)
            result["telemetry_timestamp"] = snapshot.timestamp
            if result.get("predicted_power_w") is not None:
                self._save_prediction(snapshot, result)
            self._last_snapshot_timestamp = snapshot.timestamp
            self._last_snapshot_result = copy.deepcopy(result)
            return result

    def _save_prediction(self, snapshot: TelemetrySnapshot, result: dict):
        """Append prediction to daily CSV log."""
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            csv_path = os.path.join(
                self.predictions_dir, f"predictions_{date_str}.csv"
            )
            row = {
                "timestamp": result.get("telemetry_timestamp", snapshot.timestamp),
                "predicted_power_w": result["predicted_power_w"],
                "model_name": result.get("model_name", ""),
                "cpu_utilization_pct": snapshot.cpu.utilization_pct,
                "ram_utilization_pct": snapshot.memory.utilization_pct,
                "gpu_utilization_pct": (
                    snapshot.gpu.utilization_pct if snapshot.gpu.available else ""
                ),
            }
            file_exists = os.path.isfile(csv_path)
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=PREDICTION_CSV_COLUMNS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
        except Exception as e:
            logger.debug(f"Failed to save prediction to CSV: {e}")

    def get_model_status(self) -> dict:
        """Return current model loading status."""
        self._ensure_model_loaded()
        metadata = model_loader.get_metadata() or {}
        return {
            "model_ready": model_loader.is_model_ready(),
            "model_name": metadata.get("model_name"),
            "features": metadata.get("features", []),
            "metrics": metadata.get("metrics", {}),
            "training_date": metadata.get("training_date"),
            "dataset_type": metadata.get("dataset_type", "legacy_unknown"),
            "hardware_validation_performed": metadata.get("hardware_validation_performed", False),
            "error": model_loader.get_load_error(),
        }

