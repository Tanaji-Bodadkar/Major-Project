# Carbon Intelligence Platform — Telemetry Specification

## Overview

The telemetry layer collects observable system metrics from the Windows operating system
using native OS performance interfaces (psutil, WMI). These metrics are **not** electrical
measurements — they are inputs to an ML model that estimates power consumption.

## Telemetry Sources

| Source | Library | Notes |
|--------|---------|-------|
| CPU utilization, frequency | psutil | Cross-platform, widely validated |
| Memory usage | psutil | Reliable on Windows |
| Disk I/O rates | psutil | Bytes/sec per disk |
| Network I/O rates | psutil | Bytes/sec per interface |
| GPU utilization | WMI (Win32_PerfFormattedData_GPUPerformanceCounters) | Optional, may be unavailable |
| Process list | psutil | Top N processes by CPU% |

---

## Telemetry Record Schema

```
timestamp                  ISO-8601 string            e.g. 2026-09-20T14:32:01.123456
collection_interval_s      float                      seconds between samples (default 5.0)

--- CPU ---
cpu_utilization_pct        float [0.0–100.0]          overall CPU usage %
cpu_frequency_mhz          float                      current clock frequency in MHz
cpu_user_pct               float [0.0–100.0]          % time in user mode
cpu_privileged_pct         float [0.0–100.0]          % time in privileged (kernel) mode
cpu_idle_pct               float [0.0–100.0]          % time idle
cpu_logical_count          int                        number of logical CPU cores

--- Memory ---
ram_total_mb               float                      total installed RAM in MB
ram_available_mb           float                      currently available RAM in MB
ram_used_mb                float                      RAM in use in MB
ram_utilization_pct        float [0.0–100.0]          % RAM used

--- Disk ---
disk_read_mb_s             float                      MB/s read (all disks aggregate)
disk_write_mb_s            float                      MB/s write (all disks aggregate)

--- Network ---
network_sent_mb_s          float                      MB/s sent (all interfaces)
network_recv_mb_s          float                      MB/s received (all interfaces)

--- GPU (optional) ---
gpu_available              bool                       True if GPU metrics could be collected
gpu_utilization_pct        float or null              % GPU compute engine usage
gpu_memory_used_mb         float or null              MB of GPU memory in use
gpu_memory_total_mb        float or null              Total GPU memory in MB

--- Processes ---
process_count              int                        total running processes
top_process_name           string                     name of top CPU process
top_process_cpu_pct        float                      CPU% of top process
top_process_memory_mb      float                      Memory MB of top process
```

---

## Sampling Strategy

- **Default interval:** 5 seconds (configurable in `config.py`)
- **Disk/Network:** calculated as delta over the interval (bytes_now - bytes_prev) / interval_s → MB/s
- **CPU:** `psutil.cpu_percent(interval=None)` — non-blocking, reads from cached kernel counter
- **GPU:** attempted via WMI query; if query fails, `gpu_available=False` and GPU fields set to `null`

---

## Storage

Raw telemetry is appended to daily CSV files:

```
data/telemetry/telemetry_YYYYMMDD.csv
```

CSV column order matches the schema above. `null` GPU values are stored as empty strings.

---

## What Telemetry Is NOT

The following are **estimated values**, computed from telemetry:

- `predicted_power_w` — ML model output
- `energy_wh` — calculated from predicted power × time
- `co2e_g` — calculated from energy × carbon intensity

The UI must display these as:
> **Estimated Power: 72 W**
> **Estimated Energy: 0.36 kWh**
> **Estimated CO₂e: 184 g**

---

## Availability Matrix

| Metric | Expected Availability | Fallback Behavior |
|--------|-----------------------|-------------------|
| CPU utilization | Always | N/A |
| CPU frequency | Always (psutil) | Log warning if 0 Hz |
| RAM usage | Always | N/A |
| Disk I/O | Always | Returns 0.0 if no activity |
| Network I/O | Always | Returns 0.0 if no activity |
| GPU metrics | Optional — NVIDIA/AMD with WMI driver support | `gpu_available=False`, fields `null` |
| Top process CPU | Requires sufficient permissions | Returns "N/A" if access denied |

---

## Privacy Considerations

- Process names are collected (e.g., "chrome.exe") for workload classification.
- No process command-line arguments, user data, or file paths are collected.
- No user account information is collected.
- All data is stored locally on the user's machine.

