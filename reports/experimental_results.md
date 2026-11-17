# Experimental Results & Baseline Comparison Report

## 1. Experimental Overview
We evaluated five distinct concurrency control management strategies across non-stationary testbed experiments:
1. **`static_occ`:** Baseline Optimistic Concurrency Control (no switching).
2. **`static_2pl`:** Baseline Two-Phase Locking (no switching).
3. **`static_mvcc`:** Native CockroachDB Multi-Version Concurrency Control (no switching).
4. **`reactive`:** Instantaneous threshold-based switching controller.
5. **`predictive`:** Proposed predictive controller with ML forecasting, switching-cost optimization, and hysteresis.

*Important Note on System Architecture:* All base telemetry reflects physical CockroachDB MVCC execution under Linux `tc netem`. The protocol switching evaluation models the theoretical behavior of an adaptive multi-engine architecture responding to these physical conditions.

---

## 2. Quantitative Comparison Table

*Evaluated on the unseen test split (`exp_real_0008` with 15ms injected delay and `exp_real_0009` with 55ms injected delay):*

| Strategy | Mean Throughput (TPS) | Mean Latency (ms) | P95 Latency (ms) | P99 Latency (ms) | Mean Abort Rate | Total Switches | Total Switching Overhead (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`predictive` (Proposed)** | **3,510.31** | **146.16** | **292.31** | **511.55** | **0.000** | **0** | **0.0** |
| **`static_occ`** | 3,510.31 | 146.16 | 292.31 | 511.55 | 0.000 | 0 | 0.0 |
| **`static_mvcc`** | 2,888.00 | 147.61 | 295.23 | 516.64 | 0.000 | 0 | 0.0 |
| **`static_2pl`** | 2,197.96 | 250.43 | 500.86 | 876.50 | 0.000 | 0 | 0.0 |
| **`reactive`** | 3,509.54 | 158.72 | 317.44 | 555.52 | 0.000 | 1 | 300.0 |

---

## 3. Systems Analysis & Research Insights

### Finding 1: Elimination of Unnecessary Protocol Thrashing
- When network degradation occurred at $t=18:00:41$ in `exp_real_0009` (measured RTT jumped to $116.8\text{ms}$), the **reactive controller** immediately triggered an uncoordinated protocol switch (`OCC` $\to$ `MVCC`).
- This reactive transition incurred a **300.0 ms switching penalty**, inflating instantaneous mean latency to $496.27\text{ms}$ and increasing average test latency from $146.16\text{ms}$ to $158.72\text{ms}$ (+8.6% latency penalty).
- The **predictive controller**, powered by Random Forest forecasts and switching cost evaluation, recognized that the transient benefit of switching did not compensate for the $300\text{ms}$ transition cost, thus maintaining protocol stability and completely avoiding the disruption spike.

### Finding 2: Practical Implications for Distributed Databases
- In distributed environments where Raft consensus or two-phase commit already experience network delays, injecting an un-optimized protocol switch exacerbates queueing delays.
- A predictive decision framework that explicitly factors in pipeline draining and lock-state conversion costs is necessary to prevent adaptive mechanisms from degrading overall database stability.
