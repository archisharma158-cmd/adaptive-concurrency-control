# Machine Learning Model Evaluation Report

## 1. Executive Summary
This report summarizes the experimental training and holdout evaluation of machine learning models for predicting:
1. Future transaction contention (`target_conflict_rate`)
2. Future network degradation (`target_network_rtt_ms`)

All evaluations were executed on a strict chronological test split representing the final 20% of experimental sessions (5 distinct holdout experiments, 595 evaluation samples), avoiding any intra-experiment data leakage.

---

## 2. Quantitative Model Comparison

| Target Dimension | Model Candidate | MAE | RMSE | $R^2$ Score | MAPE (%) | Test Samples |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Contention** (`conflict_rate`) | Persistence Baseline | 0.012359 | 0.020063 | **0.978787** | 8.75% | 595 |
| **Contention** (`conflict_rate`) | Random Forest Regressor | 0.013390 | 0.025054 | 0.966919 | 9.21% | 595 |
| **Contention** (`conflict_rate`) | XGBoost Regressor | 0.013462 | 0.023804 | 0.970138 | 9.18% | 595 |
| **Network** (`network_rtt_ms`) | Persistence Baseline | 4.092924 | 6.559248 | **0.984598** | 8.28% | 595 |
| **Network** (`network_rtt_ms`) | Random Forest Regressor | 4.791646 | 8.933640 | 0.971430 | 9.89% | 595 |
| **Network** (`network_rtt_ms`) | XGBoost Regressor | 4.736314 | 8.492957 | 0.974179 | 9.86% | 595 |

---

## 3. Analysis & Key Insights

1. **Persistence Baseline Performance:**
   - In smoothly varying time series (AR-1 processes), the persistence baseline ($\hat{y}_{t+1} = y_t$) is an extraordinarily competitive benchmark, capturing $97.8\%$ to $98.4\%$ of variance.
   - Reporting persistence baselines is an academic best practice; failure to report persistence often yields illusory claims of ML superiority.
2. **Feature Importance Insights:**
   - For Random Forest contention prediction, the rolling mean window features (`conflict_rate_rmean_10` with 31.5% importance and `conflict_rate` with 16.6%) dominated decision splits.
   - For XGBoost network prediction, `network_rtt_ms_rmean_3` provided 82.8% of split gain, showing that short-window smoothing filters out transient network jitter.
3. **Artifacts Generated:**
   - Scatter plots: `results/figures/actual_vs_predicted_contention.png`, `results/figures/actual_vs_predicted_network.png`
   - Time-series tracking: `results/figures/prediction_timeseries_contention.png`, `results/figures/prediction_timeseries_network.png`
   - Residual error plots: `results/figures/residuals_contention.png`, `results/figures/residuals_network.png`

