"""
Carbon Intelligence Platform — Disk I/O Telemetry Collector

Calculates disk read/write rates in MB/s by comparing
consecutive psutil.disk_io_counters() readings.
"""

import time
import logging
import psutil
from app.telemetry.base import DiskMetrics

logger = logging.getLogger(__name__)

_BYTES_TO_MB = 1 / (1024 * 1024)

# Module-level state for rate calculation
_prev_read_bytes: int = 0
_prev_write_bytes: int = 0
_prev_time: float = 0.0
_initialized: bool = False


def collect_disk_metrics(interval_s: float = 5.0) -> DiskMetrics:
    """
    Collect disk I/O rates in MB/s.

    Rate is calculated as delta bytes / delta time since the last call.
    On the first call, initializes the baseline and returns 0.0 rates.

    Args:
        interval_s: Expected sampling interval (used as fallback if time delta is tiny)
    """
    global _prev_read_bytes, _prev_write_bytes, _prev_time, _initialized

    try:
        counters = psutil.disk_io_counters(perdisk=False)
        if counters is None:
            logger.warning("Disk I/O counters unavailable on this system.")
            return DiskMetrics(read_mb_s=0.0, write_mb_s=0.0)

        now = time.monotonic()
        current_read = counters.read_bytes
        current_write = counters.write_bytes

        if not _initialized:
            # First call — just initialize baseline
            _prev_read_bytes = current_read
            _prev_write_bytes = current_write
            _prev_time = now
            _initialized = True
            return DiskMetrics(read_mb_s=0.0, write_mb_s=0.0)

        delta_t = now - _prev_time
        if delta_t < 0.1:
            # Too short an interval — avoid division instability
            delta_t = interval_s

        delta_read = max(0, current_read - _prev_read_bytes)
        delta_write = max(0, current_write - _prev_write_bytes)

        read_mb_s = (delta_read * _BYTES_TO_MB) / delta_t
        write_mb_s = (delta_write * _BYTES_TO_MB) / delta_t

        # Update state
        _prev_read_bytes = current_read
        _prev_write_bytes = current_write
        _prev_time = now

        return DiskMetrics(
            read_mb_s=round(read_mb_s, 3),
            write_mb_s=round(write_mb_s, 3),
        )

    except Exception as e:
        logger.error(f"Error collecting disk metrics: {e}")
        return DiskMetrics(read_mb_s=0.0, write_mb_s=0.0)

