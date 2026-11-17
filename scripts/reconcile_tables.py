"""
scripts/reconcile_tables.py
Reconciles raw measurements, transition states, and steady-state post-injection
telemetry across all verified physical database experiments.
"""

import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    combined_path = PROJECT_ROOT / "data" / "raw" / "combined_real_dataset.csv"
    df = pd.read_csv(combined_path)

    print(f"{'Exp ID':<15} | {'Workload':<12} | {'Conc':<4} | {'Pre TPS':<10} | {'Trans TPS':<10} | {'Steady Post TPS':<16} | {'All Post TPS':<13} | {'Steady Lat':<12}")
    print("-" * 105)

    reconciled_rows = []

    for exp_id, g in df.groupby("experiment_id"):
        pre = g[g["network_rtt_ms"] < 10.0]
        post = g[g["network_rtt_ms"] >= 10.0]

        pre_tps = pre["throughput_tps"].mean() if not pre.empty else 0.0
        pre_lat = pre["average_latency_ms"].mean() if not pre.empty else 0.0

        trans_tps = post["throughput_tps"].iloc[0] if not post.empty else 0.0
        steady_post = post.iloc[1:] if len(post) > 1 else post
        steady_tps = steady_post["throughput_tps"].mean() if not steady_post.empty else 0.0
        steady_lat = steady_post["average_latency_ms"].mean() if not steady_post.empty else 0.0
        steady_p99 = steady_post["p99_latency_ms"].mean() if not steady_post.empty else 0.0
        steady_rtt = steady_post["network_rtt_ms"].mean() if not steady_post.empty else 0.0
        all_post_tps = post["throughput_tps"].mean() if not post.empty else 0.0

        wl = g["workload_type"].iloc[0]
        conc = g["concurrent_transactions"].iloc[0]

        print(f"{exp_id:<15} | {wl:<12} | {conc:<4} | {pre_tps:<10.1f} | {trans_tps:<10.1f} | {steady_tps:<16.1f} | {all_post_tps:<13.1f} | {steady_lat:<12.2f}")

        reconciled_rows.append({
            "Experiment ID": exp_id,
            "Workload Type": wl,
            "Concurrency": conc,
            "Pre-Net TPS": round(pre_tps, 1),
            "Pre-Net Lat (ms)": round(pre_lat, 2),
            "Transition TPS": round(trans_tps, 1),
            "Steady Post-Net TPS": round(steady_tps, 1),
            "All Post-Net TPS": round(all_post_tps, 1),
            "Steady Post Lat (ms)": round(steady_lat, 2),
            "Steady Post P99 (ms)": round(steady_p99, 2),
            "Steady Post RTT (ms)": round(steady_rtt, 2),
            "Max Conflict Rate": round(g["conflict_rate"].max(), 5),
        })

    reconciled_df = pd.DataFrame(reconciled_rows)
    out_csv = PROJECT_ROOT / "results" / "reconciled_experiment_summary.csv"
    reconciled_df.to_csv(out_csv, index=False)
    print(f"\nSaved reconciled summary to {out_csv}")


if __name__ == "__main__":
    main()
