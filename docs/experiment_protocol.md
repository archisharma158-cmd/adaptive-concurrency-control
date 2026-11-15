# Experimental Protocol for Real Database Benchmarks

## 1. Prerequisites and Environment Setup
This research implements and validates a live distributed database experimental harness in Windows + WSL 2 (Ubuntu 24.04 LTS), running a 3-node CockroachDB cluster with network latency injection and native workload execution.

### A. Distributed Database Selection & Architecture: CockroachDB v23.2.0
- **Engine Architecture:** Multi-node distributed SQL utilizing Raft consensus across partitions and in-memory storage (`--store=type=mem,size=1GB`).
- **Isolation & Concurrency Model:** Strict Serializable Isolation implemented via Multi-Version Concurrency Control (MVCC) with lockless optimistic read intents, write intent resolution, and transaction restarts (`txn_restarts_writetoooldmulti`).
- **Cluster Topology:**
  - Node 1: SQL/Raft Port `26257`, HTTP/Prometheus Port `8080` (Cluster coordinator).
  - Node 2: SQL/Raft Port `26258`, HTTP/Prometheus Port `8081`.
  - Node 3: SQL/Raft Port `26259`, HTTP/Prometheus Port `8082`.
- **Process Isolation:** Nodes run in user space detached from session SIGHUP using `/usr/bin/setsid nohup` and direct PID tracking in `/tmp/cockroach_node*.pid`.

---

## 2. Workload Generation with CockroachDB Native YCSB
1. **Workload Ingestion:**
   Native YCSB workloads are pre-compiled and run directly through the CockroachDB binary (`cockroach workload init/run ycsb`).
   ```bash
   # Initialize 2,000 to 10,000 records
   cockroach workload init ycsb "postgresql://root@127.0.0.1:26257/ycsb?sslmode=disable" --record-count 2000

   # Run workload under high concurrency
   cockroach workload run ycsb "postgresql://root@127.0.0.1:26257/ycsb?sslmode=disable" \
     --workload A --concurrency 16 --duration 60s
   ```
2. **Workload Configurations:**
   - **Workload A (50/50 Read/Write):** Simulates high write contention (`read_write_ratio: 0.5`).
   - **Workload B (95/5 Read/Write):** Simulates read-heavy low contention (`read_write_ratio: 0.95`).
   - **Workload C (100% Read):** Zero-write baseline (`read_write_ratio: 1.0`).
   - **Contention Stress:** High concurrency (16 to 64 threads) concentrated on 2,000 keys causes frequent concurrent MVCC write intent conflicts and timestamp pushes.

---

## 3. Network Emulation with Linux `tc netem`
Network degradation is deterministically injected onto the loopback interface (`lo`) or virtual ethernet interface (`eth0`) in WSL 2 via Linux traffic control (`tc`):

```bash
# Apply 35ms base latency, 8ms jitter, and 0.2% packet loss
sudo /usr/sbin/tc qdisc add dev lo root netem delay 35ms 8ms loss 0.2%

# Verify active queue discipline
sudo /usr/sbin/tc qdisc show dev lo

# Safe teardown (guaranteed on test exit)
sudo /usr/sbin/tc qdisc del dev lo root
```

---

## 4. Telemetry Harvesting and Metrics Pipeline
Telemetry is sampled synchronously at configurable intervals ($\Delta t = 3\text{s}$ or $5\text{s}$) via `scripts/collect_metrics.py` and `scripts/run_real_experiment.py`:
1. **Transaction Throughput & Latency Percentiles:** Parsed in real time from live CockroachDB YCSB stdout logs (`/tmp/crdb_ycsb.log`), extracting instantaneous TPS, mean latency, p95, and p99.
2. **Cluster Concurrency Conflicts:** Harvested from Prometheus metrics scraping endpoints (`http://localhost:8080/_status/vars`), monitoring `txn_restarts_writetoooldmulti` across all active nodes.
3. **Physical Network RTT & Jitter:** Measured via repeated active TCP handshakes to the SQL port (`127.0.0.1:26257`), computing instantaneous mean RTT and sample standard deviation (jitter).
4. **Data Segregation:** Real physical telemetry is strictly exported to `data/raw/<experiment_id>.csv`, completely segregated from synthetic test data in `data/sample/`.

---

## 5. Academic Integrity & Protocol Scope
CockroachDB's engine physically executes MVCC. It does NOT possess an internal toggle to swap its storage engine to pure 2-Phase Locking (2PL) or classical Optimistic Concurrency Control (OCC) at runtime.
Therefore, in this academic research:
- Physical measurements (`exp_real_*.csv`) reflect genuine MVCC performance under real network latency and contention.
- The comparative switching framework evaluates whether a theoretical or adaptive multi-engine system should recommend switching away from MVCC under detected conditions, and calculates the exact switching cost overhead incurred.

