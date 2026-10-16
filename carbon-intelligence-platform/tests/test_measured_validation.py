import numpy as np
import pandas as pd
import pytest
import csv
from datetime import datetime, timezone

from app.ml.evaluate_measured import evaluate_measured_dataset
from app.ml.measured_dataset import align_meter_readings
from app.ml.preprocessing import FEATURE_COLUMNS


def _telemetry_rows(timestamps):
    rows = []
    for i, timestamp in enumerate(timestamps):
        row = {"timestamp": timestamp}
        row.update({feature: float(i + j + 1) for j, feature in enumerate(FEATURE_COLUMNS)})
        rows.append(row)
    return pd.DataFrame(rows)


def test_aligns_meter_readings_by_nearest_timestamp_and_keeps_provenance():
    telemetry = _telemetry_rows([
        "2026-10-16T10:00:00Z",
        "2026-10-16T10:00:05Z",
    ])
    telemetry["session_id"] = ["run-a", "run-b"]
    meter = pd.DataFrame([
        {"timestamp": "2026-10-16T10:00:01Z", "power_w": 42.0, "session_id": "run-a", "workload_label": "idle"},
        {"timestamp": "2026-10-16T10:00:05Z", "power_w": 58.0, "session_id": "run-b", "workload_label": "coding"},
    ])

    aligned, summary = align_meter_readings(telemetry, meter, tolerance_s=2.5)

    assert aligned["measured_power_w"].tolist() == [42.0, 58.0]
    assert aligned["session_id"].tolist() == ["run-a", "run-b"]
    assert aligned["meter_match_offset_seconds"].tolist() == [1.0, 0.0]
    assert summary["matched_rows"] == 2
    assert summary["unmatched_rows"] == 0


def test_alignment_never_uses_telemetry_from_a_different_session():
    telemetry = _telemetry_rows(["2026-10-16T10:00:00Z"])
    telemetry["session_id"] = ["other-session"]
    meter = pd.DataFrame([{
        "timestamp": "2026-10-16T10:00:00Z",
        "power_w": 40.0,
        "session_id": "target-session",
    }])

    with pytest.raises(ValueError, match="No meter rows matched"):
        align_meter_readings(telemetry, meter)


def test_active_session_telemetry_is_saved_with_session_id(tmp_path, monkeypatch):
    from app.services import telemetry_service as module
    from app.telemetry.base import (
        CPUMetrics, DiskMetrics, GPUMetrics, MemoryMetrics,
        NetworkMetrics, TelemetrySnapshot,
    )

    class Config:
        TELEMETRY_INTERVAL_S = 5.0
        TOP_PROCESS_COUNT = 5
        DATA_DIR = str(tmp_path)
        TELEMETRY_DIR = str(tmp_path / "telemetry")
        MEASURED_DIR = str(tmp_path / "measured")

    class SessionService:
        def get_active_session(self):
            return {"session_id": "run-123"}

    class Provider:
        def __init__(self, **kwargs):
            pass

        def get_snapshot(self):
            return _snapshot()

    def _snapshot():
        return TelemetrySnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            collection_interval_s=5.0,
            cpu=CPUMetrics(45.2, 2800.0, 30.0, 10.0, 60.0, 8),
            memory=MemoryMetrics(16384.0, 8192.0, 8192.0, 50.0),
            disk=DiskMetrics(4.2, 1.1),
            network=NetworkMetrics(0.1, 0.8),
            gpu=GPUMetrics(available=False),
            process_count=0,
            top_processes=[],
        )

    monkeypatch.setattr(module, "WindowsTelemetryProvider", Provider)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    (tmp_path / "telemetry").mkdir()
    service = module.TelemetryService(Config(), session_service=SessionService())
    snapshot = _snapshot()
    service._save_to_csv(snapshot)

    output = tmp_path / "measured" / f"telemetry_{pd.Timestamp.utcnow():%Y%m%d}.csv"
    # The timestamp's date, not file-system modification time, determines the daily path.
    assert output.exists()
    with output.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))
    assert row["session_id"] == "run-123"
    assert row["cpu_utilization_pct"] == "45.2"


def test_alignment_rejects_timezone_naive_timestamps():
    telemetry = _telemetry_rows(["2026-10-16T10:00:00Z"])
    meter = pd.DataFrame([{
        "timestamp": "2026-10-16T10:00:00",
        "power_w": 40.0,
        "session_id": "run-a",
    }])

    with pytest.raises(ValueError, match="UTC offset"):
        align_meter_readings(telemetry, meter)


def test_measured_evaluation_holds_out_entire_sessions():
    rows = []
    for session_num in range(5):
        for sample in range(12):
            row = {
                "session_id": f"session-{session_num}",
                "measured_power_w": 30 + session_num * 2 + sample,
                "workload_label": "idle" if sample < 6 else "coding",
            }
            row.update({feature: float(session_num + sample + index) for index, feature in enumerate(FEATURE_COLUMNS)})
            rows.append(row)
    data = pd.DataFrame(rows)

    report, model, features = evaluate_measured_dataset(data)

    assert set(report["training_sessions"]).isdisjoint(report["held_out_sessions"])
    assert set(report["fit_sessions_before_validation"]).isdisjoint(report["validation_sessions"])
    assert set(report["validation_sessions"]).isdisjoint(report["held_out_sessions"])
    assert report["evaluation_type"] == "real_meter_group_holdout"
    assert report["held_out_sessions"]
    assert set(report["workload_metrics"]) == {"idle", "coding"}
    assert report["selected_model"] != "MedianBaseline"
    assert model is not None
    assert features

