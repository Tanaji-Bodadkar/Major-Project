"""
Carbon Intelligence Platform — ML Model Loader

Loads and caches the trained power estimation model and preprocessing pipeline.
Provides a singleton pattern so the model is only loaded once per application lifetime.
"""

import os
import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

_model = None
_pipeline = None
_metadata = None
_load_error: Optional[str] = None
_loaded = False


def load_model(config) -> bool:
    """
    Load the model, preprocessing pipeline, and metadata from disk.

    Returns:
        True if loading succeeded, False otherwise.
    """
    global _model, _pipeline, _metadata, _load_error, _loaded

    if _loaded:
        return _load_error is None

    try:
        import joblib

        model_path = config.MODEL_FILE
        pipeline_path = config.PREPROCESSING_FILE
        metadata_path = config.METADATA_FILE

        # Verify files exist before loading
        missing = []
        for path in [model_path, pipeline_path, metadata_path]:
            if not os.path.isfile(path):
                missing.append(path)

        if missing:
            _load_error = (
                f"Model artifacts not found: {missing}. "
                f"Run 'python -m app.ml.train' to train the model first."
            )
            logger.warning(_load_error)
            _loaded = True
            return False

        _model = joblib.load(model_path)
        _pipeline = joblib.load(pipeline_path)

        with open(metadata_path, "r", encoding="utf-8") as f:
            _metadata = json.load(f)

        from app.ml.preprocessing import FEATURE_COLUMNS
        if _metadata.get("features") != FEATURE_COLUMNS:
            raise ValueError("Model metadata feature names/order do not match live preprocessing")
        if _model is None or _pipeline is None:
            raise ValueError("Model or preprocessing artifact is empty")

        logger.info(
            f"Model loaded: {_metadata.get('model_name', 'unknown')} "
            f"(R²={_metadata.get('metrics', {}).get('r2', 'N/A')}, "
            f"RMSE={_metadata.get('metrics', {}).get('rmse_w', 'N/A')} W)"
        )
        _load_error = None
        _loaded = True
        return True

    except Exception as e:
        _load_error = f"Failed to load model: {e}"
        logger.error(_load_error)
        _loaded = True
        return False


def get_model():
    """Return the loaded sklearn model, or None if not loaded."""
    return _model


def get_pipeline():
    """Return the loaded preprocessing pipeline, or None if not loaded."""
    return _pipeline


def get_metadata() -> Optional[dict]:
    """Return model metadata dict, or None if not loaded."""
    return _metadata


def get_load_error() -> Optional[str]:
    """Return the error message if model loading failed, or None."""
    return _load_error


def is_model_ready() -> bool:
    """Return True if model and pipeline are both loaded and ready."""
    return _load_error is None and _model is not None and _pipeline is not None


def reset():
    """Reset the loader state (used in tests)."""
    global _model, _pipeline, _metadata, _load_error, _loaded
    _model = None
    _pipeline = None
    _metadata = None
    _load_error = None
    _loaded = False

