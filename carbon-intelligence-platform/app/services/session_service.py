"""
Carbon Intelligence Platform — Session Management Service

Manages monitoring sessions: start, stop, persist, and retrieve.

A session represents a defined period of monitoring activity.
All values within a session are derived from actual measurements.
"""

import os
import json
import uuid
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class SessionService:
    """
    Manages monitoring sessions.

    Sessions are stored in data/emissions/sessions.json.
    """

    def __init__(self, config):
        self.config = config
        self.sessions_file = config.SESSIONS_FILE
        self._active_session: Optional[dict] = None
        self._active_start_monotonic: Optional[float] = None
        self._cpu_history: list = []  # recent CPU % readings for recommendation engine

    def start_session(self, name: Optional[str] = None) -> dict:
        """
        Start a new monitoring session.

        Args:
            name: Optional human-readable session name

        Returns:
            New session dict
        """
        if self._active_session:
            logger.warning("Session already active. Stop the current session first.")
            return self._active_session

        session_id = str(uuid.uuid4())[:8]
        start_time = datetime.now(timezone.utc).isoformat()

        self._active_session = {
            "session_id": session_id,
            "name": name or f"Session {session_id}",
            "start_time": start_time,
            "end_time": None,
            "duration_s": None,
            "average_power_w": None,
            "peak_power_w": None,
            "total_energy_wh": None,
            "total_energy_kwh": None,
            "total_co2e_g": None,
            "total_co2e_kg": None,
            "carbon_intensity_avg": None,
            "carbon_intensity_energy_weighted_g_per_kwh": None,
            "carbon_intensity_timestamp": None,
            "carbon_coverage_status": None,
            "uncovered_energy_wh": 0.0,
            "carbon_source": None,
            "status": "active",
        }
        self._active_start_monotonic = time.monotonic()
        self._cpu_history = []

        logger.info(f"Session started: {session_id} ({self._active_session['name']})")
        return self._active_session

    def stop_session(
        self,
        energy_state: dict,
        co2e_data: dict,
        carbon_intensity: Optional[float] = None,
        carbon_source: Optional[str] = None,
        carbon_intensity_timestamp: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Stop the active session and persist it.

        Args:
            energy_state: dict from EnergyService.get_state()
            co2e_data: dict from CarbonService.calculate_co2e()
            carbon_intensity: average carbon intensity during session
            carbon_source: name of carbon data source used

        Returns:
            Completed session dict, or None if no active session
        """
        if not self._active_session:
            logger.warning("No active session to stop.")
            return None

        end_time = datetime.now(timezone.utc).isoformat()
        duration_s = (
            time.monotonic() - self._active_start_monotonic
            if self._active_start_monotonic
            else 0.0
        )

        # Update session with final values
        self._active_session.update({
            "end_time": end_time,
            "duration_s": round(duration_s, 1),
            "average_power_w": energy_state.get("average_power_w"),
            "peak_power_w": energy_state.get("peak_power_w"),
            "total_energy_wh": energy_state.get("session_energy_wh"),
            "total_energy_kwh": energy_state.get("session_energy_kwh"),
            "total_co2e_g": co2e_data.get("co2e_g"),
            "total_co2e_kg": co2e_data.get("co2e_kg"),
            # This is the last source value, not a time average. The energy-
            # weighted session intensity is calculated from interval data below.
            "carbon_intensity_avg": None,
            "carbon_intensity_energy_weighted_g_per_kwh": co2e_data.get("energy_weighted_intensity_g_per_kwh"),
            "carbon_intensity_g_per_kwh": carbon_intensity,
            "carbon_intensity_timestamp": carbon_intensity_timestamp,
            "carbon_source": carbon_source,
            "carbon_coverage_status": co2e_data.get("status"),
            "uncovered_energy_wh": co2e_data.get("uncovered_energy_wh", 0.0),
            "carbon_sources": co2e_data.get("sources", []),
            "status": "completed",
        })

        completed = dict(self._active_session)
        self._save_session(completed)
        self._active_session = None
        self._active_start_monotonic = None

        logger.info(
            f"Session stopped: {completed['session_id']} "
            f"(duration={duration_s:.1f}s, "
            f"energy={completed.get('total_energy_kwh', 0):.4f} kWh, "
            f"CO2e={completed.get('total_co2e_g', 'N/A')} g)"
        )
        return completed

    def get_active_session(self) -> Optional[dict]:
        """Return the current active session, or None."""
        return self._active_session

    def is_session_active(self) -> bool:
        """Return True if a session is currently running."""
        return self._active_session is not None

    def get_all_sessions(self) -> list:
        """Load and return all completed sessions."""
        return self._load_sessions()

    def get_session_by_id(self, session_id: str) -> Optional[dict]:
        """Find a specific session by ID."""
        sessions = self._load_sessions()
        for s in sessions:
            if s.get("session_id") == session_id:
                return s
        return None

    def update_cpu_history(self, cpu_pct: float, max_history: int = 20):
        """Add a CPU reading to history for recommendation engine."""
        self._cpu_history.append(cpu_pct)
        if len(self._cpu_history) > max_history:
            self._cpu_history = self._cpu_history[-max_history:]

    def get_cpu_history(self) -> list:
        """Return recent CPU % history."""
        return list(self._cpu_history)

    def _save_session(self, session: dict):
        """Append a completed session to the sessions JSON file."""
        sessions = self._load_sessions()
        sessions.append(session)
        try:
            os.makedirs(os.path.dirname(self.sessions_file), exist_ok=True)
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2)
            logger.info(f"Session saved to {self.sessions_file}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def _load_sessions(self) -> list:
        """Load all sessions from JSON file."""
        if not os.path.isfile(self.sessions_file):
            return []
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
            return []

