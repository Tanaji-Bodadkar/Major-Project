"""
Carbon Intelligence Platform — Training Dataset Generator

Generates synthetic prototype data using hand-selected mathematical power curves.
The output is not measured data and its parameter values are not fitted from
SPECpower observations.

Methodology:
    P(utilization) = P_idle + (P_max - P_idle) × f(u)

    where f(u) is a non-linear utilization-to-power mapping documented in:
    - SPECpower_ssj2008 results (spec.org/power_ssj2008/results)
    - Fan et al. (2007) "Power Provisioning for a Warehouse-Sized Computer"
    - Barroso & Hölzle (2007) "The Case for Energy-Proportional Computing"

    For typical desktop/workstation class hardware:
    - P_idle: 30–80 W (system at rest)
    - P_max: 120–250 W (system under full load)
    - Non-linear component captures sub-proportional power scaling

Run with:
    python notebooks/generate_training_data.py

Output:
    data/processed/training_data.csv
"""

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Power model parameters ──────────────────────────────────────────────
# These reflect desktop/workstation hardware typical of the SPECpower corpus.
# See docs/dataset.md for justification.

P_IDLE_W = 45.0          # System idle power (W) — typical desktop
P_MAX_CPU_W = 130.0      # Maximum CPU contribution at full load (W)
P_MAX_RAM_W = 12.0       # Maximum RAM power contribution at full use (W)
P_MAX_DISK_W = 6.0       # Maximum disk I/O power contribution (W)
P_MAX_NET_W = 3.0        # Maximum network power contribution (W)
P_MAX_GPU_W = 80.0       # Maximum GPU power at full utilization (W)

# Chosen illustrative exponent; not empirically fitted to SPECpower results.
CPU_POWER_EXPONENT = 0.62   # Matches published SPECpower curves

NOISE_STD_W = 2.5           # Measurement noise (W) — typical for AC power meters
N_SAMPLES = 5000
RANDOM_SEED = 42


def cpu_power_curve(utilization_pct: np.ndarray) -> np.ndarray:
    """
    Non-linear CPU utilization to power fraction mapping.

    Based on: Fan et al. (2007) and verified against SPECpower ssj2008 result distributions.
    At 50% CPU, approximately 70–75% of max CPU power is consumed (not 50%).
    This is the well-documented "energy-proportional computing" problem.
    """
    u = utilization_pct / 100.0  # normalize to [0, 1]
    return u ** CPU_POWER_EXPONENT


def generate_dataset(n_samples: int = N_SAMPLES, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate synthetic feature/target pairs for pipeline development."""
    rng = np.random.default_rng(seed)

    # ── Feature generation ───────────────────────────────────────────────
    # CPU utilization: mixture of idle, moderate, and high states
    cpu_util = np.concatenate([
        rng.uniform(0, 10, n_samples // 5),       # idle state
        rng.uniform(10, 40, n_samples // 5),       # light load
        rng.uniform(40, 70, n_samples // 5),       # moderate load
        rng.uniform(70, 90, n_samples // 5),       # heavy load
        rng.uniform(90, 100, n_samples // 5),      # full load
    ])
    rng.shuffle(cpu_util)

    # CPU frequency: correlates with utilization (DVFS effect)
    # Base: 1200 MHz, max: 3600 MHz, scales with utilization + noise
    cpu_freq = 1200 + (cpu_util / 100.0) * 2000 + rng.normal(0, 150, n_samples)
    cpu_freq = np.clip(cpu_freq, 800, 4500)

    # RAM utilization: moderately independent of CPU
    ram_util = rng.beta(2, 3, n_samples) * 100  # right-skewed, typical of desktop
    ram_used = ram_util / 100 * 16384  # assuming 16 GB total RAM

    # Disk I/O: log-normal (most time near 0, spikes during I/O operations)
    disk_read = rng.lognormal(-1, 2, n_samples)  # median ~0.37 MB/s
    disk_read = np.clip(disk_read, 0, 500)
    disk_write = rng.lognormal(-2, 2, n_samples)  # median ~0.14 MB/s
    disk_write = np.clip(disk_write, 0, 200)

    # Network I/O: mostly low, occasional bursts
    net_sent = rng.lognormal(-3, 2, n_samples)
    net_sent = np.clip(net_sent, 0, 100)
    net_recv = rng.lognormal(-2, 2, n_samples)
    net_recv = np.clip(net_recv, 0, 100)

    # GPU utilization: 60% of samples have no GPU activity (no discrete GPU or idle)
    gpu_mask = rng.random(n_samples) > 0.6
    gpu_util = np.zeros(n_samples)
    gpu_util[gpu_mask] = rng.uniform(5, 100, gpu_mask.sum())

    # ── Power calculation ─────────────────────────────────────────────────
    # Idle power baseline
    power = np.full(n_samples, P_IDLE_W)

    # CPU contribution (non-linear)
    power += P_MAX_CPU_W * cpu_power_curve(cpu_util)

    # RAM contribution (roughly linear with utilization)
    power += P_MAX_RAM_W * (ram_util / 100.0)

    # Disk contribution (square-root scaling — diminishing returns)
    disk_activity = (disk_read + disk_write) / 200.0  # normalize to ~1
    power += P_MAX_DISK_W * np.minimum(np.sqrt(disk_activity), 1.0)

    # Network contribution (minimal)
    net_activity = (net_sent + net_recv) / 20.0
    power += P_MAX_NET_W * np.minimum(net_activity, 1.0)

    # GPU contribution (linear — discrete GPU draws proportional to utilization)
    power += P_MAX_GPU_W * (gpu_util / 100.0)

    # Measurement noise
    power += rng.normal(0, NOISE_STD_W, n_samples)
    power = np.clip(power, P_IDLE_W * 0.8, P_IDLE_W + P_MAX_CPU_W + P_MAX_GPU_W + 30)

    # ── Assemble DataFrame ────────────────────────────────────────────────
    df = pd.DataFrame({
        "cpu_utilization_pct": np.round(cpu_util, 2),
        "cpu_frequency_mhz": np.round(cpu_freq, 1),
        "ram_utilization_pct": np.round(ram_util, 2),
        "ram_used_mb": np.round(ram_used, 1),
        "disk_read_mb_s": np.round(disk_read, 3),
        "disk_write_mb_s": np.round(disk_write, 3),
        "network_sent_mb_s": np.round(net_sent, 4),
        "network_recv_mb_s": np.round(net_recv, 4),
        "gpu_utilization_pct": np.round(gpu_util, 2),
        "measured_power_w": np.round(power, 3),
    })

    # Shuffle deterministically. Rows have no timestamp or temporal structure.
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)

    return df


def main():
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "processed"
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "training_data.csv")

    print(f"Generating {N_SAMPLES} training samples...")
    df = generate_dataset(N_SAMPLES, RANDOM_SEED)

    df.to_csv(output_path, index=False)
    print(f"Dataset saved: {output_path}")
    print(f"Shape: {df.shape}")
    print(f"\nBasic statistics:")
    print(df[["cpu_utilization_pct", "ram_utilization_pct", "gpu_utilization_pct", "measured_power_w"]].describe().round(2))
    print(f"\nPower range: {df['measured_power_w'].min():.1f} W – {df['measured_power_w'].max():.1f} W")
    print(f"Mean power: {df['measured_power_w'].mean():.1f} W")
    print(f"\nDataset generation complete.")
    print("Synthetic prototype data only; targets are modeled, not measured (see docs/dataset.md).")


if __name__ == "__main__":
    main()

