"""
Carbon Intelligence Platform — Analytics Service

Provides workload analysis, trend data, and cross-session comparisons.
All analytics are derived from actual telemetry and prediction data.
"""

import os
import csv
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Provides analytics derived from telemetry and session history.
    """

    def __init__(self, config):
        self.config = config
        self.telemetry_dir = config.TELEMETRY_DIR
        self.predictions_dir = config.PREDICTIONS_DIR
        self.sessions_file = config.SESSIONS_FILE

    def get_recent_power_trend(self, window_minutes: int = 10) -> dict:
        """
        Load the most recent N minutes of predictions for chart display.

        Returns:
            dict with 'timestamps' and 'power_values' lists
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        timestamps = []
        power_values = []

        try:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            csv_path = os.path.join(
                self.predictions_dir, f"predictions_{date_str}.csv"
            )
            if not os.path.isfile(csv_path):
                return {"timestamps": [], "power_values": [], "window_minutes": window_minutes}

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.fromisoformat(row["timestamp"])
                        if ts >= cutoff:
                            timestamps.append(row["timestamp"])
                            power_values.append(float(row["predicted_power_w"]))
                    except (ValueError, KeyError):
                        continue

        except Exception as e:
            logger.error(f"Error reading power trend: {e}")

        return {
            "timestamps": timestamps,
            "power_values": power_values,
            "window_minutes": window_minutes,
        }

    def get_recent_telemetry_trend(self, window_minutes: int = 10) -> dict:
        """
        Load recent CPU and RAM utilization for chart display.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        timestamps = []
        cpu_values = []
        ram_values = []
        gpu_values = []

        try:
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            csv_path = os.path.join(
                self.telemetry_dir, f"telemetry_{date_str}.csv"
            )
            if not os.path.isfile(csv_path):
                return {
                    "timestamps": [], "cpu_values": [], "ram_values": [],
                    "gpu_values": [], "window_minutes": window_minutes
                }

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts = datetime.fromisoformat(row["timestamp"])
                        if ts >= cutoff:
                            timestamps.append(row["timestamp"])
                            cpu_values.append(float(row.get("cpu_utilization_pct", 0) or 0))
                            ram_values.append(float(row.get("ram_utilization_pct", 0) or 0))
                            gpu_raw = row.get("gpu_utilization_pct", "")
                            gpu_values.append(float(gpu_raw) if gpu_raw else None)
                    except (ValueError, KeyError):
                        continue

        except Exception as e:
            logger.error(f"Error reading telemetry trend: {e}")

        return {
            "timestamps": timestamps,
            "cpu_values": cpu_values,
            "ram_values": ram_values,
            "gpu_values": gpu_values,
            "window_minutes": window_minutes,
        }

    def compare_with_previous_session(
        self, current_energy_kwh: float, current_duration_s: float
    ) -> Optional[dict]:
        """
        Compare the current session's energy-per-hour with the most recent completed session.

        Returns comparison dict or None if no comparable session exists.
        Only compares sessions where duration is at least 5 minutes.
        """
        sessions = self._load_sessions()
        completed = [
            s for s in sessions
            if s.get("end_time") and s.get("total_energy_kwh") and s.get("duration_s", 0) >= 300
        ]

        if not completed:
            return None

        # Most recent completed session
        prev = completed[-1]
        prev_duration_s = prev.get("duration_s", 1)
        prev_energy_kwh = prev.get("total_energy_kwh", 0)

        if prev_duration_s < 1:
            return None

        # Normalize to energy per hour for fair comparison
        current_kwh_per_hour = (current_energy_kwh / max(current_duration_s, 1)) * 3600
        prev_kwh_per_hour = (prev_energy_kwh / prev_duration_s) * 3600

        if prev_kwh_per_hour == 0:
            return None

        pct_diff = ((current_kwh_per_hour - prev_kwh_per_hour) / prev_kwh_per_hour) * 100

        return {
            "previous_session_id": prev.get("session_id"),
            "previous_avg_power_w": prev.get("average_power_w"),
            "current_kwh_per_hour": round(current_kwh_per_hour, 6),
            "previous_kwh_per_hour": round(prev_kwh_per_hour, 6),
            "percentage_difference": round(pct_diff, 1),
            "direction": "higher" if pct_diff > 0 else "lower",
            "note": (
                f"Current session is consuming {abs(pct_diff):.1f}% "
                f"{'more' if pct_diff > 0 else 'less'} energy per hour "
                f"than the previous comparable session."
            ),
        }

    def _load_sessions(self) -> list:
        """Load all sessions from the sessions JSON file."""
        if not os.path.isfile(self.sessions_file):
            return []
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            return []

