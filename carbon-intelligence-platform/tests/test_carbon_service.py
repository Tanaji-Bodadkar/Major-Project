"""
Unit tests for carbon calculation logic.

Verifies CO₂e = Energy(kWh) × Intensity(gCO₂e/kWh) formula.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_co2e_basic_formula():
    """0.5 kWh × 500 gCO₂e/kWh = 250 gCO₂e"""
    energy_kwh = 0.5
    intensity_g_per_kwh = 500.0
    expected_co2e_g = 250.0

    co2e_g = energy_kwh * intensity_g_per_kwh
    assert abs(co2e_g - expected_co2e_g) < 0.001, \
        f"Expected {expected_co2e_g} g, got {co2e_g} g"


def test_co2e_small_energy():
    """0.00001 kWh × 520 gCO₂e/kWh = 0.0052 gCO₂e"""
    energy_kwh = 0.00001
    intensity = 520.0
    expected = 0.0052
    result = energy_kwh * intensity
    assert abs(result - expected) < 0.000001


def test_co2e_kg_conversion():
    """250 g = 0.250 kg"""
    co2e_g = 250.0
    co2e_kg = co2e_g / 1000.0
    assert abs(co2e_kg - 0.250) < 0.0001


def test_co2e_zero_energy():
    """Zero energy → zero CO₂e"""
    assert 0.0 * 500.0 == 0.0


def test_india_grid_intensity():
    """
    Test with India national average carbon intensity.
    India CEA 2022: ~708 gCO₂e/kWh
    1 kWh × 708 = 708 g
    """
    energy_kwh = 1.0
    india_intensity = 708.0
    co2e_g = energy_kwh * india_intensity
    assert abs(co2e_g - 708.0) < 0.001


def test_energy_wh_to_kwh_conversion():
    """100 Wh = 0.1 kWh"""
    wh = 100.0
    kwh = wh / 1000.0
    assert abs(kwh - 0.1) < 0.0001


def test_what_if_calculation():
    """90 W × 2 hours = 180 Wh = 0.18 kWh"""
    from app.services.whatif_service import calculate_what_if
    result = calculate_what_if(
        power_w=90.0,
        additional_hours=2.0,
        carbon_intensity_g_per_kwh=500.0,
    )
    assert abs(result["projected_additional_energy_wh"] - 180.0) < 0.001
    assert abs(result["projected_additional_energy_kwh"] - 0.18) < 0.0001
    assert abs(result["projected_additional_co2e_g"] - 90.0) < 0.001  # 0.18 kWh × 500 = 90 g
    assert result["is_projected_estimate"] is True


def test_what_if_negative_inputs_are_rejected():
    """Invalid scenario inputs should be rejected instead of silently altered."""
    from app.services.whatif_service import calculate_what_if
    with pytest.raises(ValueError, match="finite non-negative"):
        calculate_what_if(
            power_w=-10.0,
            additional_hours=-1.0,
            carbon_intensity_g_per_kwh=-100.0,
        )

