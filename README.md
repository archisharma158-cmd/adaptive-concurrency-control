# Predictive Network- and Contention-Aware Concurrency Control Switching in Distributed Databases

An academic research project exploring predictive and adaptive concurrency control in distributed databases under changing workloads and network conditions.

## Research Overview

Distributed databases handle multiple transactions simultaneously. Changes in transaction workloads, contention and network conditions can affect database performance.

This research aims to investigate whether predicting these changes and dynamically selecting suitable concurrency control protocols can improve transaction performance while minimising protocol-switching overhead.

## Research Objectives

- Study existing concurrency control techniques such as OCC, 2PL and MVCC.
- Analyse the impact of changing workloads and network conditions on database performance.
- Develop an ML model to predict upcoming transaction contention and network degradation.
- Design an adaptive controller for concurrency control protocol selection.
- Evaluate the proposed approach against static and reactive approaches.

## Proposed Methodology

1. **Literature Review:** Study existing research and identify potential research gaps.
2. **Data Collection:** Generate database workloads and collect transaction and network performance metrics.
3. **Data Processing:** Clean, analyse and visualise the collected experimental data.
4. **ML Development:** Train and evaluate prediction models.
5. **Adaptive Control:** Develop a decision mechanism that considers predicted conditions and switching costs.
6. **Evaluation:** Compare performance under different workloads and network conditions.

## Technology Stack

| Component | Tools |
|---|---|
| Programming | Python |
| Development | VS Code, Jupyter Notebook |
| Workload Generation | YCSB |
| Data Processing | Pandas, NumPy |
| Machine Learning | Scikit-learn, XGBoost |
| Visualisation | Matplotlib, Seaborn |
| Benchmarking | CCBench / suitable distributed database |
| Network Simulation | Linux tc netem |
| Version Control | Git, GitHub |

## Performance Metrics

- Transaction throughput (TPS)
- Average and P95/P99 latency
- Transaction conflict rate
- Transaction abort rate
- Network RTT and jitter
- Protocol-switching overhead
- Protocol switching frequency
- Recovery time after workload or network changes

## Repository Structure

```text
adaptive-concurrency-control/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_data_visualization.ipynb
│   └── 04_model_training.ipynb
│
├── scripts/
│   ├── collect_metrics.py
│   └── preprocess_data.py
│
├── models/
│
├── experiments/
│
├── results/
│
├── src/
│   ├── prediction/
│   └── controller/
│
├── requirements.txt
└── README.md
```

## Current Research Status

- [x] Research direction selected
- [ ] Literature review and gap validation
- [ ] Experimental environment setup
- [ ] Dataset generation
- [ ] Data cleaning and visualisation
- [ ] ML model development
- [ ] Adaptive controller implementation
- [ ] Performance evaluation
- [ ] Research paper preparation

## Research Focus

The central research question is:

**Can predicting network and workload changes together, while accounting for protocol-switching costs, improve the performance and stability of distributed databases compared with existing approaches?**

## Note

This repository is a work in progress for academic research. The proposed methodology and research contributions will be refined based on literature findings and experimental results.
