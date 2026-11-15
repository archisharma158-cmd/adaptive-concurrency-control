# Research Limitations and Threats to Validity

## 1. Threats to Internal Validity

### CockroachDB Protocol Boundary (Physical MVCC vs Simulated Protocol Switching)
- In our live physical experiments (`scripts/run_real_experiment.py`), CockroachDB v23.2.0 executed as a 3-node cluster utilizing Multi-Version Concurrency Control (MVCC) with multi-node Raft consensus and Strict Serializable isolation.
- **Physical Limitation:** CockroachDB's storage engine (Pebble) and transaction manager do not expose runtime hooks to dynamically replace the internal MVCC engine with pure Two-Phase Locking (2PL) or classical Optimistic Concurrency Control (OCC).
- **Academic Scope & Rigor:** The collected physical telemetry (`data/raw/exp_real_0001.csv` and `exp_real_0004` through `exp_real_0009.csv`) genuinely captures real-world MVCC execution, lock contention restarts (`txn_restarts_writetoooldmulti`), and TCP socket latency. The predictive switching framework evaluates whether an adaptive system *should* transition protocols and simulates switching penalties based on database queueing literature, but does not claim CockroachDB physically replaced its storage engine at runtime.

### Network Emulation Scope on the Loopback Interface (`lo`)
- In our WSL 2 testbed, `tc netem` delay, jitter, and packet loss were applied directly to the loopback interface (`lo`), where all three CockroachDB nodes (`127.0.0.1:26257`, `26258`, `26259`) and the client workload process reside.
- **Consequence:** Loopback emulation affects **both** client-to-coordinator SQL connections and inter-node Raft consensus replication traffic.
- **Systems Dynamic:** When $35\text{ms}$ delay is applied, the TCP connection handshake round-trip is $2 \times 35\text{ms} = 70\text{ms}$. An additional $70\text{ms}$ is incurred during two-phase Raft consensus commit across nodes, resulting in total transaction round-trip latencies of $\sim 140\text{ms}$. While this realistically models a scenario where an entire cluster partition or datacenter link experiences WAN degradation, it does not isolate client-only access network latency from inter-cluster consensus latency.

### Execution Isolation and Exclusion of Contaminated Pilot Runs
- During early exploratory runs, `exp_real_0002` and `exp_real_0003` were accidentally executed concurrently in overlapping background tasks against the same port allocation.
- In `exp_real_0003`, when `exp_real_0002` completed and executed its `cleanup_all()` handler, it sent `pkill -9 -f cockroach`, abruptly terminating the cluster while `exp_real_0003` was midway through sampling. This caused `exp_real_0003` to poll a dead port and log hardcoded fallback default values (`tps=0.0`, `lat=1.0ms`, `rtt=0.5ms`).
- **Resolution & Integrity:** To uphold scientific honesty, both `exp_real_0002.csv` and `exp_real_0003.csv` were preserved in `data/raw/` with descriptive YAML metadata explicitly documenting the failure mode, and were excluded from clean model training and baseline comparison. All reported results rely strictly on the 7 independently verified runs (`exp_real_0001`, `exp_real_0004`, `exp_real_0005`, `exp_real_0006`, `exp_real_0007`, `exp_real_0008`, `exp_real_0009`).

---

## 2. Threats to External Validity

### Workload Generalizability
- Workload generation utilized YCSB canonical profiles: Workload A (Write-heavy 50/50), Workload B (Read-heavy 95/5), and Workload C (Read-only 100/0) with Zipfian key access distributions.
- **Limitation:** Enterprise workloads often feature irregular diurnal cycles, unpredictable flash sales, and ad-hoc analytical queries (HTAP) with long read transactions conflicting with bursts of writes.
- **Future Direction:** Integrating real-world transaction traces such as Alibaba Cloud or TPC-C / TPC-E benchmark traces.

### Prediction Horizon Sensitivity
- Models were evaluated with a single-step lookahead horizon ($h=1$ step, corresponding to $3\text{s}$ or $5\text{s}$).
- **Limitation:** A 3-to-5 second horizon is well-suited for proactive pipeline draining before a protocol switch, but large multi-datacenter clusters spanning wide geographic regions may benefit from hierarchical multi-step forecasting horizons (15s to 30s).
