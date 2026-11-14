"""
scripts/generate_workloads.py
Synthetic data generator for pipeline testing.

This script generates SYNTHETIC experimental data that simulates what a
real benchmark (e.g. YCSB + CCBench) would produce. It is labelled clearly
as synthetic and must NEVER be mixed with real experimental results.

The synthetic data is intended to:
  - Test the preprocessing, training, and evaluation pipeline end-to-end.
  - Verify that the ML models can learn patterns from structured data.
  - Demonstrate the project workflow before real benchmarks are available.

Real data collection requires:
  - A distributed database (e.g. CockroachDB, TiDB, VoltDB).
  - YCSB for workload generation.
  - CCBench or an equivalent for concurrency-control experiments.
  - Linux tc netem for network simulation (requires WSL/Linux).

See docs/experiment_protocol.md for real data collection instructions.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import yaml
import sys
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = PROJECT_ROOT / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def generate_correlated_metrics(
    n: int,
    contention: str,
    network: str,
    params: dict,
    rng: np.random.Generator,
    protocol: str = "OCC",
) -> pd.DataFrame:
    """Generate n observations with realistic correlations.

    Relationships modelled (based on database systems literature):
    - Higher contention → higher conflict rate → higher abort rate.
    - Higher contention → lower throughput, higher latency.
    - Higher network RTT → higher latency, lower throughput.
    - OCC performs better under low contention; 2PL/MVCC under high.
    - Conflict rate and abort rate are correlated (abort <= conflict).
    - p95 > average, p99 > p95 always.

    Parameters
    ----------
    n : int
        Number of observations.
    contention : str
        'low' or 'high'.
    network : str
        'normal' or 'degraded'.
    params : dict
        Parameters from config.yaml.
    rng : np.random.Generator
    protocol : str
        'OCC', '2PL', or 'MVCC'.
    """
    c_params = params[f"{contention}_contention"]
    n_params = params[f"{network}_network"]

    # --- Core metrics with temporal autocorrelation ---
    def autocorrelated_series(low, high, n, rng, smoothing=0.7):
        """Generate a smoothed random walk within [low, high]."""
        raw = rng.uniform(low, high, n)
        series = np.zeros(n)
        series[0] = raw[0]
        for i in range(1, n):
            series[i] = smoothing * series[i-1] + (1 - smoothing) * raw[i]
            series[i] = np.clip(series[i], low, high)
        return series

    concurrent_txns = autocorrelated_series(
        *c_params["concurrent_transactions"], n, rng
    ).astype(int)

    txn_rate = autocorrelated_series(
        *c_params["transaction_rate"], n, rng
    )

    conflict_rate = autocorrelated_series(
        *c_params["conflict_rate"], n, rng, smoothing=0.8
    )

    # Abort rate correlated with conflict rate but lower
    abort_rate = conflict_rate * rng.uniform(0.3, 0.8, n)
    abort_rate = np.clip(abort_rate, *c_params["abort_rate"])

    queue_length = autocorrelated_series(
        *c_params["queue_length"], n, rng
    ).astype(int)

    # Network metrics
    network_rtt = autocorrelated_series(
        *n_params["network_rtt_ms"], n, rng, smoothing=0.85
    )
    network_jitter = autocorrelated_series(
        *n_params["network_jitter_ms"], n, rng, smoothing=0.75
    )
    packet_loss = autocorrelated_series(
        *n_params["packet_loss_rate"], n, rng, smoothing=0.8
    )

    # --- Derived metrics (throughput and latency) ---
    # Base throughput depends on contention and protocol
    protocol_efficiency = {
        "OCC":  {"low": 1.0, "high": 0.5},
        "2PL":  {"low": 0.7, "high": 0.8},
        "MVCC": {"low": 0.85, "high": 0.75},
    }
    eff = protocol_efficiency.get(protocol, {"low": 0.7, "high": 0.7})

    base_throughput = txn_rate * eff[contention] * (1 - conflict_rate * 0.5)
    # Network degradation reduces throughput
    network_penalty = 1.0 / (1.0 + network_rtt / 100.0)
    throughput = base_throughput * network_penalty
    throughput = np.maximum(throughput, 1.0)  # never zero

    # Latency: base + network + contention penalty
    base_latency = 1.0 + conflict_rate * 50 + rng.normal(0, 2, n)
    avg_latency = np.abs(base_latency + network_rtt * 0.5 +
                         queue_length * 0.1)
    avg_latency = np.maximum(avg_latency, 0.1)

    # p95 and p99 are always >= average
    p95_latency = avg_latency * rng.uniform(1.5, 3.0, n)
    p99_latency = p95_latency * rng.uniform(1.2, 2.5, n)

    return pd.DataFrame({
        "concurrent_transactions": concurrent_txns,
        "transaction_rate": np.round(txn_rate, 2),
        "conflict_rate": np.round(conflict_rate, 4),
        "abort_rate": np.round(abort_rate, 4),
        "queue_length": queue_length,
        "network_rtt_ms": np.round(network_rtt, 2),
        "network_jitter_ms": np.round(network_jitter, 2),
        "packet_loss_rate": np.round(packet_loss, 6),
        "throughput_tps": np.round(throughput, 2),
        "average_latency_ms": np.round(avg_latency, 2),
        "p95_latency_ms": np.round(p95_latency, 2),
        "p99_latency_ms": np.round(p99_latency, 2),
    })


def generate_dynamic_scenario(
    n: int,
    scenario_name: str,
    params: dict,
    rng: np.random.Generator,
    protocol: str = "MVCC",
) -> pd.DataFrame:
    """Generate a scenario with a sudden change mid-experiment.

    The first half uses one condition, the second half another, with a
    brief transition period.
    """
    mid = n // 2
    transition = max(5, n // 20)  # ~5% transition window

    if scenario_name == "sudden_workload_spike":
        part1 = generate_correlated_metrics(
            mid, "low", "normal", params, rng, protocol)
        part2 = generate_correlated_metrics(
            n - mid, "high", "normal", params, rng, protocol)
    elif scenario_name == "sudden_network_degradation":
        part1 = generate_correlated_metrics(
            mid, "low", "normal", params, rng, protocol)
        part2 = generate_correlated_metrics(
            n - mid, "low", "degraded", params, rng, protocol)
    elif scenario_name == "simultaneous_change":
        part1 = generate_correlated_metrics(
            mid, "low", "normal", params, rng, protocol)
        part2 = generate_correlated_metrics(
            n - mid, "high", "degraded", params, rng, protocol)
    else:
        # Unknown scenario: just generate low/normal
        return generate_correlated_metrics(n, "low", "normal", params, rng, protocol)

    # Concatenate with smooth transition
    df = pd.concat([part1, part2], ignore_index=True)

    # Smooth the transition region
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    start = mid - transition // 2
    end = mid + transition // 2
    for col in numeric_cols:
        vals = df[col].values.copy()
        if start > 0 and end < len(vals):
            transition_vals = np.linspace(
                vals[start], vals[end], end - start + 1)
            vals[start:end + 1] = transition_vals
            df[col] = vals

    return df


def generate_full_dataset(config: dict) -> pd.DataFrame:
    """Generate the complete synthetic dataset.

    Returns a DataFrame with all scenarios, clearly labelled.
    """
    syn_cfg = config["synthetic"]
    rng = np.random.default_rng(syn_cfg["random_seed"])
    params = syn_cfg["parameters"]
    n_obs = syn_cfg["observations_per_scenario"]
    interval = syn_cfg["sampling_interval_sec"]
    protocols = syn_cfg["protocols"]

    all_data = []
    exp_id = 0
    base_time = datetime(2026, 1, 1, 0, 0, 0)

    scenarios = syn_cfg["scenarios"]
    workload_types = scenarios["workload_types"]
    rw_ratios = scenarios["read_write_ratios"]
    contention_levels = scenarios["contention_levels"]
    network_conditions = scenarios["network_conditions"]

    # --- Static scenarios ---
    for wl_idx, workload in enumerate(workload_types):
        rw_ratio = rw_ratios[wl_idx]
        for contention in contention_levels:
            for network in network_conditions:
                # Assign protocol based on conditions (for diversity)
                protocol = rng.choice(protocols)
                exp_id += 1
                exp_name = f"exp_{exp_id:04d}"

                df = generate_correlated_metrics(
                    n_obs, contention, network, params, rng, protocol)

                # Add metadata columns
                timestamps = [
                    base_time + timedelta(seconds=i * interval)
                    for i in range(n_obs)
                ]
                df.insert(0, "timestamp", timestamps)
                df.insert(1, "experiment_id", exp_name)
                df.insert(2, "workload_type", workload)
                df.insert(3, "read_write_ratio", rw_ratio)
                df["active_protocol"] = protocol
                df["protocol_switch_count"] = 0
                df["switching_overhead_ms"] = 0.0

                all_data.append(df)

                # Advance base time for next experiment
                base_time += timedelta(seconds=n_obs * interval + 60)

    # --- Dynamic scenarios ---
    for dyn_scenario in scenarios.get("dynamic_scenarios", []):
        name = dyn_scenario["name"]
        for protocol in protocols:
            exp_id += 1
            exp_name = f"exp_{exp_id:04d}"

            df = generate_dynamic_scenario(
                n_obs, name, params, rng, protocol)

            timestamps = [
                base_time + timedelta(seconds=i * interval)
                for i in range(n_obs)
            ]
            df.insert(0, "timestamp", timestamps)
            df.insert(1, "experiment_id", exp_name)
            df.insert(2, "workload_type", "mixed")
            df.insert(3, "read_write_ratio", 0.5)
            df["active_protocol"] = protocol
            df["protocol_switch_count"] = 0
            df["switching_overhead_ms"] = 0.0

            all_data.append(df)
            base_time += timedelta(seconds=n_obs * interval + 60)

    dataset = pd.concat(all_data, ignore_index=True)

    print(f"Generated {len(dataset)} total observations across "
          f"{exp_id} experiments.")
    print(f"Columns: {list(dataset.columns)}")

    return dataset


def main():
    """Generate and save the synthetic dataset."""
    config = load_config()
    sample_dir = Path(PROJECT_ROOT) / config["data"]["sample_dir"]
    sample_dir.mkdir(parents=True, exist_ok=True)
    filename = config["synthetic"].get("sample_filename",
                                       "synthetic_experiment_data.csv")
    output_path = sample_dir / filename

    print("=" * 60)
    print("SYNTHETIC DATA GENERATION")
    print("=" * 60)
    print()
    print("WARNING: This generates SYNTHETIC data for pipeline testing.")
    print("It is NOT real experimental data.")
    print()

    dataset = generate_full_dataset(config)
    dataset.to_csv(output_path, index=False)

    print(f"\nSaved to: {output_path}")
    print(f"Shape: {dataset.shape}")
    print(f"\nExperiment summary:")
    summary = dataset.groupby("experiment_id").agg(
        workload=("workload_type", "first"),
        protocol=("active_protocol", "first"),
        n_obs=("timestamp", "count"),
        mean_conflict=("conflict_rate", "mean"),
        mean_rtt=("network_rtt_ms", "mean"),
    )
    print(summary.to_string())

    # Also save a manifest
    manifest = {
        "source": "synthetic",
        "generated_at": datetime.now().isoformat(),
        "description": ("Synthetic experiment data for pipeline testing. "
                        "NOT real experimental results."),
        "n_experiments": int(dataset["experiment_id"].nunique()),
        "n_observations": len(dataset),
        "config_file": "config.yaml",
    }
    manifest_path = sample_dir / "SYNTHETIC_DATA_MANIFEST.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False)
    print(f"\nManifest saved to: {manifest_path}")


if __name__ == "__main__":
    main()

