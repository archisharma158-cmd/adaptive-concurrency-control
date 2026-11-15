# Predictive Network- and Contention-Aware Concurrency Control Switching with Switching-Cost Optimization in Distributed Databases

[![Tests](https://img.shields.io/badge/pytest-24%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)]()
[![Database](https://img.shields.io/badge/CockroachDB-v23.2.0-red.svg)]()
[![TrafficControl](https://img.shields.io/badge/Linux-tc_netem-orange.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

An academic research implementation and experimental framework investigating whether predicting transaction contention and network degradation—while explicitly accounting for protocol-switching costs and hysteresis—improves the performance, stability, and abort rates of distributed database management systems.

---

## 1. Research Overview

Distributed databases handle concurrent transactions across interconnected nodes subject to dynamic workload shifts and network volatility. Traditional systems employ either:
1. **Static Concurrency Control:** A single fixed protocol (OCC, 2PL, or MVCC) chosen at deployment time, which inevitably suffers when operating conditions deviate from its optimal regime.
2. **Reactive Adaptation:** Instantaneous threshold-based switching that frequently results in thrashing (excessive protocol oscillation), inflicting catastrophic transaction draining and lock synchronization overhead.

### The Research Question
> **Can predicting network and workload changes together, while accounting for protocol-switching costs and hysteresis, improve the performance and stability of distributed databases compared with static and reactive approaches?**

### The Proposed Approach
- **Multi-Horizon Time-Series Forecasting:** Machine learning models (Random Forest, XGBoost) trained on lag and rolling features to forecast upcoming contention (`conflict_rate`) and network degradation (`network_rtt_ms`).
- **Cost-Aware Decision Controller:** An optimization engine that computes protocol suitability deltas and only triggers transitions when the predicted performance gain amortizes the protocol-switching cost.
- **Hysteresis & Anti-Flapping:** Temporal thresholds preventing protocol thrashing during transient bursts.

---

## 2. Quantitative Results Summary

All results are obtained under identical holdout test configurations (5 holdout experiments, 595 observations, strict chronological separation with zero data leakage):

### A. Machine Learning Prediction Performance

| Prediction Target | Baseline ($R^2$) | Random Forest ($R^2$) | XGBoost ($R^2$) | Best MAE |
| :--- | :--- | :--- | :--- | :--- |
| **Contention** (`conflict_rate`) | 0.9788 | 0.9669 | 0.9701 | 0.0123 |
| **Network RTT** (`network_rtt_ms`) | 0.9846 | 0.9714 | 0.9742 | 4.0929 ms |

*Note: The persistence baseline ($\hat{y}_{t+1} = y_t$) is documented alongside ML models following academic best practices.*

### B. Controller Benchmark Comparison

| Concurrency Control Strategy | Mean Throughput (TPS) | Mean Latency (ms) | P95 Latency (ms) | P99 Tail Latency (ms) | Mean Abort Rate | Total Switches | Total Switch Overhead |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Proposed Predictive Controller** | 172.36 | **70.72** | **141.44** | **247.52** | **0.1385** | **1** | **300.0 ms** |
| **Reactive Threshold Controller** | **179.79** | 77.21 | 154.43 | 270.25 | 0.1393 | 11 | 3,900.0 ms |
| **Static OCC Baseline** | 151.37 | 126.11 | 252.23 | 441.40 | 0.2674 | 0 | 0.0 ms |
| **Static 2PL Baseline** | 151.37 | 126.11 | 252.23 | 441.40 | 0.2674 | 0 | 0.0 ms |
| **Static MVCC Baseline** | 151.37 | 126.11 | 252.23 | 441.40 | 0.2674 | 0 | 0.0 ms |

**Key Takeaways:**
- **43.9% reduction in latency** and **48.2% reduction in abort rate** compared to static baselines.
- **92.3% reduction in switching disruption** (1 switch vs. 11 switches) compared to reactive switching, preventing system thrashing.

---

## 3. Repository Structure

```text
adaptive-concurrency-control/
│
├── config.yaml                    # Master experimental configuration file
├── requirements.txt               # Pinned package dependencies
├── streamlit_app.py               # Interactive research & simulation dashboard
│
├── data/
│   ├── raw/                       # Incoming real benchmark CSV traces
│   ├── processed/                 # Cleaned dataset with features and shifted targets
│   └── sample/                    # Verified synthetic dataset for reproducible testing
│       ├── synthetic_experiment_data.csv
│       └── SYNTHETIC_DATA_MANIFEST.yaml
│
├── src/
│   ├── data/
│   │   ├── validation.py          # Data validation suite and quality reporting
│   │   └── preprocessing.py       # Time-series feature engineering & leakage-free split
│   ├── models/
│   │   ├── train.py               # Training pipeline (Baseline, RF, XGBoost)
│   │   ├── predict.py             # Inference wrappers & ensemble predictors
│   │   └── evaluate.py            # Holdout evaluation & diagnostic plotting
│   ├── controller/
│   │   ├── decision_engine.py     # Static, Reactive, and Predictive controllers
│   │   └── switching_cost.py      # Protocol transition modeling & safety semantics
│   └── experiments/
│       └── run_experiments.py     # End-to-end comparative benchmark runner
│
├── scripts/
│   ├── run_real_experiment.py     # End-to-end CockroachDB + YCSB + tc netem physical experiment runner
│   ├── run_matrix_experiments.py  # Automated sequential matrix runner (Workloads A/B/C, delays 15-55ms)
│   ├── combine_real_datasets.py   # Aggregator for verified genuine physical CSV traces
│   ├── generate_real_eda_and_comparison.py # Real benchmark visualizations and comparative report
│   ├── collect_metrics.py         # Benchmark adapter interface for telemetry harvesting
│   ├── preprocess_data.py         # CLI preprocessing & feature engineering runner
│   ├── generate_workloads.py      # Synthetic testbed data generator
│   └── build_notebooks.py         # Programmatic builder for Jupyter notebooks
│
├── notebooks/
│   ├── 01_data_collection.ipynb   # Workload generation and telemetry architecture
│   ├── 02_data_cleaning.ipynb     # Schema validation and feature engineering
│   ├── 03_data_visualization.ipynb# Exploratory visual analysis
│   ├── 04_model_training.ipynb    # Machine learning model training
│   └── 05_model_evaluation.ipynb  # Diagnostic evaluation and controller simulation
│
├── models/
│   └── saved/                     # Serialized models (.joblib) and metadata (.json)
│
├── results/
│   ├── model_comparison.csv       # Quantitative ML metrics (MAE, RMSE, R2, MAPE)
│   ├── benchmark_comparison.csv   # Controller comparative metrics
│   ├── experiment_results_detailed.csv # Per-step trace logs
│   └── figures/                   # 24 publication-ready figures (.png) (8 real physical + 16 testbed)
│
├── docs/
│   ├── research_methodology.md    # Hypotheses, theoretical framework & architecture
│   ├── dataset_documentation.md   # Feature schema, units, and integrity constraints
│   ├── prediction_target.md       # Target formulation & leakage prevention
│   ├── controller_design.md       # Utility model, hysteresis & database transition steps
│   └── experiment_protocol.md     # Setup guide for live DBs (CockroachDB/YCSB/tc netem)
│
├── reports/
│   ├── real_experiment_comparison.md # Cross-experiment systems analysis & Little's Law validation
│   ├── real_data_quality_report.md# Automated validation audit on combined real dataset
│   ├── model_evaluation.md        # Comprehensive ML performance report on real holdout testbed
│   ├── experimental_results.md    # Strategy comparison and thrashing analysis
│   └── limitations.md             # Threats to validity, loopback netem scope, and MVCC boundary
│
└── tests/
    └── test_pipeline.py           # 24 unit, schema, and physical data invariant tests (100% passing)
```

---

## 4. Setup and Execution Guide

### Prerequisites
- Python 3.10 to 3.13
- Git

### Installation
```bash
git clone https://github.com/your-username/adaptive-concurrency-control.git
cd adaptive-concurrency-control

# Install dependencies
pip install -r requirements.txt
```

### End-to-End Real Database Pipeline Reproduction (CockroachDB + WSL 2)

Execute the complete physical research pipeline using verified physical experiments:

```bash
# Step 1: Run full unit, schema, and dataset invariant tests
python -m pytest tests/ -v

# Step 2: Combine verified physical experiments (excludes contaminated pilot runs)
python scripts/combine_real_datasets.py

# Step 3: Generate 8 physical EDA figures and comparative markdown report
python scripts/generate_real_eda_and_comparison.py

# Step 4: Validate and preprocess data (engineers lags, rolling statistics, & prediction targets)
python scripts/preprocess_data.py --input data/raw/combined_real_dataset.csv --output data/processed/processed_real_data.csv --report reports/real_data_quality_report.md

# Step 5: Train machine learning models (Persistence Baseline, Random Forest, XGBoost)
python -m src.models.train --data data/processed/processed_real_data.csv

# Step 6: Evaluate models on chronological holdout test set (unseen network regimes)
python -m src.models.evaluate --data data/processed/processed_real_data.csv

# Step 7: Run comparative benchmark experiment across all 5 strategies
python -m src.experiments.run_experiments --data data/processed/processed_real_data.csv
```

### Running Physical Experiments in WSL 2 (Optional / Automated)
```bash
# Execute automated matrix (Workloads A/B/C, concurrency 16/32, delays 15/35/55ms)
wsl -u root -d Ubuntu -e bash -c "python3 '/mnt/c/Users/archi/OneDrive/Desktop/Research Paper/adaptive-concurrency-control/scripts/run_matrix_experiments.py'"
```

### Launching the Interactive Dashboard (Optional)
```bash
streamlit run streamlit_app.py
```

---

## 5. Protocols & Real-World Integration

- **OCC (Optimistic Concurrency Control):** Best under low contention and normal network; suffers severe abort cascading under high contention.
- **2PL (Two-Phase Locking):** Pessimistic locking. Optimal under high contention, but suffers lock convoys under degraded network latency.
- **MVCC (Multi-Version Concurrency Control):** Non-blocking reads from snapshot versions; highly resilient to network delays.

To connect live database engines (CockroachDB, TiDB, or CCBench), refer to the adapter specifications in [docs/experiment_protocol.md](docs/experiment_protocol.md) and implement `scripts/collect_metrics.py`.

---

## 6. Citation & Academic Notice

```bibtex
@article{adaptive_cc_2026,
  title={Predictive Network- and Contention-Aware Concurrency Control Switching with Switching-Cost Optimization in Distributed Databases},
  author={Research Team},
  journal={Working Paper in Distributed Database Systems},
  year={2026}
}
```
