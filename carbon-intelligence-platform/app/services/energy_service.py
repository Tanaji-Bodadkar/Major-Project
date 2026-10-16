"""Accumulate estimated energy from timestamped power predictions."""

import logging
import math
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
MAX_INTEGRATION_GAP_S = 300.0


class EnergyService:
    """Session energy accumulator; each telemetry timestamp is accepted once."""

    def __init__(self):
        self._session_energy_wh = 0.0
        self._current_power_w: Optional[float] = None
        self._peak_power_w = 0.0
        self._power_readings = []
        self._last_timestamp: Optional[datetime] = None
        self._last_update_time: Optional[float] = None
        self._session_start_time: Optional[float] = None
        self._last_energy_increment_wh = 0.0
        self._last_sample_accepted = False

    def reset(self):
        self._session_energy_wh = 0.0
        self._current_power_w = None
        self._peak_power_w = 0.0
        self._power_readings = []
        self._last_timestamp = None
        self._last_update_time = time.monotonic()
        self._session_start_time = time.monotonic()
        self._last_energy_increment_wh = 0.0
        self._last_sample_accepted = False
        logger.info("EnergyService reset for a new session.")

    @staticmethod
    def _parse_timestamp(timestamp: str) -> datetime:
        try:
            value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ValueError("timestamp must be a valid ISO-8601 datetime") from exc
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def update(self, predicted_power_w: float, timestamp: Optional[str] = None,
               elapsed_s: Optional[float] = None) -> dict:
        """Accept one prediction; timestamp mode is idempotent and uses sample time.

        `elapsed_s` remains available for deterministic unit tests and callers that
        already measured an interval. Production routes should pass snapshot time.
        """
        if predicted_power_w is None or not math.isfinite(predicted_power_w) or predicted_power_w < 0:
            raise ValueError("predicted_power_w must be a finite non-negative number")
        if timestamp is not None and elapsed_s is not None:
            raise ValueError("provide timestamp or elapsed_s, not both")

        now_monotonic = time.monotonic()
        self._last_sample_accepted = False
        self._last_energy_increment_wh = 0.0

        if timestamp is not None:
            sample_time = self._parse_timestamp(timestamp)
            if self._last_timestamp is not None and sample_time <= self._last_timestamp:
                return self.get_state()
            interval_s = (
                (sample_time - self._last_timestamp).total_seconds()
                if self._last_timestamp is not None else 0.0
            )
            self._last_timestamp = sample_time
        else:
            if elapsed_s is not None and (not math.isfinite(elapsed_s) or elapsed_s < 0):
                raise ValueError("elapsed_s must be a finite non-negative number")
            interval_s = elapsed_s
            if interval_s is None and self._last_update_time is not None:
                interval_s = now_monotonic - self._last_update_time

        if interval_s is not None and 0 < interval_s <= MAX_INTEGRATION_GAP_S:
            self._last_energy_increment_wh = predicted_power_w * interval_s / 3600.0
            self._session_energy_wh += self._last_energy_increment_wh
        elif interval_s is not None and interval_s > MAX_INTEGRATION_GAP_S:
            logger.warning("Skipped energy interval %.1fs; exceeds %.0fs gap limit.", interval_s, MAX_INTEGRATION_GAP_S)

        self._last_sample_accepted = True
        self._last_update_time = now_monotonic
        self._current_power_w = predicted_power_w
        self._peak_power_w = max(self._peak_power_w, predicted_power_w)
        self._power_readings.append((timestamp or datetime.now(timezone.utc).isoformat(), predicted_power_w))
        if len(self._power_readings) > 10000:
            self._power_readings = self._power_readings[-10000:]
        return self.get_state()

    def break_series(self, timestamp: Optional[str] = None):
        """Prevent a later valid estimate from bridging an interval with no estimate."""
        if timestamp is not None:
            sample_time = self._parse_timestamp(timestamp)
            if self._last_timestamp is None or sample_time > self._last_timestamp:
                self._last_timestamp = sample_time
        self._current_power_w = None
        self._last_update_time = time.monotonic()
        self._last_energy_increment_wh = 0.0
        self._last_sample_accepted = False

    def get_state(self) -> dict:
        avg_power = (
            sum(power for _, power in self._power_readings) / len(self._power_readings)
            if self._power_readings else 0.0
        )
        duration = (
            time.monotonic() - self._session_start_time
            if self._session_start_time is not None else 0.0
        )
        return {
            "current_power_w": round(self._current_power_w, 2) if self._current_power_w is not None else None,
            "peak_power_w": round(self._peak_power_w, 2),
            "average_power_w": round(avg_power, 2),
            "session_energy_wh": round(self._session_energy_wh, 6),
            "session_energy_kwh": round(self._session_energy_wh / 1000.0, 9),
            "session_duration_s": round(duration, 1),
            "reading_count": len(self._power_readings),
            "last_energy_increment_wh": round(self._last_energy_increment_wh, 9),
            "last_sample_accepted": self._last_sample_accepted,
            "last_sample_timestamp": self._last_timestamp.isoformat() if self._last_timestamp else None,
        }

    def get_session_energy_kwh(self) -> float:
        return self._session_energy_wh / 1000.0

    def get_current_power_w(self) -> Optional[float]:
        return self._current_power_w

