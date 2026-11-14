"""
scripts/generate_eda_visualizations.py
Generates the 10 core Exploratory Data Analysis (EDA) visualizations required
by the research specification.

Visualizations:
  1. Distribution of conflict rate
  2. Distribution of abort rate
  3. Distribution of network RTT
  4. Distribution of transaction latency
  5. Correlation heatmap
  6. Network RTT and jitter over time
  7. Transaction contention over time
  8. Throughput comparison under different workloads
  9. Latency comparison under different network conditions
  10. Relationships between contention, network conditions and throughput

Charts are saved to results/figures/ and clearly marked with a synthetic data
notice in titles/captions as required.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Styling configuration
sns.set_theme(style="whitegrid", palette="deep")
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
})

FIG_DIR = PROJECT_ROOT / "results" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
SYNTH_TAG = "[Synthetic Testbed Data]"


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def plot_distributions(df: pd.DataFrame):
    # 1. Conflict Rate Distribution
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.histplot(df["conflict_rate"], kde=True, bins=30, ax=ax, color="#1f77b4")
    ax.set_title(f"1. Distribution of Transaction Conflict Rate {SYNTH_TAG}")
    ax.set_xlabel("Conflict Rate (ratio [0, 1])")
    ax.set_ylabel("Frequency / Count")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "01_distribution_conflict_rate.png", dpi=150)
    plt.close(fig)

    # 2. Abort Rate Distribution
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.histplot(df["abort_rate"], kde=True, bins=30, ax=ax, color="#d62728")
    ax.set_title(f"2. Distribution of Transaction Abort Rate {SYNTH_TAG}")
    ax.set_xlabel("Abort Rate (ratio [0, 1])")
    ax.set_ylabel("Frequency / Count")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "02_distribution_abort_rate.png", dpi=150)
    plt.close(fig)

    # 3. Network RTT Distribution
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.histplot(df["network_rtt_ms"], kde=True, bins=30, ax=ax, color="#2ca02c")
    ax.set_title(f"3. Distribution of Network RTT {SYNTH_TAG}")
    ax.set_xlabel("Network Round-Trip Time (RTT) (ms)")
    ax.set_ylabel("Frequency / Count")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "03_distribution_network_rtt.png", dpi=150)
    plt.close(fig)

    # 4. Transaction Latency Distribution (Average, P95, P99)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.kdeplot(df["average_latency_ms"], label="Mean Latency", ax=ax, fill=True, alpha=0.3, color="#1f77b4")
    sns.kdeplot(df["p95_latency_ms"], label="P95 Latency", ax=ax, fill=True, alpha=0.2, color="#ff7f0e")
    sns.kdeplot(df["p99_latency_ms"], label="P99 Latency", ax=ax, fill=True, alpha=0.1, color="#d62728")
    ax.set_title(f"4. Distribution of Transaction Latencies {SYNTH_TAG}")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Density")
    ax.legend(title="Latency Metric")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "04_distribution_transaction_latency.png", dpi=150)
    plt.close(fig)


def plot_correlations(df: pd.DataFrame):
    # 5. Correlation Heatmap
    metric_cols = [
        "conflict_rate", "abort_rate", "network_rtt_ms", "network_jitter_ms",
        "packet_loss_rate", "throughput_tps", "average_latency_ms",
        "p95_latency_ms", "concurrent_transactions", "queue_length"
    ]
    corr = df[metric_cols].corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1,
        cbar_kws={"label": "Pearson Correlation Coefficient"}, ax=ax, linewidths=0.5
    )
    ax.set_title(f"5. Correlation Heatmap of System and Workload Metrics {SYNTH_TAG}")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "05_correlation_heatmap.png", dpi=150)
    plt.close(fig)


def plot_time_series(df: pd.DataFrame):
    # Pick a dynamic experiment or typical experiment
    target_exp = "exp_0023" if "exp_0023" in df["experiment_id"].values else df["experiment_id"].iloc[0]
    sub = df[df["experiment_id"] == target_exp].copy().sort_values("timestamp")

    # 6. Network RTT and Jitter over time
    fig, ax1 = plt.subplots(figsize=(10, 4.5))
    time_steps = np.arange(len(sub)) * 5  # 5-second sampling
    ax1.plot(time_steps, sub["network_rtt_ms"], color="#1f77b4", label="Network RTT (ms)", linewidth=1.8)
    ax1.set_xlabel("Elapsed Time (seconds)")
    ax1.set_ylabel("RTT (ms)", color="#1f77b4")
    ax1.tick_params(axis="y", labelcolor="#1f77b4")

    ax2 = ax1.twinx()
    ax2.plot(time_steps, sub["network_jitter_ms"], color="#ff7f0e", linestyle="--", label="Network Jitter (ms)", linewidth=1.5)
    ax2.set_ylabel("Jitter (ms)", color="#ff7f0e")
    ax2.tick_params(axis="y", labelcolor="#ff7f0e")

    plt.title(f"6. Network RTT and Jitter Over Time ({target_exp}) {SYNTH_TAG}")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "06_network_rtt_jitter_over_time.png", dpi=150)
    plt.close(fig)

    # 7. Transaction Contention over time
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(time_steps, sub["conflict_rate"], label="Conflict Rate", color="#d62728", linewidth=1.8)
    ax.plot(time_steps, sub["abort_rate"], label="Abort Rate", color="#9467bd", linestyle="--", linewidth=1.5)
    ax.set_title(f"7. Transaction Contention and Aborts Over Time ({target_exp}) {SYNTH_TAG}")
    ax.set_xlabel("Elapsed Time (seconds)")
    ax.set_ylabel("Rate (Ratio [0, 1])")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "07_contention_over_time.png", dpi=150)
    plt.close(fig)


def plot_comparisons(df: pd.DataFrame):
    # 8. Throughput comparison under different workloads
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.boxplot(data=df, x="workload_type", y="throughput_tps", hue="active_protocol", ax=ax, palette="Set2")
    ax.set_title(f"8. Throughput Comparison Across Workloads and Protocols {SYNTH_TAG}")
    ax.set_xlabel("Workload Profile")
    ax.set_ylabel("Throughput (TPS)")
    ax.legend(title="Active Protocol")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "08_throughput_by_workload.png", dpi=150)
    plt.close(fig)

    # 9. Latency comparison under different network conditions
    df_copy = df.copy()
    df_copy["network_status"] = np.where(df_copy["network_rtt_ms"] > 20.0, "Degraded (>20ms)", "Normal (<=20ms)")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.boxplot(data=df_copy, x="network_status", y="average_latency_ms", hue="active_protocol", ax=ax, palette="Set1")
    ax.set_title(f"9. Average Latency Under Normal vs Degraded Network {SYNTH_TAG}")
    ax.set_xlabel("Network Condition")
    ax.set_ylabel("Average Transaction Latency (ms)")
    ax.legend(title="Active Protocol")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "09_latency_by_network_condition.png", dpi=150)
    plt.close(fig)

    # 10. Relationships between contention, network conditions and throughput
    fig, ax = plt.subplots(figsize=(9, 5.5))
    scatter = ax.scatter(
        df["conflict_rate"],
        df["throughput_tps"],
        c=df["network_rtt_ms"],
        cmap="viridis",
        alpha=0.6,
        s=30,
        edgecolors="none"
    )
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Network RTT (ms)")
    ax.set_title(f"10. Tri-variate Impact: Contention, Network RTT, and Throughput {SYNTH_TAG}")
    ax.set_xlabel("Conflict Rate (ratio)")
    ax.set_ylabel("Throughput (TPS)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "10_contention_network_throughput_relation.png", dpi=150)
    plt.close(fig)


def main():
    data_path = PROJECT_ROOT / "data" / "processed" / "processed_data.csv"
    if not data_path.exists():
        data_path = PROJECT_ROOT / "data" / "sample" / "synthetic_experiment_data.csv"
    print(f"Loading data from {data_path}...")
    df = load_dataset(data_path)

    print("Generating EDA visualizations...")
    plot_distributions(df)
    plot_correlations(df)
    plot_time_series(df)
    plot_comparisons(df)

    print(f"Successfully generated all 10 EDA charts in {FIG_DIR}")


if __name__ == "__main__":
    main()

