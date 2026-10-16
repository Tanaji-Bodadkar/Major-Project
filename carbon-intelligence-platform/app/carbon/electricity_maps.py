"""
Carbon Intelligence Platform — Electricity Maps Carbon Intensity Provider

Fetches real-time grid carbon intensity from the Electricity Maps API v3.
Documentation: https://docs.electricitymap.org/api-reference/v3

Required environment variable: ELECTRICITY_MAPS_API_KEY
Required environment variable: CARBON_ZONE (e.g. 'IN-WE', 'GB', 'DE')
"""

import logging
import requests
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

ELECTRICITY_MAPS_BASE_URL = "https://api.electricitymap.org/v3"
REQUEST_TIMEOUT_S = 10


class ElectricityMapsProvider:
    """
    Fetches carbon intensity from Electricity Maps API v3.

    Returns carbon intensity in gCO₂eq/kWh.
    Source: https://www.electricitymaps.com/
    """

    def __init__(self, api_key: str, zone: str):
        self.api_key = api_key
        self.zone = zone
        self._cached_result: Optional[dict] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 900  # 15 minutes (matches API update frequency)

    def get_intensity(self) -> dict:
        """
        Fetch or return cached carbon intensity.

        Returns:
            dict with keys:
              - carbon_intensity_g_per_kwh: float
              - zone: str
              - source: str
              - timestamp: ISO-8601 str
              - status: 'live' or error description
        """
        # Check cache
        if self._cached_result and self._cache_timestamp:
            age = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
            if age < self._cache_ttl_seconds:
                logger.debug(f"Using cached carbon intensity (age={age:.0f}s)")
                return self._cached_result

        return self._fetch()

    def _fetch(self) -> dict:
        """Make the API request."""
        if not self.api_key:
            return {
                "carbon_intensity_g_per_kwh": None,
                "zone": self.zone,
                "source": "ElectricityMaps",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "error",
                "error": "ELECTRICITY_MAPS_API_KEY not configured.",
            }

        url = f"{ELECTRICITY_MAPS_BASE_URL}/carbon-intensity/latest"
        params = {"zone": self.zone}
        headers = {"auth-token": self.api_key}

        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_S
            )
            response.raise_for_status()
            data = response.json()

            intensity = data.get("carbonIntensity")
            if intensity is None:
                return self._error_result("API returned no carbonIntensity value.")

            result = {
                "carbon_intensity_g_per_kwh": float(intensity),
                "zone": data.get("zone", self.zone),
                "source": "ElectricityMaps",
                "timestamp": data.get("datetime", datetime.now(timezone.utc).isoformat()),
                "status": "live",
                "error": None,
            }

            self._cached_result = result
            self._cache_timestamp = datetime.now(timezone.utc)
            logger.info(
                f"Carbon intensity: {intensity} gCO₂e/kWh "
                f"(zone={result['zone']}, source=ElectricityMaps)"
            )
            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            if status_code == 401:
                error_msg = "Invalid Electricity Maps API key (HTTP 401)."
            elif status_code == 404:
                error_msg = f"Zone '{self.zone}' not found in Electricity Maps (HTTP 404)."
            else:
                error_msg = f"Electricity Maps API HTTP error: {status_code}"
            logger.warning(error_msg)
            return self._error_result(error_msg)

        except requests.exceptions.Timeout:
            error_msg = "Electricity Maps API request timed out."
            logger.warning(error_msg)
            return self._error_result(error_msg)

        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to Electricity Maps API (network error)."
            logger.warning(error_msg)
            return self._error_result(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error fetching carbon intensity: {e}"
            logger.error(error_msg)
            return self._error_result(error_msg)

    def _error_result(self, error_msg: str) -> dict:
        return {
            "carbon_intensity_g_per_kwh": None,
            "zone": self.zone,
            "source": "ElectricityMaps",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": error_msg,
        }

