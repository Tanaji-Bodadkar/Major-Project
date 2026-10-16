"""
Carbon Intelligence Platform — Process Telemetry Collector

Collects top N processes by CPU utilization using psutil.
Only collects process name, PID, CPU%, and memory — no command-line args or user data.

Note: Some process metrics may require elevated permissions on Windows.
If access is denied for a process, it is gracefully skipped.
"""

import logging
import psutil
from app.telemetry.base import ProcessInfo

logger = logging.getLogger(__name__)

_BYTES_TO_MB = 1 / (1024 * 1024)


def collect_process_metrics(top_n: int = 5) -> tuple[int, list[ProcessInfo]]:
    """
    Collect top N processes sorted by CPU utilization.

    Returns:
        (total_process_count, list of ProcessInfo objects)

    Processes that cannot be accessed due to permissions are silently skipped.
    """
    processes = []
    total_count = 0

    try:
        all_procs = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            total_count += 1
            try:
                info = proc.info
                if info["name"] is None:
                    continue

                cpu = info.get("cpu_percent") or 0.0
                mem_info = info.get("memory_info")
                mem_mb = (mem_info.rss * _BYTES_TO_MB) if mem_info else 0.0

                all_procs.append(
                    ProcessInfo(
                        name=info["name"],
                        pid=info["pid"],
                        cpu_pct=round(cpu, 2),
                        memory_mb=round(mem_mb, 2),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Skip inaccessible or terminated processes
                continue
            except Exception as e:
                logger.debug(f"Skipping process due to error: {e}")
                continue

        # Sort by CPU% descending, take top N
        all_procs.sort(key=lambda p: p.cpu_pct, reverse=True)
        processes = all_procs[:top_n]

    except Exception as e:
        logger.error(f"Error collecting process metrics: {e}")

    return total_count, processes

