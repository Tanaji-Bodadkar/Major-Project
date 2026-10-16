"""
Carbon Intelligence Platform — Static Fallback Carbon Intensity

Used ONLY when both Electricity Maps and Climatiq are unavailable AND
FALLBACK_CARBON_INTENSITY_G_PER_KWH is configured in .env.

This is always clearly labeled in the UI as a fallback value, never as live data.
The value and source are shown to the user.

Sources for documented regional averages (must be configured via .env, not hard-coded):
- India: CEA Annual Report 2022 — 708 gCO₂e/kWh
- UK: DESNZ 2023 — 233 gCO₂e/kWh
- EU average: EEA 2022 — 276 gCO₂e/kWh
- USA average: EPA eGRID 2022 — 386 gCO₂e/kWh
- Global average: IEA 2022 — 436 gCO₂e/kWh
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class FallbackProvider:
    """
    Returns a static configured carbon intensity value.
    Always labeled as fallback — never presented as live data.
    """

    def __init__(self, intensity_g_per_kwh: float, source_description: str):
        self.intensity = intensity_g_per_kwh
        self.source = source_description
        logger.warning(
            f"FallbackProvider initialized: {intensity_g_per_kwh} gCO₂e/kWh "
            f"({source_description}). This is a static value, not live data."
        )

    def get_intensity(self) -> dict:
        """Return static intensity value, clearly labeled as fallback."""
        return {
            "carbon_intensity_g_per_kwh": self.intensity,
            "zone": "static-fallback",
            "source": f"Fallback — {self.source}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "fallback",
            "error": None,
            "fallback_notice": (
                f"Using static fallback value ({self.intensity} gCO₂e/kWh). "
                f"Live carbon intensity APIs are unavailable. "
                f"Source: {self.source}"
            ),
        }

