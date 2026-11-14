# Machine Learning Prediction Target Formulation

## 1. Research Motivation
In distributed concurrency control, reacting to current bottlenecks is often too late: by the time an abort storm or lock convoy is detected, thousands of distributed transactions have already failed or timed out.

Conversely, predicting **future workload contention** and **future network degradation** provides the controller with a planning window to gracefully drain in-flight transactions and transition to a more resilient protocol *before* degradation occurs.

---

## 2. Mathematical Definition of Targets

Let $t$ index discrete time intervals with sampling step $\Delta t = 5$ seconds. Let $h \ge 1$ denote the prediction horizon in steps.

### Target A: Future Contention (Continuous Regression)
$$\tau_{\text{contention}}(t) = y_{C, t+h} = \text{conflict\_rate}(t + h)$$
- **Default Horizon:** $h = 1$ step ($5$ seconds ahead).
- **Physical Meaning:** Expected fraction of transaction operations that will encounter read-write or write-write conflicts in the subsequent window.

### Target B: Future Network Degradation (Continuous Regression)
$$\tau_{\text{network}}(t) = y_{R, t+h} = \text{network\_rtt\_ms}(t + h)$$
- **Default Horizon:** $h = 1$ step ($5$ seconds ahead).
- **Physical Meaning:** Expected node-to-node round-trip communication latency during the subsequent window.

### Target C & D: Derived Classification Labels
For operational alerting, continuous predictions can be discretized using domain thresholds $\theta_C$ and $\theta_R$:
$$L_{\text{contention}}(t) = \begin{cases} 1 & \text{if } y_{C, t+h} > \theta_C \quad (\text{High Contention}) \\ 0 & \text{otherwise} \quad (\text{Low Contention}) \end{cases}$$

$$L_{\text{network}}(t) = \begin{cases} 1 & \text{if } y_{R, t+h} > \theta_R \quad (\text{Degraded Network}) \\ 0 & \text{otherwise} \quad (\text{Normal Network}) \end{cases}$$
Where $\theta_C = 0.15$ and $\theta_R = 20.0\text{ ms}$ per `config.yaml`.

---

## 3. Data Leakage Prevention & Chronological Splitting
To ensure realistic evaluation for academic publication:
1. **Target Separation:** Targets are strictly future-shifted values within each `experiment_id` partition.
2. **Feature Censoring:** No contemporaneous target or future-derived measurement is present in the feature matrix $X_t$. The feature set consists solely of:
   - Current measurements at time $t$
   - Historical lag features at $t - 1, t - 2, t - 3, t - 5$
   - Rolling window statistics (mean, standard deviation) over past $w \in \{3, 5, 10\}$ steps.
3. **Chronological Experiment Splitting:**
   - Shuffling rows randomly is invalid for time series.
   - Experiments are partitioned chronologically:
     - **Train Split (60%):** Earliest 15 experiments.
     - **Validation Split (20%):** Subsequent 5 experiments.
     - **Test Split (20%):** Final 5 holdout experiments.
   - Zero overlap of `experiment_id` across splits.

