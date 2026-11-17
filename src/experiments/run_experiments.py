"""
src/experiments/run_experiments.py
Experiment runner for baseline comparison.

Simulates running the three control strategies (static, reactive,
predictive) on the same workload scenarios and compares their
performance.

NOTE: This is a SIMULATION of what would happen if the controllers were
connected to a real database. The actual database performance numbers
are derived from the synthetic dataset. For real experiments, this module
would need adapters to an actual database system.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import yaml
import json

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.controller.decision_engine import (
    StaticController,
    ReactiveController,
    PredictiveController,
)
from src.controller.switching_cost import SwitchingCostEstimator


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def simulate_protocol_performance(
    row: pd.Series,
    protocol: str,
    switching_overhead: float = 0.0,
) -> dict:
    """Simulate performance metrics under a given protocol.

    This uses the protocol suitability model to adjust the base metrics.
    In a real experiment, these would come from actual database
    measurements.

    Parameters
    ----------
    row : pd.Series
        A single observation from the dataset.
    protocol : str
        The active protocol.
    switching_overhead : float
        Additional latency from a recent switch (ms).

    Returns
    -------
    dict with simulated performance metrics.
    """
    # Protocol efficiency factors (from database literature)
    efficiency = {
        "OCC": {
            "low_contention": 1.0,
            "high_contention": 0.4,
            "low_network": 1.0,
            "high_network": 0.6,
        },
        "2PL": {
            "low_contention": 0.7,
            "high_contention": 0.85,
            "low_network": 0.9,
            "high_network": 0.5,
        },
        "MVCC": {
            "low_contention": 0.85,
            "high_contention": 0.75,
            "low_network": 0.95,
            "high_network": 0.7,
        },
    }

    eff = efficiency.get(protocol, efficiency["MVCC"])

    # Determine condition categories
    contention = ("high_contention" if row.get("conflict_rate", 0) > 0.15
                  else "low_contention")
    network = ("high_network" if row.get("network_rtt_ms", 0) > 20
               else "low_network")

    contention_factor = eff[contention]
    network_factor = eff[network]
    combined_factor = contention_factor * network_factor

    base_throughput = row.get("throughput_tps", 100)
    base_latency = row.get("average_latency_ms", 10)

    sim_throughput = base_throughput * combined_factor
    sim_latency = base_latency / combined_factor + switching_overhead

    return {
        "throughput_tps": round(sim_throughput, 2),
        "average_latency_ms": round(sim_latency, 2),
        "p95_latency_ms": round(sim_latency * 2.0, 2),
        "p99_latency_ms": round(sim_latency * 3.5, 2),
        "abort_rate": round(row.get("abort_rate", 0) / combined_factor, 4),
        "conflict_rate": row.get("conflict_rate", 0),
    }


def run_strategy_experiment(
    df: pd.DataFrame,
    controller,
    strategy_name: str,
    contention_predictor=None,
    network_predictor=None,
    feature_cols: Optional[list] = None,
) -> pd.DataFrame:
    """Run a single strategy over the dataset and record results.

    Parameters
    ----------
    df : pd.DataFrame
        The experiment data (sorted by time).
    controller : BaseController
        The control strategy.
    strategy_name : str
    contention_predictor : optional
        ML model for contention prediction (predictive strategy only).
    network_predictor : optional
        ML model for network prediction (predictive strategy only).
    feature_cols : list, optional
        Feature columns for ML predictors.

    Returns
    -------
    pd.DataFrame with per-observation results.
    """
    results = []
    # If the controller is static with a fixed protocol, start with that protocol.
    # Otherwise, default to OCC as the initial baseline protocol.
    current_protocol = getattr(controller, "fixed_protocol", "OCC")
    switch_count = 0
    total_switching_overhead = 0.0

    for idx, row in df.iterrows():
        timestamp = row.get("timestamp", datetime.now())
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)

        current_contention = row.get("conflict_rate", 0.1)
        current_rtt = row.get("network_rtt_ms", 5.0)

        # Get predictions (for predictive controller)
        pred_contention = None
        pred_rtt = None

        if contention_predictor and feature_cols:
            try:
                features = row[feature_cols].to_frame().T
                pred_contention = float(contention_predictor.predict(features)[0])
            except Exception:
                pred_contention = None

        if network_predictor and feature_cols:
            try:
                features = row[feature_cols].to_frame().T
                pred_rtt = float(network_predictor.predict(features)[0])
            except Exception:
                pred_rtt = None

        # Make decision
        if strategy_name.startswith("static"):
            decision = controller.decide(
                current_protocol=current_protocol,
                current_time=timestamp,
            )
        elif strategy_name == "reactive":
            decision = controller.decide(
                current_protocol=current_protocol,
                current_contention=current_contention,
                current_network_rtt=current_rtt,
                current_time=timestamp,
            )
        elif strategy_name == "predictive":
            decision = controller.decide(
                current_protocol=current_protocol,
                predicted_contention=pred_contention,
                predicted_network_rtt=pred_rtt,
                current_contention=current_contention,
                current_network_rtt=current_rtt,
                current_time=timestamp,
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        # Apply decision
        switching_overhead = 0.0
        if decision.action == "switch":
            switch_count += 1
            switching_overhead = decision.switching_cost_ms
            total_switching_overhead += switching_overhead
            current_protocol = decision.recommended_protocol

        # Simulate performance under current protocol
        perf = simulate_protocol_performance(
            row, current_protocol, switching_overhead
        )

        results.append({
            "timestamp": timestamp,
            "experiment_id": row.get("experiment_id", ""),
            "strategy": strategy_name,
            "active_protocol": current_protocol,
            "decision_action": decision.action,
            "decision_reason": decision.reason,
            "switch_count_cumulative": switch_count,
            "switching_overhead_ms": switching_overhead,
            "total_switching_overhead_ms": total_switching_overhead,
            **perf,
        })

    return pd.DataFrame(results)


def run_all_experiments(
    data_path: str,
    config_path: str = "config.yaml",
    results_dir: str = "results",
    model_dir: str = "models/saved",
) -> pd.DataFrame:
    """Run all strategy experiments and compare.

    Parameters
    ----------
    data_path : str
        Path to processed data CSV.
    config_path : str
    results_dir : str
    model_dir : str

    Returns
    -------
    pd.DataFrame with benchmark comparison.
    """
    config = load_config(config_path)
    df = pd.read_csv(data_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Use a subset (last 20% = test split) for fair comparison
    pred_cfg = config.get("prediction", {})
    from src.data.preprocessing import chronological_experiment_split, get_feature_columns
    _, _, test_df = chronological_experiment_split(
        df,
        train_ratio=pred_cfg.get("train_ratio", 0.6),
        val_ratio=pred_cfg.get("val_ratio", 0.2),
        test_ratio=pred_cfg.get("test_ratio", 0.2),
    )

    feature_cols = get_feature_columns(df)

    # Try to load trained models
    contention_predictor = None
    network_predictor = None
    try:
        import joblib
        from src.models.predict import Predictor
        rf_cont = Path(model_dir) / "rf_contention.joblib"
        rf_net = Path(model_dir) / "rf_network.joblib"
        if rf_cont.exists():
            contention_predictor = joblib.load(rf_cont)
        if rf_net.exists():
            network_predictor = joblib.load(rf_net)
    except Exception as e:
        print(f"  Could not load models: {e}")

    all_results = []

    # 1. Static strategies
    for protocol in ["OCC", "2PL", "MVCC"]:
        print(f"\nRunning Static ({protocol})...")
        ctrl = StaticController(protocol, config_path)
        result = run_strategy_experiment(
            test_df, ctrl, f"static_{protocol.lower()}"
        )
        all_results.append(result)

    # 2. Reactive strategy
    print("\nRunning Reactive...")
    ctrl = ReactiveController(config_path)
    result = run_strategy_experiment(
        test_df, ctrl, "reactive"
    )
    all_results.append(result)

    # 3. Predictive strategy
    print("\nRunning Predictive...")
    ctrl = PredictiveController(config_path)
    result = run_strategy_experiment(
        test_df, ctrl, "predictive",
        contention_predictor=contention_predictor,
        network_predictor=network_predictor,
        feature_cols=feature_cols,
    )
    all_results.append(result)

    # Combine
    combined = pd.concat(all_results, ignore_index=True)

    # Generate summary
    summary = combined.groupby("strategy").agg(
        mean_throughput=("throughput_tps", "mean"),
        mean_latency=("average_latency_ms", "mean"),
        mean_p95_latency=("p95_latency_ms", "mean"),
        mean_p99_latency=("p99_latency_ms", "mean"),
        mean_abort_rate=("abort_rate", "mean"),
        total_switches=("switch_count_cumulative", "max"),
        total_switch_overhead=("total_switching_overhead_ms", "max"),
    ).round(4)

    # Save results
    results_path = Path(results_dir)
    results_path.mkdir(parents=True, exist_ok=True)

    combined.to_csv(results_path / "experiment_results_detailed.csv", index=False)
    summary.to_csv(results_path / "benchmark_comparison.csv")

    print(f"\n{'='*60}")
    print("BENCHMARK COMPARISON")
    print(f"{'='*60}")
    print(summary.to_string())
    print(f"\nDetailed results: {results_path / 'experiment_results_detailed.csv'}")
    print(f"Summary: {results_path / 'benchmark_comparison.csv'}")

    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run experiments")
    parser.add_argument("--data", type=str,
                        default="data/processed/processed_data.csv")
    parser.add_argument("--config", type=str, default="config.yaml")
    args = parser.parse_args()

    run_all_experiments(args.data, args.config)

