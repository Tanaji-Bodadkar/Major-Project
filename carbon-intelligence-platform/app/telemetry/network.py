"""
Carbon Intelligence Platform — Network I/O Telemetry Collector

Calculates network sent/received rates in MB/s using psutil.net_io_counters().
"""

import time
import logging
import psutil
from app.telemetry.base import NetworkMetrics

logger = logging.getLogger(__name__)

_BYTES_TO_MB = 1 / (1024 * 1024)

# Module-level state for rate calculation
_prev_sent_bytes: int = 0
_prev_recv_bytes: int = 0
_prev_time: float = 0.0
_initialized: bool = False


def collect_network_metrics(interval_s: float = 5.0) -> NetworkMetrics:
    """
    Collect network I/O rates in MB/s.

    Rate is calculated as delta bytes / delta time since last call.
    On first call, returns 0.0 rates.
    """
    global _prev_sent_bytes, _prev_recv_bytes, _prev_time, _initialized

    try:
        counters = psutil.net_io_counters(pernic=False)
        if counters is None:
            logger.warning("Network I/O counters unavailable.")
            return NetworkMetrics(sent_mb_s=0.0, recv_mb_s=0.0)

        now = time.monotonic()
        current_sent = counters.bytes_sent
        current_recv = counters.bytes_recv

        if not _initialized:
            _prev_sent_bytes = current_sent
            _prev_recv_bytes = current_recv
            _prev_time = now
            _initialized = True
            return NetworkMetrics(sent_mb_s=0.0, recv_mb_s=0.0)

        delta_t = now - _prev_time
        if delta_t < 0.1:
            delta_t = interval_s

        delta_sent = max(0, current_sent - _prev_sent_bytes)
        delta_recv = max(0, current_recv - _prev_recv_bytes)

        sent_mb_s = (delta_sent * _BYTES_TO_MB) / delta_t
        recv_mb_s = (delta_recv * _BYTES_TO_MB) / delta_t

        _prev_sent_bytes = current_sent
        _prev_recv_bytes = current_recv
        _prev_time = now

        return NetworkMetrics(
            sent_mb_s=round(sent_mb_s, 4),
            recv_mb_s=round(recv_mb_s, 4),
        )

    except Exception as e:
        logger.error(f"Error collecting network metrics: {e}")
        return NetworkMetrics(sent_mb_s=0.0, recv_mb_s=0.0)

