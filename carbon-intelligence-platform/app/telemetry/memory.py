"""
Carbon Intelligence Platform — Memory Telemetry Collector

Collects RAM metrics using psutil.virtual_memory().
"""

import logging
import psutil
from app.telemetry.base import MemoryMetrics

logger = logging.getLogger(__name__)

_BYTES_TO_MB = 1 / (1024 * 1024)


def collect_memory_metrics() -> MemoryMetrics:
    """
    Collect system RAM metrics.

    Returns MemoryMetrics with values in MB and utilization %.
    """
    try:
        vm = psutil.virtual_memory()

        return MemoryMetrics(
            total_mb=round(vm.total * _BYTES_TO_MB, 2),
            available_mb=round(vm.available * _BYTES_TO_MB, 2),
            used_mb=round(vm.used * _BYTES_TO_MB, 2),
            utilization_pct=round(vm.percent, 2),
        )

    except Exception as e:
        logger.error(f"Error collecting memory metrics: {e}")
        return MemoryMetrics(
            total_mb=0.0,
            available_mb=0.0,
            used_mb=0.0,
            utilization_pct=0.0,
        )

