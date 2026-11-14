# Research Limitations and Threats to Validity

## 1. Threats to Internal Validity

### Synthetic Benchmark Testbed
- The initial quantitative experiments in this repository utilize a calibrated synthetic generator (`scripts/generate_workloads.py`) simulating known empirical relationships from database systems literature.
- **Limitation:** While temporal autocorrelation, Zipfian-like contention distributions, and network penalties are accurately represented, real distributed database engines introduce complex emergent phenomena such as deadlock detection latency, multi-node Raft consensus replication delays, and garbage collection pauses that are not fully captured by parametric simulation.
- **Mitigation:** The architecture provides explicit `BenchmarkAdapter` abstractions (`scripts/collect_metrics.py`) so real database traces (CockroachDB, TiDB, CCBench) can seamlessly replace the synthetic generator without changing downstream preprocessing, modeling, or controller logic.

### Protocol Switching Realizability
- The controller simulates switching penalties using an empirical cost matrix ($300\text{--}500\text{ ms}$).
- **Limitation:** In an operational SQL engine, hot switching from Two-Phase Locking to Optimistic Concurrency Control across distributed nodes is an active research challenge. Real-world systems require either a global quiescence point, epoch-based transitions, or dual-protocol compatibility modes.
- **Mitigation:** Section 3 of `docs/controller_design.md` explicitly details the lock draining and version chain requirements necessary before asserting production-safe deployment.

---

## 2. Threats to External Validity

### Workload Generalizability
- Workload generation assumes four canonical profiles: `read_heavy`, `write_heavy`, `mixed`, and `scan_heavy`.
- **Limitation:** Enterprise workloads often feature irregular diurnal cycles, unpredictable flash sales, and ad-hoc analytical queries (HTAP) with long read transactions conflicting with bursts of writes.
- **Future Direction:** Integrating real-world transaction traces such as Alibaba Cloud or TPC-C / TPC-E benchmark traces.

### Prediction Horizon Sensitivity
- Models were trained with a fixed horizon of $h=1$ step (5 seconds).
- **Limitation:** A 5-second horizon is suitable for protocol draining, but larger distributed clusters with geographically separated data centers may require multi-step lookaheads (15s to 30s) or hierarchical horizon planning.

