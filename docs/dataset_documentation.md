# Dataset Documentation

## 1. Overview and Data Lineage
This document specifies the exact dataset schema, collection mechanisms, units, and integrity standards for the experimental evaluation of predictive concurrency control.

- **Sample / Synthetic Data:** Stored in `data/sample/synthetic_experiment_data.csv`. Accompanied by `data/sample/SYNTHETIC_DATA_MANIFEST.yaml` explicitly identifying it as simulated for pipeline testing.
- **Processed Clean Data:** Stored in `data/processed/processed_data.csv`. Contains cleaned records, imputed features, engineered time-series lags, and shifted future prediction targets.
- **Raw Real Experimental Data:** Reserved directory `data/raw/` for incoming live database traces.

---

## 2. Feature Schema Specification

| Feature Name | Data Type | Units | Bounds / Domain | Source / Method of Measurement |
| :--- | :--- | :--- | :--- | :--- |
| `timestamp` | datetime (ISO 8601) | YYYY-MM-DD HH:MM:SS | Monotonic per experiment | System clock sampling at 5-second intervals. |
| `experiment_id` | string | Identifier (`exp_0001`...) | Unique experiment run tag | Automated experiment orchestrator. |
| `workload_type` | categorical | string (`read_heavy`, `write_heavy`, `mixed`, `scan_heavy`) | Workload profile generator (e.g. YCSB parameterization). |
| `read_write_ratio` | float | Ratio [0.0, 1.0] | Configured workload generator parameter. |
| `concurrent_transactions`| integer | Count | $[1, 10000]$ | Active concurrent client client threads / connection pool. |
| `transaction_rate` | float | Transactions / sec | $[0.0, \infty)$ | Injected transaction arrival rate from client harness. |
| `conflict_rate` | float | Ratio [0.0, 1.0] | Database transaction manager telemetry ($\frac{\text{Conflicting Ops}}{\text{Total Ops}}$). |
| `abort_rate` | float | Ratio [0.0, 1.0] | Transaction manager abort counter ($\frac{\text{Aborted Txns}}{\text{Committed + Aborted Txns}}$). |
| `queue_length` | integer | Count | $[0, \infty)$ | Transaction engine wait queue or lock wait queue depth. |
| `network_rtt_ms` | float | Milliseconds | $[0.0, \infty)$ | Node-to-node ICMP or application-level ping round-trip time. |
| `network_jitter_ms` | float | Milliseconds | $[0.0, \infty)$ | Standard deviation or variation in successive RTT samples. |
| `packet_loss_rate` | float | Ratio [0.0, 1.0] | Network interface packet drop telemetry (via `tc netem` or `ip link`). |
| `throughput_tps` | float | Transactions / sec | $[0.0, \infty)$ | Successfully committed transactions per second. |
| `average_latency_ms` | float | Milliseconds | $[0.0, \infty)$ | Arithmetic mean elapsed transaction completion latency. |
| `p95_latency_ms` | float | Milliseconds | $[0.0, \infty)$ | 95th percentile transaction latency over sample window. |
| `p99_latency_ms` | float | Milliseconds | $[0.0, \infty)$ | 99th percentile transaction tail latency over sample window. |
| `active_protocol` | categorical | string (`OCC`, `2PL`, `MVCC`) | Concurrency control protocol currently active in the database. |
| `protocol_switch_count` | integer | Count | Cumulative number of protocol transitions executed in run. |
| `switching_overhead_ms` | float | Milliseconds | Aggregate latency penalty attributable to draining & state switch. |

---

## 3. Data Integrity & Validation Constraints
The pipeline enforces the following physical and logical consistency invariants via `src/data/validation.py`:
1. **Latency Ordering:** For every observation $i$:
   $$\text{average\_latency\_ms} \le \text{p95\_latency\_ms} \le \text{p99\_latency\_ms}$$
2. **Rate Bounds:** All rate fields (`conflict_rate`, `abort_rate`, `packet_loss_rate`, `read_write_ratio`) must be constrained strictly within $[0.0, 1.0]$.
3. **Temporal Ordering:** Timestamps within each `experiment_id` partition must be strictly monotonic:
   $$t_{k+1} > t_k \quad \forall k \in \text{experiment\_id}$$
4. **Target Shift Invariant:** For prediction target calculation with horizon $h$, the target at observation $k$ must equal the actual measurement at $k+h$:
   $$\text{target\_conflict\_rate}_k \equiv \text{conflict\_rate}_{k+h}$$
   Any observation at the boundary of an experiment where $k+h > N_{\text{exp}}$ must evaluate to `NaN` and be excluded from training.

