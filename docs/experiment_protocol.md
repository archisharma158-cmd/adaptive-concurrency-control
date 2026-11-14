# Experimental Protocol for Real Database Benchmarks

## 1. Prerequisites and Environment Setup
To transition this research from synthetic simulation to live distributed database experiments, the following components must be deployed.

### A. Distributed Database Selection
- **Option 1: CockroachDB (Recommended)**
  - Distributed SQL with multi-node Raft consensus.
  - Native support for MVCC and serializable isolation.
  - Exposes extensive internal Prometheus metrics on contention, transaction retries, and network RPC latencies.
- **Option 2: TiDB / TiKV**
  - Modular distributed architecture with TiKV storage engine utilizing MVCC and 2PC.
- **Option 3: CCBench (In-Memory Academic Testbed)**
  - C++ in-memory research benchmark explicitly implementing pure OCC, Silo, TicToc, 2PL, and MVCC variants.
  - Source: [github.com/thawk105/ccbench](https://github.com/thawk105/ccbench)

---

## 2. Workload Generation with YCSB
1. **Clone and Build YCSB:**
   ```bash
   git clone https://github.com/brianfrankcooper/YCSB.git
   cd YCSB
   mvn -pl site.ycsb:jdbc-binding -am clean package -DskipTests
   ```
2. **Workload Parameterization:**
   - **Workload A (50/50 Read/Write):** Simulates high write contention (`read_write_ratio: 0.5`).
   - **Workload B (95/5 Read/Write):** Simulates read-heavy low contention (`read_write_ratio: 0.95`).
   - **Hotspot Contention Injection:** Configure Zipfian key distribution (`requestdistribution=zipfian`) with parameter $\alpha \in [0.8, 1.2]$ to concentrate access on specific keys.

---

## 3. Network Emulation with Linux `tc netem`
Network degradation must be controlled deterministically on the database network interfaces. Since the host OS includes WSL 2 Ubuntu, execute network emulation in Linux:

```bash
# Example: Add 50ms latency with 10ms jitter and 1% packet loss
sudo tc qdisc add dev eth0 root netem delay 50ms 10ms loss 1%

# Verify current rules
sudo tc qdisc show dev eth0

# Reset network interface to normal
sudo tc qdisc del dev eth0 root
```

---

## 4. Metric Collection Adapter Integration
Use `scripts/collect_metrics.py` to instantiate `MetricCollector`. Implement the subclass methods in `BenchmarkAdapter`:
1. `run_workload()`: Wraps client YCSB invocation.
2. `get_protocol_metrics()`: Queries database `system.transaction_statistics` or Prometheus endpoint for instantaneous abort/conflict counts.
3. `get_network_metrics()`: Measures periodic socket RTT to coordinator nodes.
4. Records 5-second interval snapshots directly to `data/raw/<experiment_id>.csv`.

