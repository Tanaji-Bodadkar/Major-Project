"""
Unit tests for telemetry parsing and data structures.
"""

import sys
import os
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.telemetry.base import (
    CPUMetrics, MemoryMetrics, DiskMetrics, NetworkMetrics,
    GPUMetrics, ProcessInfo, TelemetrySnapshot
)


def make_test_snapshot() -> TelemetrySnapshot:
    """Create a minimal valid snapshot for testing."""
    return TelemetrySnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        collection_interval_s=5.0,
        cpu=CPUMetrics(
            utilization_pct=45.2,
            frequency_mhz=2800.0,
            user_pct=30.0,
            privileged_pct=10.0,
            idle_pct=60.0,
            logical_count=8,
        ),
        memory=MemoryMetrics(
            total_mb=16384.0,
            available_mb=8192.0,
            used_mb=8192.0,
            utilization_pct=50.0,
        ),
        disk=DiskMetrics(read_mb_s=4.2, write_mb_s=1.1),
        network=NetworkMetrics(sent_mb_s=0.1, recv_mb_s=0.8),
        gpu=GPUMetrics(
            available=False,
            unavailability_reason="No WMI GPU counter available.",
        ),
        process_count=120,
        top_processes=[
            ProcessInfo(name="chrome.exe", pid=1234, cpu_pct=12.5, memory_mb=512.0),
        ],
    )


def test_snapshot_to_dict():
    """Snapshot should serialize to a valid dict."""
    snap = make_test_snapshot()
    d = snap.to_dict()
    assert "cpu" in d
    assert "memory" in d
    assert "disk" in d
    assert "network" in d
    assert "gpu" in d
    assert "processes" in d
    assert d["cpu"]["utilization_pct"] == 45.2
    assert d["gpu"]["available"] is False


def test_snapshot_to_csv_row():
    """CSV row should contain expected flat keys."""
    snap = make_test_snapshot()
    row = snap.to_csv_row()
    assert "cpu_utilization_pct" in row
    assert "ram_used_mb" in row
    assert "disk_read_mb_s" in row
    assert row["gpu_available"] is False
    assert row["gpu_utilization_pct"] == ""  # empty when unavailable


def test_gpu_unavailable_not_crashes():
    """GPU unavailability should not crash the snapshot creation."""
    snap = make_test_snapshot()
    assert snap.gpu.available is False
    assert snap.gpu.utilization_pct is None


def test_snapshot_gpu_available():
    """Test snapshot with GPU available."""
    snap = make_test_snapshot()
    snap.gpu = GPUMetrics(
        available=True,
        utilization_pct=55.0,
        memory_used_mb=2048.0,
        memory_total_mb=8192.0,
    )
    d = snap.to_dict()
    assert d["gpu"]["available"] is True
    assert d["gpu"]["utilization_pct"] == 55.0


def test_preprocessing_snapshot_to_features():
    """Feature engineering should produce correct columns."""
    from app.ml.preprocessing import snapshot_to_features, FEATURE_COLUMNS
    snap = make_test_snapshot()
    features_df = snapshot_to_features(snap)
    assert list(features_df.columns) == FEATURE_COLUMNS
    assert features_df["cpu_utilization_pct"].values[0] == 45.2
    assert features_df["gpu_utilization_pct"].isna().values[0]  # unknown stays unknown


def test_preprocessing_gpu_available_uses_real_value():
    """When GPU is available, its real value should be used."""
    from app.ml.preprocessing import snapshot_to_features
    snap = make_test_snapshot()
    snap.gpu = GPUMetrics(available=True, utilization_pct=67.5, memory_used_mb=1024.0)
    features_df = snapshot_to_features(snap)
    assert features_df["gpu_utilization_pct"].values[0] == 67.5


def test_feature_clipping():
    """Features should be clipped to valid ranges."""
    from app.ml.preprocessing import snapshot_to_features
    snap = make_test_snapshot()
    snap.cpu = snap.cpu.__class__(
        utilization_pct=105.0,  # Invalid — should clip to 100
        frequency_mhz=2800.0,
        user_pct=30.0, privileged_pct=10.0, idle_pct=0.0, logical_count=8,
    )
    features_df = snapshot_to_features(snap)
    assert features_df["cpu_utilization_pct"].values[0] <= 100.0

