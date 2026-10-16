"""
Carbon Intelligence Platform — EDA and Preprocessing Script

Performs exploratory data analysis on the training dataset.
Saves plots to reports/figures/.

Run with:
    python notebooks/eda_and_preprocessing.py

Or open as Jupyter notebook if nbformat is available.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

FIGURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports", "figures"
)
DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "processed", "training_data.csv"
)

os.makedirs(FIGURES_DIR, exist_ok=True)
sns.set_theme(style="whitegrid", palette="muted")


def load_data() -> pd.DataFrame:
    if not os.path.isfile(DATA_PATH):
        print(f"Dataset not found: {DATA_PATH}")
        print("Run: python notebooks/generate_training_data.py first")
        sys.exit(1)
    df = pd.read_csv(DATA_PATH)
    print(f"Dataset loaded: {df.shape[0]} rows × {df.shape[1]} columns")
    return df


def describe_dataset(df: pd.DataFrame):
    print("\n=== Dataset Overview ===")
    print(f"Shape: {df.shape}")
    print(f"\nData types:\n{df.dtypes}")
    print(f"\nMissing values:\n{df.isnull().sum()}")
    print(f"\nDuplicates: {df.duplicated().sum()}")
    print(f"\nDescriptive statistics:")
    print(df.describe().round(3))


def plot_power_distribution(df: pd.DataFrame):
    """Distribution of the target variable."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(df["measured_power_w"], bins=50, color="#2d5a3d", edgecolor="white", alpha=0.8)
    axes[0].set_xlabel("Measured Power (W)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Distribution of Measured Power")
    axes[0].axvline(df["measured_power_w"].mean(), color="red", linestyle="--",
                    label=f"Mean: {df['measured_power_w'].mean():.1f} W")
    axes[0].legend()

    axes[1].boxplot(df["measured_power_w"], vert=True)
    axes[1].set_ylabel("Measured Power (W)")
    axes[1].set_title("Power Boxplot")
    axes[1].set_xticklabels(["Power"])

    plt.suptitle("Target Variable Distribution — Measured Power (W)")
    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "eda_power_distribution.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def plot_feature_correlations(df: pd.DataFrame):
    """Correlation heatmap of features vs. power."""
    fig, ax = plt.subplots(figsize=(10, 8))
    corr = df.corr(numeric_only=True)
    mask = np.zeros_like(corr, dtype=bool)
    mask[np.triu_indices_from(mask)] = True
    sns.heatmap(
        corr, mask=mask, annot=True, fmt=".2f", cmap="RdYlGn",
        center=0, ax=ax, square=True, linewidths=0.5, cbar_kws={"shrink": 0.8}
    )
    ax.set_title("Feature Correlation Matrix")
    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "eda_correlation_heatmap.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def plot_cpu_vs_power(df: pd.DataFrame):
    """CPU utilization vs. power — the key relationship."""
    fig, ax = plt.subplots(figsize=(8, 5))
    scatter = ax.scatter(
        df["cpu_utilization_pct"], df["measured_power_w"],
        c=df["gpu_utilization_pct"], cmap="YlOrRd",
        alpha=0.3, s=8
    )
    plt.colorbar(scatter, label="GPU Utilization (%)")
    ax.set_xlabel("CPU Utilization (%)")
    ax.set_ylabel("Measured Power (W)")
    ax.set_title("CPU Utilization vs. Measured Power\n(color = GPU utilization)")

    # Add a trend line
    z = np.polyfit(df["cpu_utilization_pct"], df["measured_power_w"], 2)
    p = np.poly1d(z)
    x_line = np.linspace(0, 100, 200)
    ax.plot(x_line, p(x_line), "r--", linewidth=2, label="Polynomial trend")
    ax.legend()

    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "eda_cpu_vs_power.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def plot_feature_vs_power(df: pd.DataFrame):
    """Scatter plots of each feature vs power."""
    features = [
        "cpu_utilization_pct", "cpu_frequency_mhz",
        "ram_utilization_pct", "disk_read_mb_s",
        "network_recv_mb_s", "gpu_utilization_pct",
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes_flat = axes.flatten()

    for i, feat in enumerate(features):
        axes_flat[i].scatter(
            df[feat], df["measured_power_w"],
            alpha=0.2, s=5, color=sns.color_palette("muted")[i]
        )
        axes_flat[i].set_xlabel(feat)
        axes_flat[i].set_ylabel("Power (W)")
        axes_flat[i].set_title(f"{feat} vs Power")

    plt.suptitle("Feature vs. Power Relationships")
    plt.tight_layout()
    path = os.path.join(FIGURES_DIR, "eda_feature_vs_power.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def main():
    print("=== Carbon Intelligence Platform — EDA ===\n")
    df = load_data()
    describe_dataset(df)
    plot_power_distribution(df)
    plot_feature_correlations(df)
    plot_cpu_vs_power(df)
    plot_feature_vs_power(df)
    print(f"\nAll EDA plots saved to: {FIGURES_DIR}")
    print("\nKey observations:")
    print(f"  - Power range: {df['measured_power_w'].min():.1f} – {df['measured_power_w'].max():.1f} W")
    print(f"  - CPU–Power correlation: {df['cpu_utilization_pct'].corr(df['measured_power_w']):.3f}")
    print(f"  - GPU–Power correlation: {df['gpu_utilization_pct'].corr(df['measured_power_w']):.3f}")
    print(f"  - RAM–Power correlation: {df['ram_utilization_pct'].corr(df['measured_power_w']):.3f}")


if __name__ == "__main__":
    main()

