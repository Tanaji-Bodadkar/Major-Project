"""
Carbon Intelligence Platform — Climatiq Carbon Intensity Provider

Uses the Climatiq API as a secondary fallback for carbon intensity data.
Documentation: https://www.climatiq.io/docs

Required environment variable: CLIMATIQ_API_KEY
"""

import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CLIMATIQ_BASE_URL = "https://beta.api.climatiq.io"
REQUEST_TIMEOUT_S = 10


class ClimatiqProvider:
    """
    Fetches carbon intensity from the Climatiq API.
    Used as a secondary provider if Electricity Maps is unavailable.
    """

    def __init__(self, api_key: str, region: str = "IN"):
        self.api_key = api_key
        # Map Electricity Maps zones to Climatiq region codes where possible
        self.region = self._map_zone_to_region(region)

    def _map_zone_to_region(self, zone: str) -> str:
        """Map Electricity Maps zone codes to Climatiq region codes."""
        mapping = {
            "IN-WE": "IN", "IN-NO": "IN", "IN-SO": "IN", "IN-EA": "IN",
            "IN-NE": "IN", "IN": "IN",
            "GB": "GB",
            "DE": "DE",
            "FR": "FR",
            "US-CAL-CISO": "US",
            "US": "US",
            "AU": "AU",
        }
        return mapping.get(zone, zone.split("-")[0] if "-" in zone else zone)

    def get_intensity(self) -> dict:
        """
        Fetch electricity emission factor from Climatiq.

        Returns:
            dict matching the same schema as ElectricityMapsProvider.get_intensity()
        """
        if not self.api_key:
            return self._error_result("CLIMATIQ_API_KEY not configured.")

        url = f"{CLIMATIQ_BASE_URL}/estimate"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "emission_factor": {
                "activity_id": "electricity-supply_grid-source_residual_mix",
                "region": self.region,
            },
            "parameters": {
                "energy": 1,
                "energy_unit": "kWh",
            },
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_S
            )
            response.raise_for_status()
            data = response.json()

            # Climatiq returns co2e in kg; convert to g per kWh
            co2e_kg = data.get("co2e")
            if co2e_kg is None:
                return self._error_result("Climatiq returned no co2e value.")

            intensity_g_per_kwh = float(co2e_kg) * 1000.0

            result = {
                "carbon_intensity_g_per_kwh": round(intensity_g_per_kwh, 2),
                "zone": self.region,
                "source": "Climatiq",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "live",
                "error": None,
            }
            logger.info(
                f"Climatiq intensity: {intensity_g_per_kwh:.1f} gCO₂e/kWh "
                f"(region={self.region})"
            )
            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            return self._error_result(f"Climatiq HTTP error: {status_code}")
        except requests.exceptions.Timeout:
            return self._error_result("Climatiq API request timed out.")
        except requests.exceptions.ConnectionError:
            return self._error_result("Cannot connect to Climatiq API.")
        except Exception as e:
            return self._error_result(f"Climatiq error: {e}")

    def _error_result(self, error_msg: str) -> dict:
        logger.warning(f"Climatiq provider: {error_msg}")
        return {
            "carbon_intensity_g_per_kwh": None,
            "zone": self.region,
            "source": "Climatiq",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": error_msg,
        }

