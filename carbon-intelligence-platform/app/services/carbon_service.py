"""
Carbon Intelligence Platform — Carbon Service

Orchestrates carbon intensity provider selection and CO₂e calculation.

Provider priority:
1. Electricity Maps (primary — live, real-time grid data)
2. Climatiq (secondary — fallback if EM unavailable)
3. Static fallback (only if configured in .env and both APIs fail)

CO₂e calculation:
    co2e_g = energy_kwh × carbon_intensity_g_per_kwh
"""

import os
import csv
import json
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from app.carbon.electricity_maps import ElectricityMapsProvider
from app.carbon.climatiq import ClimatiqProvider
from app.carbon.fallback import FallbackProvider

logger = logging.getLogger(__name__)


class CarbonService:
    """
    Manages carbon intensity fetching and CO₂e calculations.

    Usage:
        service = CarbonService(config)
        intensity = service.get_intensity()
        co2e = service.calculate_co2e(energy_kwh=0.5)
    """

    def __init__(self, config):
        self.config = config
        self.emissions_dir = config.EMISSIONS_DIR

        # Initialize providers
        self._em_provider = ElectricityMapsProvider(
            api_key=config.ELECTRICITY_MAPS_API_KEY,
            zone=config.CARBON_ZONE,
        )
        self._climatiq_provider = ClimatiqProvider(
            api_key=config.CLIMATIQ_API_KEY,
            region=config.CARBON_ZONE,
        )

        # Static fallback — only if configured
        self._fallback_provider: Optional[FallbackProvider] = None
        fallback_value = config.FALLBACK_CARBON_INTENSITY_G_PER_KWH
        fallback_source = config.FALLBACK_CARBON_SOURCE
        if fallback_value and fallback_source:
            try:
                self._fallback_provider = FallbackProvider(
                    intensity_g_per_kwh=float(fallback_value),
                    source_description=fallback_source,
                )
            except ValueError:
                logger.warning(
                    f"Invalid FALLBACK_CARBON_INTENSITY_G_PER_KWH: {fallback_value}"
                )

        self._latest_intensity: Optional[dict] = None
        self._intensity_cache_until = 0.0
        self._intensity_lock = threading.Lock()
        self._session_co2e_g = 0.0
        self._session_covered_energy_wh = 0.0
        self._session_uncovered_energy_wh = 0.0
        self._session_sources = set()
        self._last_session_intensity = None

    def reset_session_emissions(self):
        self._session_co2e_g = 0.0
        self._session_covered_energy_wh = 0.0
        self._session_uncovered_energy_wh = 0.0
        self._session_sources = set()
        self._last_session_intensity = None

    def record_energy_interval(self, energy_wh: float, intensity_data: dict):
        """Accumulate emissions using the intensity available for this energy interval."""
        if energy_wh is None or not math.isfinite(energy_wh) or energy_wh < 0:
            raise ValueError("energy_wh must be a finite non-negative number")
        if energy_wh == 0:
            return
        intensity = (intensity_data or {}).get("carbon_intensity_g_per_kwh")
        if intensity is None or not math.isfinite(float(intensity)) or float(intensity) < 0:
            self._session_uncovered_energy_wh += energy_wh
            return
        emissions_g = (energy_wh / 1000.0) * float(intensity)
        self._session_covered_energy_wh += energy_wh
        self._session_co2e_g += emissions_g
        self._session_sources.add((intensity_data.get("source"), intensity_data.get("status")))
        self._last_session_intensity = dict(intensity_data)

    def get_session_emissions(self) -> dict:
        complete = self._session_uncovered_energy_wh <= 1e-12
        if complete:
            status = "complete"
            if any(source_status == "fallback" for _, source_status in self._session_sources):
                status = "fallback"
        else:
            status = "partial"
        known_co2e = round(self._session_co2e_g, 4)
        return {
            "co2e_g": known_co2e if complete else None,
            "co2e_kg": round(known_co2e / 1000.0, 6) if complete else None,
            "partial_co2e_g": known_co2e,
            "covered_energy_wh": round(self._session_covered_energy_wh, 6),
            "uncovered_energy_wh": round(self._session_uncovered_energy_wh, 6),
            "energy_weighted_intensity_g_per_kwh": (
                round(self._session_co2e_g / (self._session_covered_energy_wh / 1000.0), 4)
                if self._session_covered_energy_wh > 0 else None
            ),
            "latest_intensity": dict(self._last_session_intensity) if self._last_session_intensity else None,
            "status": status,
            "sources": [source for source, _ in sorted(self._session_sources) if source],
            "error": "Some energy intervals had no carbon intensity; full-session CO₂e is unavailable." if not complete else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_intensity(self) -> dict:
        """
        Get current carbon intensity from the best available source.

        Returns a dict with carbon_intensity_g_per_kwh, zone, source,
        timestamp, status, and optionally fallback_notice and error.
        """
        with self._intensity_lock:
            now = time.monotonic()
            if self._latest_intensity is not None and now < self._intensity_cache_until:
                return dict(self._latest_intensity)

            result = self._em_provider.get_intensity()
            if result.get("status") == "live":
                self._latest_intensity = result
                self._intensity_cache_until = now + 900
                return dict(result)
            em_error = result.get("error", "Unknown error")
            logger.info("Electricity Maps unavailable: %s. Trying Climatiq...", em_error)

            result = self._climatiq_provider.get_intensity()
            if result.get("status") == "live":
                self._latest_intensity = result
                self._intensity_cache_until = now + 900
                return dict(result)
            climatiq_error = result.get("error", "Unknown error")
            logger.info("Climatiq unavailable: %s. Checking static fallback...", climatiq_error)

            if self._fallback_provider:
                result = self._fallback_provider.get_intensity()
                self._latest_intensity = result
                self._intensity_cache_until = now + 900
                return dict(result)

            error_result = {
                "carbon_intensity_g_per_kwh": None,
                "zone": self.config.CARBON_ZONE,
                "source": "None",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "unavailable",
                "error": (
                    f"All carbon intensity sources unavailable. Electricity Maps: {em_error}. "
                    f"Climatiq: {climatiq_error}. No fallback configured."
                ),
            }
            self._latest_intensity = error_result
            self._intensity_cache_until = now + 60
            return dict(error_result)

    def get_latest_intensity(self) -> Optional[dict]:
        """Return the last successfully fetched intensity (may be cached)."""
        return dict(self._latest_intensity) if self._latest_intensity is not None else None

    def calculate_co2e(self, energy_kwh: float) -> dict:
        """
        Calculate CO₂e from energy consumption.

        Args:
            energy_kwh: Energy in kilowatt-hours

        Returns:
            dict with co2e_g, co2e_kg, energy_kwh, intensity details
        """
        intensity_data = self.get_intensity()
        intensity_g_per_kwh = intensity_data.get("carbon_intensity_g_per_kwh")

        if intensity_g_per_kwh is None:
            return {
                "co2e_g": None,
                "co2e_kg": None,
                "energy_kwh": energy_kwh,
                "carbon_intensity_g_per_kwh": None,
                "source": intensity_data.get("source"),
                "status": "unavailable",
                "error": intensity_data.get("error"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        co2e_g = energy_kwh * intensity_g_per_kwh
        co2e_kg = co2e_g / 1000.0

        return {
            "co2e_g": round(co2e_g, 4),
            "co2e_kg": round(co2e_kg, 6),
            "energy_kwh": energy_kwh,
            "carbon_intensity_g_per_kwh": intensity_g_per_kwh,
            "carbon_intensity_unit": "gCO2e/kWh",
            "source": intensity_data.get("source"),
            "zone": intensity_data.get("zone"),
            "intensity_timestamp": intensity_data.get("timestamp"),
            "status": intensity_data.get("status"),
            "fallback_notice": intensity_data.get("fallback_notice"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def save_emission_record(self, record: dict):
        """Save an emission record to the emissions directory."""
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            filepath = os.path.join(self.emissions_dir, f"emissions_{date_str}.jsonl")
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to save emission record: {e}")

