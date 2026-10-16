"""
Unit tests for recommendation engine rules.
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
from app.services.recommendation_service import (
    generate_recommendations,
    HIGH_CPU_THRESHOLD,
    HIGH_CARBON_INTENSITY,
    SUSTAINED_HIGH_CPU_READINGS,
    ENERGY_COMPARISON_THRESHOLD,
)


def make_snapshot(cpu_pct=30.0, process_name="idle"):
    return TelemetrySnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        collection_interval_s=5.0,
        cpu=CPUMetrics(cpu_pct, 2800, 20, 10, 70, 8),
        memory=MemoryMetrics(16384, 8192, 8192, 50.0),
        disk=DiskMetrics(0.1, 0.1),
        network=NetworkMetrics(0.01, 0.1),
        gpu=GPUMetrics(available=False),
        process_count=50,
        top_processes=[ProcessInfo(process_name, 1234, cpu_pct, 200.0)],
    )


def test_no_recommendations_when_no_session():
    """No session → no recommendations."""
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(),
        energy_state={},
        carbon_data={},
        session_comparison=None,
        cpu_history=[],
        session_active=False,
    )
    assert recs == []


def test_high_impact_workload_detection():
    """Sustained high CPU should trigger high-impact recommendation."""
    cpu_history = [HIGH_CPU_THRESHOLD + 5] * SUSTAINED_HIGH_CPU_READINGS
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(cpu_pct=HIGH_CPU_THRESHOLD + 5),
        energy_state={"current_power_w": 120.0, "average_power_w": 115.0},
        carbon_data={"carbon_intensity_g_per_kwh": 300.0, "status": "live"},
        session_comparison=None,
        cpu_history=cpu_history,
        session_active=True,
    )
    rec_ids = [r["id"] for r in recs]
    assert "high_impact_workload" in rec_ids


def test_no_high_impact_with_insufficient_history():
    """Only 3 high readings (< SUSTAINED_HIGH_CPU_READINGS) should not trigger."""
    cpu_history = [HIGH_CPU_THRESHOLD + 5] * 3  # Below required minimum
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(cpu_pct=HIGH_CPU_THRESHOLD + 5),
        energy_state={"current_power_w": 120.0, "average_power_w": 115.0},
        carbon_data={"carbon_intensity_g_per_kwh": 300.0, "status": "live"},
        session_comparison=None,
        cpu_history=cpu_history,
        session_active=True,
    )
    rec_ids = [r["id"] for r in recs]
    assert "high_impact_workload" not in rec_ids


def test_carbon_aware_scheduling_when_high_intensity():
    """High carbon intensity should trigger scheduling recommendation."""
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(cpu_pct=20.0),
        energy_state={},
        carbon_data={
            "carbon_intensity_g_per_kwh": HIGH_CARBON_INTENSITY + 100,
            "status": "live"
        },
        session_comparison=None,
        cpu_history=[20.0] * 10,
        session_active=True,
    )
    rec_ids = [r["id"] for r in recs]
    assert "carbon_aware_scheduling" in rec_ids


def test_no_carbon_scheduling_when_low_intensity():
    """Low carbon intensity should NOT trigger scheduling recommendation."""
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(cpu_pct=20.0),
        energy_state={},
        carbon_data={
            "carbon_intensity_g_per_kwh": HIGH_CARBON_INTENSITY - 100,
            "status": "live"
        },
        session_comparison=None,
        cpu_history=[20.0] * 10,
        session_active=True,
    )
    rec_ids = [r["id"] for r in recs]
    assert "carbon_aware_scheduling" not in rec_ids


def test_historical_comparison_high():
    """Significantly higher energy should trigger comparison recommendation."""
    comparison = {
        "percentage_difference": ENERGY_COMPARISON_THRESHOLD + 10.0,
        "direction": "higher",
        "note": "Current session is consuming 25.0% more energy per hour.",
    }
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(),
        energy_state={},
        carbon_data={"status": "live"},
        session_comparison=comparison,
        cpu_history=[20.0] * 10,
        session_active=True,
    )
    rec_ids = [r["id"] for r in recs]
    assert "historical_comparison" in rec_ids


def test_all_recommendations_have_required_fields():
    """Every recommendation must have id, title, body, severity, icon."""
    cpu_history = [HIGH_CPU_THRESHOLD + 5] * SUSTAINED_HIGH_CPU_READINGS
    recs = generate_recommendations(
        telemetry_snapshot=make_snapshot(cpu_pct=HIGH_CPU_THRESHOLD + 5),
        energy_state={"current_power_w": 120.0},
        carbon_data={
            "carbon_intensity_g_per_kwh": HIGH_CARBON_INTENSITY + 100,
            "status": "live"
        },
        session_comparison=None,
        cpu_history=cpu_history,
        session_active=True,
    )
    required_fields = {"id", "category", "severity", "icon", "title", "body"}
    for rec in recs:
        for field in required_fields:
            assert field in rec, f"Recommendation missing field: {field}"

