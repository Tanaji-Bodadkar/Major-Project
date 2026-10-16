"""
Carbon Intelligence Platform — Windows Telemetry Provider

Orchestrates all sub-collectors (CPU, memory, disk, network, GPU, processes)
and assembles a complete TelemetrySnapshot.

This is the concrete Windows implementation of the TelemetryProvider interface.
"""

import logging
from datetime import datetime, timezone

from app.telemetry.base import TelemetryProvider, TelemetrySnapshot
from app.telemetry.cpu import collect_cpu_metrics
from app.telemetry.memory import collect_memory_metrics
from app.telemetry.disk import collect_disk_metrics
from app.telemetry.network import collect_network_metrics
from app.telemetry.gpu import collect_gpu_metrics
from app.telemetry.processes import collect_process_metrics

logger = logging.getLogger(__name__)


class WindowsTelemetryProvider(TelemetryProvider):
    """
    Telemetry provider for Windows systems.
    Uses psutil (CPU, memory, disk, network, processes) and WMI (GPU).
    """

    def __init__(self, interval_s: float = 5.0, top_process_count: int = 5):
        self.interval_s = interval_s
        self.top_process_count = top_process_count
        logger.info(
            f"WindowsTelemetryProvider initialized "
            f"(interval={interval_s}s, top_processes={top_process_count})"
        )

    def get_name(self) -> str:
        return "WindowsTelemetryProvider"

    def get_snapshot(self) -> TelemetrySnapshot:
        """
        Collect all telemetry and return a TelemetrySnapshot.

        Each sub-collector handles its own exceptions and returns safe defaults.
        This method will not crash even if individual collectors fail.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        cpu = collect_cpu_metrics()
        memory = collect_memory_metrics()
        disk = collect_disk_metrics(interval_s=self.interval_s)
        network = collect_network_metrics(interval_s=self.interval_s)
        gpu = collect_gpu_metrics()
        process_count, top_processes = collect_process_metrics(
            top_n=self.top_process_count
        )

        snapshot = TelemetrySnapshot(
            timestamp=timestamp,
            collection_interval_s=self.interval_s,
            cpu=cpu,
            memory=memory,
            disk=disk,
            network=network,
            gpu=gpu,
            process_count=process_count,
            top_processes=top_processes,
        )

        logger.debug(
            f"Snapshot collected: CPU={cpu.utilization_pct}% "
            f"RAM={memory.utilization_pct}% "
            f"GPU={'available' if gpu.available else 'unavailable'}"
        )

        return snapshot

