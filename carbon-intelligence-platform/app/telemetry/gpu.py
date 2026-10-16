"""
Carbon Intelligence Platform — GPU Telemetry Collector

Attempts to collect GPU utilization and memory usage via WMI.
This is optional — if GPU metrics are unavailable, GPUMetrics.available = False
is returned and the system continues without crashing.

Windows GPU performance counters used:
  Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine
  Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory

These counters are available on Windows 10/11 with modern GPU drivers.
They do NOT require NVIDIA-specific tools (no nvml/pynvml dependency).
However, they may be unavailable on systems without a discrete GPU, or
on systems where the GPU driver does not expose WMI performance counters.
"""

import logging
from app.telemetry.base import GPUMetrics

logger = logging.getLogger(__name__)

# Attempt WMI import once at module load
_wmi_available = False
_wmi_module = None
try:
    import wmi as wmi_module
    _wmi_module = wmi_module
    _wmi_available = True
except ImportError:
    logger.warning("WMI module not available. GPU metrics will be disabled.")
except Exception as e:
    logger.warning(f"WMI import failed: {e}. GPU metrics will be disabled.")

_BYTES_TO_MB = 1 / (1024 * 1024)


def collect_gpu_metrics() -> GPUMetrics:
    """
    Collect GPU metrics via WMI performance counters.

    Returns:
        GPUMetrics with available=True and populated fields if successful,
        GPUMetrics with available=False and a reason string if not.
    """
    if not _wmi_available:
        return GPUMetrics(
            available=False,
            unavailability_reason="WMI module not installed or not available on this platform.",
        )

    try:
        c = _wmi_module.WMI(namespace=r"root\cimv2")

        # Query GPU engine utilization
        # This counter provides per-engine data; we focus on the 3D/Graphics engine
        gpu_util_pct = _get_gpu_utilization(c)
        gpu_mem_used_mb, gpu_mem_total_mb = _get_gpu_memory(c)

        if gpu_util_pct is None and gpu_mem_used_mb is None:
            return GPUMetrics(
                available=False,
                unavailability_reason=(
                    "WMI GPU performance counters returned no data. "
                    "GPU driver may not support these counters, or no discrete GPU present."
                ),
            )

        return GPUMetrics(
            available=True,
            utilization_pct=gpu_util_pct,
            memory_used_mb=gpu_mem_used_mb,
            memory_total_mb=gpu_mem_total_mb,
        )

    except Exception as e:
        logger.info(f"GPU metrics unavailable: {e}")
        return GPUMetrics(
            available=False,
            unavailability_reason=f"WMI query failed: {type(e).__name__}",
        )


def _get_gpu_utilization(wmi_conn) -> float | None:
    """Query GPU engine utilization percentage."""
    try:
        # Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine
        # UtilizationPercentage — available on Win10+
        engines = wmi_conn.query(
            "SELECT Name, UtilizationPercentage FROM "
            "Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine"
        )
        if not engines:
            return None

        # Aggregate max utilization across all engines (3D, Copy, VideoEncode etc.)
        util_values = []
        for eng in engines:
            try:
                val = float(eng.UtilizationPercentage)
                util_values.append(val)
            except (AttributeError, TypeError, ValueError):
                continue

        if not util_values:
            return None

        return round(max(util_values), 2)

    except Exception as e:
        logger.debug(f"GPU utilization query failed: {e}")
        return None


def _get_gpu_memory(wmi_conn) -> tuple:
    """Query GPU adapter memory usage. Returns (used_mb, total_mb)."""
    try:
        adapters = wmi_conn.query(
            "SELECT DedicatedUsage, SharedUsage FROM "
            "Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory"
        )
        if not adapters:
            return None, None

        total_used = 0
        for adapter in adapters:
            try:
                dedicated = int(getattr(adapter, "DedicatedUsage", 0) or 0)
                total_used += dedicated
            except (AttributeError, TypeError, ValueError):
                continue

        if total_used == 0:
            return None, None

        return round(total_used * _BYTES_TO_MB, 2), None  # total not available via this counter

    except Exception as e:
        logger.debug(f"GPU memory query failed: {e}")
        return None, None

