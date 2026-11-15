"""
scripts/run_matrix_experiments.py
Sequential, controlled real experiment matrix runner.

Runs controlled physical experiments one-by-one against CockroachDB,
verifying complete teardown and isolation between each run.
"""

import sys
import time
import subprocess
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

EXPERIMENTS = [
    {
        "id": "exp_real_0005",
        "workload": "B",
        "concurrency": 16,
        "net_delay": 35.0,
        "net_jitter": 8.0,
        "net_loss": 0.2,
        "desc": "Controlled Workload Shift: Workload B (95/5 Read-heavy), Concurrency 16, Delay 35ms"
    },
    {
        "id": "exp_real_0006",
        "workload": "C",
        "concurrency": 16,
        "net_delay": 35.0,
        "net_jitter": 8.0,
        "net_loss": 0.2,
        "desc": "Controlled Workload Shift: Workload C (100% Read), Concurrency 16, Delay 35ms"
    },
    {
        "id": "exp_real_0007",
        "workload": "A",
        "concurrency": 32,
        "net_delay": 35.0,
        "net_jitter": 8.0,
        "net_loss": 0.2,
        "desc": "Controlled Concurrency Shift: Workload A, Concurrency 32 (High Contention), Delay 35ms"
    },
    {
        "id": "exp_real_0008",
        "workload": "A",
        "concurrency": 16,
        "net_delay": 15.0,
        "net_jitter": 3.0,
        "net_loss": 0.0,
        "desc": "Controlled Network Shift: Workload A, Concurrency 16, Low Network Delay (15ms)"
    },
    {
        "id": "exp_real_0009",
        "workload": "A",
        "concurrency": 16,
        "net_delay": 55.0,
        "net_jitter": 12.0,
        "net_loss": 0.5,
        "desc": "Controlled Network Shift: Workload A, Concurrency 16, High Network Delay (55ms)"
    },
]


def ensure_clean_environment():
    """Ensure no stale processes or tc rules exist before starting a run."""
    print("[RUNNER] Ensuring pristine environment...")
    subprocess.run(["pkill", "-9", "-f", "cockroach"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["pkill", "-9", "-f", "crdb_ycsb"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    subprocess.run(["sudo", "/usr/sbin/tc", "qdisc", "del", "dev", "lo", "root"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    time.sleep(2)


def run_single(exp: dict) -> bool:
    print("\n" + "=" * 70)
    print(f"[RUNNER] Starting {exp['id']}: {exp['desc']}")
    print("=" * 70)
    ensure_clean_environment()

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_real_experiment.py"),
        f"--experiment-id={exp['id']}",
        "--duration=45",
        "--sampling-interval=3.0",
        "--inject-network-at=20",
        f"--workload={exp['workload']}",
        f"--concurrency={exp['concurrency']}",
        f"--net-delay={exp['net_delay']}",
        f"--net-jitter={exp['net_jitter']}",
        f"--net-loss={exp['net_loss']}",
    ]

    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"[RUNNER] ERROR: {exp['id']} failed with code {res.returncode}")
        return False

    csv_path = PROJECT_ROOT / "data" / "raw" / f"{exp['id']}.csv"
    if not csv_path.exists():
        print(f"[RUNNER] ERROR: CSV {csv_path} not found!")
        return False

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    print(f"[RUNNER] SUCCESS: {exp['id']} generated {len(reader)} samples.")
    pre = [float(r["throughput_tps"]) for r in reader if float(r.get("network_rtt_ms", 0)) < 10.0]
    post = [float(r["throughput_tps"]) for r in reader if float(r.get("network_rtt_ms", 0)) >= 10.0]
    pre_tps = sum(pre) / len(pre) if pre else 0.0
    post_tps = sum(post) / len(post) if post else 0.0
    print(f"          Pre-netem  TPS mean: {pre_tps:.1f}")
    print(f"          Post-netem TPS mean: {post_tps:.1f}")

    ensure_clean_environment()
    return True


def main():
    print("STARTING CONTROLLED REAL EXPERIMENT MATRIX")
    for exp in EXPERIMENTS:
        success = run_single(exp)
        if not success:
            print(f"[RUNNER] Aborting matrix due to failure in {exp['id']}")
            sys.exit(1)
        time.sleep(3)
    print("\n" + "=" * 70)
    print("ALL CONTROLLED MATRIX EXPERIMENTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()

