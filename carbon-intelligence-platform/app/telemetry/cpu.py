"""
Carbon Intelligence Platform — CPU Telemetry Collector

Collects CPU utilization, frequency, and time breakdown using psutil.
Uses Windows-native performance counters via psutil (which calls GetSystemTimes
and GetSystemInfo under the hood on Windows).
"""

import logging
import psutil
from app.telemetry.base import CPUMetrics

logger = logging.getLogger(__name__)


def collect_cpu_metrics() -> CPUMetrics:
    """
    Collect CPU metrics.

    Returns a CPUMetrics object with:
    - utilization_pct: overall CPU % (non-blocking, reads cached kernel counters)
    - frequency_mhz: current clock frequency
    - user_pct / privileged_pct / idle_pct: per-mode time percentages
    - logical_count: number of logical CPUs
    """
    try:
        # Overall utilization — interval=None reads since last call (non-blocking)
        utilization = psutil.cpu_percent(interval=None)

        # CPU times as percentages across all CPUs
        times_pct = psutil.cpu_times_percent(interval=None, percpu=False)
        user_pct = getattr(times_pct, "user", 0.0)
        # Windows: 'system' = privileged time
        privileged_pct = getattr(times_pct, "system", 0.0)
        idle_pct = getattr(times_pct, "idle", 0.0)

        # CPU frequency
        freq = psutil.cpu_freq()
        if freq is not None:
            frequency_mhz = freq.current
        else:
            logger.warning("CPU frequency not available from psutil.")
            frequency_mhz = 0.0

        logical_count = psutil.cpu_count(logical=True)

        return CPUMetrics(
            utilization_pct=round(utilization, 2),
            frequency_mhz=round(frequency_mhz, 1),
            user_pct=round(user_pct, 2),
            privileged_pct=round(privileged_pct, 2),
            idle_pct=round(idle_pct, 2),
            logical_count=logical_count or 1,
        )

    except Exception as e:
        logger.error(f"Error collecting CPU metrics: {e}")
        # Return safe defaults rather than crashing
        return CPUMetrics(
            utilization_pct=0.0,
            frequency_mhz=0.0,
            user_pct=0.0,
            privileged_pct=0.0,
            idle_pct=100.0,
            logical_count=1,
        )

