"""
scripts/collect_metrics.py
Metric collection script — adapter interface for real benchmarks.

This script defines the INTERFACE for collecting metrics from real
database benchmarks. It does NOT run real benchmarks (which require
YCSB, CCBench, and a distributed database to be installed).

For pipeline testing, use scripts/generate_workloads.py instead.

To collect real data, you need:
  1. A distributed database (e.g. CockroachDB, TiDB).
  2. YCSB installed and configured.
  3. Linux/WSL with tc netem for network simulation.
  4. CCBench or equivalent for CC-specific metrics.

See docs/experiment_protocol.md for full setup instructions.
"""

import sys
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional
import csv
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class BenchmarkAdapter(ABC):
    """Abstract adapter for collecting metrics from a database benchmark.

    Subclass this for each specific benchmark/database combination.
    """

    @abstractmethod
    def setup(self, config: dict) -> None:
        """Prepare the benchmark environment."""
        pass

    @abstractmethod
    def run_workload(self, workload_config: dict) -> dict:
        """Run a workload and return collected metrics.

        Returns
        -------
        dict with metric values matching the dataset schema.
        """
        pass

    @abstractmethod
    def get_protocol_metrics(self) -> dict:
        """Get current CC protocol metrics from the database.

        Returns
        -------
        dict with protocol-specific metrics (conflict_rate, abort_rate, etc.).
        """
        pass

    @abstractmethod
    def get_network_metrics(self) -> dict:
        """Get current network metrics.

        Returns
        -------
        dict with network_rtt_ms, network_jitter_ms, packet_loss_rate.
        """
        pass

    @abstractmethod
    def teardown(self) -> None:
        """Clean up after experiments."""
        pass


class YCSBAdapter(BenchmarkAdapter):
    """Adapter for YCSB (Yahoo! Cloud Serving Benchmark).

    YCSB provides:
      - Workload generation (read, update, scan, insert operations).
      - Throughput (operations/sec).
      - Latency (average, p95, p99).

    YCSB does NOT provide:
      - Conflict rate (depends on the database's CC implementation).
      - Abort rate (YCSB retries transparently in most bindings).
      - Queue length (internal database metric).
      - Active CC protocol information.

    These must be collected from the database directly.

    Installation:
      git clone https://github.com/brianfrankcooper/YCSB.git
      cd YCSB
      mvn -pl site.ycsb:ycsb-binding-parent -am clean package -DskipTests
    """

    def setup(self, config: dict) -> None:
        print("YCSB adapter: setup not yet implemented.")
        print("Required: YCSB installation + database binding.")
        print("See: https://github.com/brianfrankcooper/YCSB")

    def run_workload(self, workload_config: dict) -> dict:
        raise NotImplementedError(
            "YCSB workload execution requires YCSB to be installed. "
            "Use scripts/generate_workloads.py for synthetic data."
        )

    def get_protocol_metrics(self) -> dict:
        raise NotImplementedError(
            "Protocol metrics must be collected from the database, "
            "not from YCSB."
        )

    def get_network_metrics(self) -> dict:
        raise NotImplementedError(
            "Network metrics require Linux tc/netem or ping measurements."
        )

    def teardown(self) -> None:
        pass


class MetricCollector:
    """Collects and writes metrics to CSV files.

    Parameters
    ----------
    output_dir : str
        Directory for output CSV files.
    """

    FIELDNAMES = [
        "timestamp", "experiment_id", "workload_type", "read_write_ratio",
        "concurrent_transactions", "transaction_rate", "conflict_rate",
        "abort_rate", "queue_length", "network_rtt_ms", "network_jitter_ms",
        "packet_loss_rate", "throughput_tps", "average_latency_ms",
        "p95_latency_ms", "p99_latency_ms", "active_protocol",
        "protocol_switch_count", "switching_overhead_ms",
    ]

    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._writer = None

    def start_experiment(self, experiment_id: str):
        """Open a CSV file for a new experiment."""
        path = self.output_dir / f"{experiment_id}.csv"
        self._file = open(path, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.FIELDNAMES)
        self._writer.writeheader()
        print(f"Collecting metrics to {path}")

    def record(self, metrics: dict):
        """Record a single observation."""
        if self._writer is None:
            raise RuntimeError("No experiment started. Call start_experiment().")

        # Add timestamp if not present
        if "timestamp" not in metrics:
            metrics["timestamp"] = datetime.now().isoformat()

        # Write only known fields
        row = {k: metrics.get(k, "") for k in self.FIELDNAMES}
        self._writer.writerow(row)
        self._file.flush()

    def end_experiment(self):
        """Close the current experiment file."""
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None


def main():
    print("=" * 60)
    print("METRIC COLLECTION")
    print("=" * 60)
    print()
    print("This script requires external benchmark tools.")
    print()
    print("For SYNTHETIC data (pipeline testing):")
    print("  python scripts/generate_workloads.py")
    print()
    print("For REAL data collection, you need:")
    print("  1. A distributed database (CockroachDB, TiDB, VoltDB)")
    print("  2. YCSB: https://github.com/brianfrankcooper/YCSB")
    print("  3. Linux tc netem for network simulation")
    print("  4. CCBench: https://github.com/thawk105/ccbench")
    print()
    print("See docs/experiment_protocol.md for instructions.")


if __name__ == "__main__":
    main()

