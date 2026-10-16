"""
Carbon Intelligence Platform — Feature Engineering / Preprocessing

Converts a TelemetrySnapshot into a feature vector for ML inference.
The same feature set and transformations used during training are applied here.

IMPORTANT: The preprocessing.pkl pipeline (median imputer, StandardScaler) is fit ONLY on
training data. The same fitted pipeline is loaded and applied to live features.
Training and inference MUST use identical feature columns in identical order.
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional

from app.telemetry.base import TelemetrySnapshot

logger = logging.getLogger(__name__)

# ============================================================
# FEATURE SPECIFICATION
# This list defines the canonical feature order.
# It must match the columns used during model training.
# The train.py script also references this list.
# ============================================================
FEATURE_COLUMNS = [
    "cpu_utilization_pct",   # %
    "cpu_frequency_mhz",     # MHz
    "ram_utilization_pct",   # %
    "ram_used_mb",            # MB
    "disk_read_mb_s",         # MB/s
    "disk_write_mb_s",        # MB/s
    "network_sent_mb_s",      # MB/s
    "network_recv_mb_s",      # MB/s
    "gpu_utilization_pct",   # %; missing if unavailable
]

# Preserve unavailable GPU as missing so the fitted training pipeline can impute it.
GPU_UNAVAILABLE_DEFAULT = np.nan


def snapshot_to_features(snapshot: TelemetrySnapshot) -> pd.DataFrame:
    """
    Convert a TelemetrySnapshot into a single-row DataFrame with FEATURE_COLUMNS.

    Unavailable GPU telemetry stays missing. The fitted training pipeline may
    impute it; inference must disclose this lower-confidence estimate because
    the synthetic prototype cannot establish actual power when GPU data is absent.

    Args:
        snapshot: Live telemetry snapshot

    Returns:
        pd.DataFrame with one row and columns matching FEATURE_COLUMNS
    """
    gpu_util = (
        snapshot.gpu.utilization_pct
        if snapshot.gpu.available and snapshot.gpu.utilization_pct is not None
        else GPU_UNAVAILABLE_DEFAULT
    )

    row = {
        "cpu_utilization_pct": snapshot.cpu.utilization_pct,
        "cpu_frequency_mhz": snapshot.cpu.frequency_mhz,
        "ram_utilization_pct": snapshot.memory.utilization_pct,
        "ram_used_mb": snapshot.memory.used_mb,
        "disk_read_mb_s": snapshot.disk.read_mb_s,
        "disk_write_mb_s": snapshot.disk.write_mb_s,
        "network_sent_mb_s": snapshot.network.sent_mb_s,
        "network_recv_mb_s": snapshot.network.recv_mb_s,
        "gpu_utilization_pct": gpu_util,
    }

    df = pd.DataFrame([row], columns=FEATURE_COLUMNS)
    for column in FEATURE_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # Clip to valid ranges — prevents extreme outlier inputs from producing absurd predictions
    df["cpu_utilization_pct"] = df["cpu_utilization_pct"].clip(0, 100)
    df["ram_utilization_pct"] = df["ram_utilization_pct"].clip(0, 100)
    df["gpu_utilization_pct"] = df["gpu_utilization_pct"].clip(0, 100)
    df["disk_read_mb_s"] = df["disk_read_mb_s"].clip(lower=0)
    df["disk_write_mb_s"] = df["disk_write_mb_s"].clip(lower=0)
    df["network_sent_mb_s"] = df["network_sent_mb_s"].clip(lower=0)
    df["network_recv_mb_s"] = df["network_recv_mb_s"].clip(lower=0)

    return df


def dict_to_features(telemetry_dict: dict) -> pd.DataFrame:
    """
    Convert a flat telemetry dictionary (e.g. from CSV) into a feature DataFrame.
    Used during ML training to prepare dataset rows.
    """
    row = {
        col: (float(telemetry_dict[col]) if telemetry_dict.get(col) is not None else np.nan)
        for col in FEATURE_COLUMNS
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def prepare_training_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare a training DataFrame by selecting and cleaning feature columns.

    Args:
        df: Raw loaded dataset with at least the FEATURE_COLUMNS present

    Returns:
        DataFrame with exactly FEATURE_COLUMNS, cleaned
    """
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Training dataset is missing required feature columns: {missing}. "
            f"Check docs/dataset.md for the column mapping."
        )

    X = df[FEATURE_COLUMNS].copy()
    for column in FEATURE_COLUMNS:
        X[column] = pd.to_numeric(X[column], errors="coerce")

    # Preserve missingness; the fitted training-only sklearn imputer handles
    # supported missing numeric values after the holdout split.

    # Clip to valid ranges
    X["cpu_utilization_pct"] = X["cpu_utilization_pct"].clip(0, 100)
    X["ram_utilization_pct"] = X["ram_utilization_pct"].clip(0, 100)
    X["gpu_utilization_pct"] = X["gpu_utilization_pct"].clip(0, 100)
    X["disk_read_mb_s"] = X["disk_read_mb_s"].clip(lower=0)
    X["disk_write_mb_s"] = X["disk_write_mb_s"].clip(lower=0)
    X["network_sent_mb_s"] = X["network_sent_mb_s"].clip(lower=0)
    X["network_recv_mb_s"] = X["network_recv_mb_s"].clip(lower=0)

    return X

