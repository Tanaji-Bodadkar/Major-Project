"""
Carbon Intelligence Platform — What-If Analysis Engine

Calculates projected energy and CO₂e for hypothetical additional workload durations.

All outputs are clearly labeled as projected estimates, not actual measurements.
"""

import logging
import math

logger = logging.getLogger(__name__)


def calculate_what_if(
    power_w: float,
    additional_hours: float,
    carbon_intensity_g_per_kwh: float,
) -> dict:
    """
    Calculate projected additional energy and CO₂e for a given duration.

    Formula:
        additional_energy_wh = power_w × additional_hours
        additional_energy_kwh = additional_energy_wh / 1000
        additional_co2e_g = additional_energy_kwh × carbon_intensity_g_per_kwh

    Args:
        power_w: Assumed power level in Watts (e.g. current predicted power)
        additional_hours: Duration in decimal hours
        carbon_intensity_g_per_kwh: Carbon intensity in gCO₂e/kWh

    Returns:
        dict with projected values, all labeled as estimates
    """
    values = (power_w, additional_hours, carbon_intensity_g_per_kwh)
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Power, duration, and carbon intensity must be finite non-negative values")

    additional_energy_wh = power_w * additional_hours
    additional_energy_kwh = additional_energy_wh / 1000.0
    additional_co2e_g = additional_energy_kwh * carbon_intensity_g_per_kwh
    additional_co2e_kg = additional_co2e_g / 1000.0

    # Format duration for display
    total_minutes = additional_hours * 60
    if total_minutes < 60:
        duration_display = f"{total_minutes:.0f} minutes"
    else:
        h = int(total_minutes // 60)
        m = int(total_minutes % 60)
        duration_display = f"{h}h {m:02d}m" if m > 0 else f"{h}h"

    return {
        "is_projected_estimate": True,  # Always True — these are never actual measurements
        "input_power_w": round(power_w, 2),
        "input_additional_hours": additional_hours,
        "input_carbon_intensity_g_per_kwh": carbon_intensity_g_per_kwh,
        "projected_additional_energy_wh": round(additional_energy_wh, 4),
        "projected_additional_energy_kwh": round(additional_energy_kwh, 6),
        "projected_additional_co2e_g": round(additional_co2e_g, 4),
        "projected_additional_co2e_kg": round(additional_co2e_kg, 6),
        "duration_display": duration_display,
        "disclaimer": (
            "These values are projected estimates based on the assumed power level "
            "remaining constant for the specified duration. Actual values will differ "
            "based on real workload variation and grid carbon intensity changes."
        ),
    }

