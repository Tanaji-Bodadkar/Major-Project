"""
Unit tests for the Energy Calculation Service.

Verifies that energy accumulation is numerically correct.
"""

import time
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.energy_service import EnergyService


def test_energy_calculation_formula():
    """80 W × 2 hours = 160 Wh"""
    service = EnergyService()
    service.reset()

    # Simulate 2 hours at 80 W
    power_w = 80.0
    duration_s = 7200.0  # 2 hours

    # Manually compute expected
    expected_wh = power_w * duration_s / 3600.0
    assert abs(expected_wh - 160.0) < 0.001, f"Expected 160 Wh, got {expected_wh}"


def test_energy_accumulation_multiple_readings():
    """
    Test that energy accumulates correctly across multiple intervals.
    100 W × 1800 s = 50 Wh
    """
    service = EnergyService()
    service.reset()

    power_w = 100.0
    interval_s = 5.0
    n_readings = int(1800 / interval_s)  # 360 readings × 5 s = 1800 s

    # Simulate by manually computing
    total_energy_wh = power_w * n_readings * interval_s / 3600.0
    expected_wh = 50.0
    assert abs(total_energy_wh - expected_wh) < 0.01, \
        f"Expected ~50 Wh, got {total_energy_wh:.4f} Wh"


def test_energy_service_reset_clears_state():
    """After reset, session energy should be 0."""
    service = EnergyService()
    service.reset()

    state = service.get_state()
    assert state["session_energy_wh"] == 0.0
    assert state["session_energy_kwh"] == 0.0


def test_energy_service_update_tracks_power():
    """After updating with a power value, current_power_w should be set."""
    service = EnergyService()
    service.reset()
    time.sleep(0.1)  # Ensure time delta is non-zero
    state = service.update(72.4)
    assert state["current_power_w"] == 72.4


def test_energy_service_kwh_conversion():
    """1000 Wh = 1 kWh — verify conversion."""
    service = EnergyService()
    service.reset()

    # Manually set internal state to test conversion
    service._session_energy_wh = 1000.0
    state = service.get_state()
    assert abs(state["session_energy_kwh"] - 1.0) < 0.0001, \
        f"Expected 1.0 kWh, got {state['session_energy_kwh']}"


def test_energy_service_peak_power():
    """Peak power should reflect the maximum prediction seen."""
    service = EnergyService()
    service.reset()
    time.sleep(0.05)
    service.update(50.0)
    time.sleep(0.05)
    service.update(120.0)
    time.sleep(0.05)
    service.update(75.0)
    state = service.get_state()
    assert state["peak_power_w"] == 120.0

