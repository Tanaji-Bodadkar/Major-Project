"""
Carbon Intelligence Platform — Telemetry Base Classes

Defines the abstract interface for telemetry providers.
Different providers (Windows, Linux, mock for testing) implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class CPUMetrics:
    utilization_pct: float          # Overall CPU utilization %
    frequency_mhz: float            # Current CPU frequency in MHz
    user_pct: float                 # % time in user mode
    privileged_pct: float           # % time in privileged/kernel mode
    idle_pct: float                 # % time idle
    logical_count: int              # Number of logical CPUs


@dataclass
class MemoryMetrics:
    total_mb: float                 # Total installed RAM in MB
    available_mb: float             # Available RAM in MB
    used_mb: float                  # Used RAM in MB
    utilization_pct: float          # % RAM used


@dataclass
class DiskMetrics:
    read_mb_s: float                # Disk read rate in MB/s
    write_mb_s: float               # Disk write rate in MB/s


@dataclass
class NetworkMetrics:
    sent_mb_s: float                # Network bytes sent in MB/s
    recv_mb_s: float                # Network bytes received in MB/s


@dataclass
class GPUMetrics:
    available: bool                 # Whether GPU metrics could be collected
    utilization_pct: Optional[float] = None   # GPU compute %
    memory_used_mb: Optional[float] = None    # GPU memory used in MB
    memory_total_mb: Optional[float] = None   # GPU total memory in MB
    unavailability_reason: Optional[str] = None  # Why GPU metrics are not available


@dataclass
class ProcessInfo:
    name: str
    pid: int
    cpu_pct: float
    memory_mb: float


@dataclass
class TelemetrySnapshot:
    """
    A complete telemetry snapshot at one point in time.
    This is the primary data structure passed between telemetry and ML layers.
    """
    timestamp: str                  # ISO-8601 timestamp
    collection_interval_s: float    # Configured sampling interval

    cpu: CPUMetrics
    memory: MemoryMetrics
    disk: DiskMetrics
    network: NetworkMetrics
    gpu: GPUMetrics

    process_count: int
    top_processes: list             # List of ProcessInfo

    def to_dict(self) -> dict:
        """Convert snapshot to JSON-serializable dictionary."""
        return {
            "timestamp": self.timestamp,
            "collection_interval_s": self.collection_interval_s,
            "cpu": {
                "utilization_pct": self.cpu.utilization_pct,
                "frequency_mhz": self.cpu.frequency_mhz,
                "user_pct": self.cpu.user_pct,
                "privileged_pct": self.cpu.privileged_pct,
                "idle_pct": self.cpu.idle_pct,
                "logical_count": self.cpu.logical_count,
            },
            "memory": {
                "total_mb": self.memory.total_mb,
                "available_mb": self.memory.available_mb,
                "used_mb": self.memory.used_mb,
                "utilization_pct": self.memory.utilization_pct,
            },
            "disk": {
                "read_mb_s": self.disk.read_mb_s,
                "write_mb_s": self.disk.write_mb_s,
            },
            "network": {
                "sent_mb_s": self.network.sent_mb_s,
                "recv_mb_s": self.network.recv_mb_s,
            },
            "gpu": {
                "available": self.gpu.available,
                "utilization_pct": self.gpu.utilization_pct,
                "memory_used_mb": self.gpu.memory_used_mb,
                "memory_total_mb": self.gpu.memory_total_mb,
                "unavailability_reason": self.gpu.unavailability_reason,
            },
            "processes": {
                "count": self.process_count,
                "top": [
                    {
                        "name": p.name,
                        "pid": p.pid,
                        "cpu_pct": p.cpu_pct,
                        "memory_mb": p.memory_mb,
                    }
                    for p in self.top_processes
                ],
            },
        }

    def to_csv_row(self) -> dict:
        """
        Convert snapshot to a flat dict for CSV storage.
        Uses the top CPU process for the process columns.
        """
        top = self.top_processes[0] if self.top_processes else None
        return {
            "timestamp": self.timestamp,
            "collection_interval_s": self.collection_interval_s,
            "cpu_utilization_pct": self.cpu.utilization_pct,
            "cpu_frequency_mhz": self.cpu.frequency_mhz,
            "cpu_user_pct": self.cpu.user_pct,
            "cpu_privileged_pct": self.cpu.privileged_pct,
            "cpu_idle_pct": self.cpu.idle_pct,
            "cpu_logical_count": self.cpu.logical_count,
            "ram_total_mb": self.memory.total_mb,
            "ram_available_mb": self.memory.available_mb,
            "ram_used_mb": self.memory.used_mb,
            "ram_utilization_pct": self.memory.utilization_pct,
            "disk_read_mb_s": self.disk.read_mb_s,
            "disk_write_mb_s": self.disk.write_mb_s,
            "network_sent_mb_s": self.network.sent_mb_s,
            "network_recv_mb_s": self.network.recv_mb_s,
            "gpu_available": self.gpu.available,
            "gpu_utilization_pct": self.gpu.utilization_pct if self.gpu.available else "",
            "gpu_memory_used_mb": self.gpu.memory_used_mb if self.gpu.available else "",
            "process_count": self.process_count,
            "top_process_name": top.name if top else "",
            "top_process_cpu_pct": top.cpu_pct if top else "",
            "top_process_memory_mb": top.memory_mb if top else "",
        }


class TelemetryProvider(ABC):
    """Abstract base class for telemetry providers."""

    @abstractmethod
    def get_snapshot(self) -> TelemetrySnapshot:
        """Collect and return a telemetry snapshot."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return provider name (e.g. 'WindowsTelemetryProvider')."""
        pass

