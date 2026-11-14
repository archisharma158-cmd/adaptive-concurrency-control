"""
scripts/build_notebooks.py
Generates reproducible Jupyter Notebooks (.ipynb) corresponding to each phase
of the experimental research pipeline using nbformat.
"""

import nbformat as nbf
from pathlib import Path

NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent / "notebooks"
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)


def create_nb(cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.13"
        }
    }
    return nb


def build_nb1():
    cells = [
        nbf.v4.new_markdown_cell("""# 01 - Data Collection and Benchmark Simulation
## Research: Predictive Network- and Contention-Aware Concurrency Control Switching

This notebook covers:
1. Overview of data requirements across distributed transaction metrics and network metrics.
2. Synthetic workload generation simulating YCSB + CCBench across different contention and network degradation scenarios.
3. Architecture of benchmark adapter interfaces for real distributed database deployments.
"""),
        nbf.v4.new_code_cell("""import sys
from pathlib import Path
import pandas as pd
import yaml

# Add project root to sys.path
PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_workloads import load_config, generate_full_dataset
"""),
        nbf.v4.new_code_cell("""# Load configuration
config = load_config(PROJECT_ROOT / "config.yaml")
print(f"Project: {config['project']['name']}")
print(f"Supported Protocols: {config['synthetic']['protocols']}")
print(f"Sampling interval: {config['synthetic']['sampling_interval_sec']} seconds")
"""),
        nbf.v4.new_code_cell("""# Generate synthetic dataset for pipeline testing
# Note: Real benchmarks require live DB (CockroachDB/TiDB) and tc netem
raw_df = generate_full_dataset(config)
raw_df.head()
"""),
        nbf.v4.new_code_cell("""# Inspect experimental scenario distribution
scenario_summary = raw_df.groupby(['workload_type', 'active_protocol']).agg(
    observations=('timestamp', 'count'),
    mean_conflict=('conflict_rate', 'mean'),
    mean_rtt_ms=('network_rtt_ms', 'mean'),
    mean_throughput_tps=('throughput_tps', 'mean')
)
scenario_summary
""")
    ]
    path = NOTEBOOKS_DIR / "01_data_collection.ipynb"
    nbf.write(create_nb(cells), path)
    print(f"Created {path}")


def build_nb2():
    cells = [
        nbf.v4.new_markdown_cell("""# 02 - Data Cleaning and Preprocessing
## Research: Predictive Network- and Contention-Aware Concurrency Control Switching

This notebook demonstrates:
1. Automated schema validation and boundary checks.
2. Exact and key-based duplicate detection.
3. Conservative missing value imputation (forward fill within time series, median fallback).
4. Feature engineering: lag features and rolling window statistics.
5. Prediction target formulation (strictly shifted future values with zero leakage).
"""),
        nbf.v4.new_code_cell("""import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.validation import validate_dataset, save_quality_report
from src.data.preprocessing import run_preprocessing_pipeline, load_raw_data
"""),
        nbf.v4.new_code_cell("""# Load raw data
raw_path = PROJECT_ROOT / "data" / "sample" / "synthetic_experiment_data.csv"
raw_df = load_raw_data(str(raw_path))
print(f"Raw shape: {raw_df.shape}")

# Execute validation suite
report = validate_dataset(raw_df)
print("Data Quality Summary:")
for k, v in report.summary.items():
    print(f"  {k}: {v}")
"""),
        nbf.v4.new_code_cell("""# Execute complete preprocessing pipeline
processed_df = run_preprocessing_pipeline(
    raw_path=str(raw_path),
    config_path=str(PROJECT_ROOT / "config.yaml"),
    output_path=str(PROJECT_ROOT / "data" / "processed" / "processed_data.csv")
)
processed_df.info()
""")
    ]
    path = NOTEBOOKS_DIR / "02_data_cleaning.ipynb"
    nbf.write(create_nb(cells), path)
    print(f"Created {path}")


def build_nb3():
    cells = [
        nbf.v4.new_markdown_cell("""# 03 - Exploratory Data Analysis & Visualization
## Research: Predictive Network- and Contention-Aware Concurrency Control Switching

Visualizing key distributions, temporal variations, correlation matrices,
and multi-variate interactions between transaction contention, network degradation, and throughput.
"""),
        nbf.v4.new_code_cell("""import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

df = pd.read_csv(PROJECT_ROOT / "data" / "processed" / "processed_data.csv")
df.head()
"""),
        nbf.v4.new_code_cell("""# Correlation analysis
metric_cols = [
    "conflict_rate", "abort_rate", "network_rtt_ms", "network_jitter_ms",
    "throughput_tps", "average_latency_ms", "concurrent_transactions", "queue_length"
]
plt.figure(figsize=(9, 7))
sns.heatmap(df[metric_cols].corr(), annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
plt.title("Correlation Heatmap")
plt.show()
"""),
        nbf.v4.new_code_cell("""# Throughput across protocols and workloads
plt.figure(figsize=(9, 5))
sns.boxplot(data=df, x="workload_type", y="throughput_tps", hue="active_protocol")
plt.title("Throughput vs Workload Type & Protocol")
plt.show()
""")
    ]
    path = NOTEBOOKS_DIR / "03_data_visualization.ipynb"
    nbf.write(create_nb(cells), path)
    print(f"Created {path}")


def build_nb4():
    cells = [
        nbf.v4.new_markdown_cell("""# 04 - Machine Learning Model Training
## Research: Predictive Network- and Contention-Aware Concurrency Control Switching

Training models to predict:
1. Future transaction contention (`target_conflict_rate`)
2. Future network degradation (`target_network_rtt_ms`)

Comparing:
- Persistence Baseline
- Random Forest Regressor
- XGBoost Regressor
"""),
        nbf.v4.new_code_cell("""import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.train import train_pipeline, load_config

config = load_config(PROJECT_ROOT / "config.yaml")
data_path = PROJECT_ROOT / "data" / "processed" / "processed_data.csv"

# Train models
results = train_pipeline(str(data_path), str(PROJECT_ROOT / "config.yaml"))
"""),
        nbf.v4.new_code_cell("""# Inspect saved models
saved_models = list((PROJECT_ROOT / "models" / "saved").glob("*.joblib"))
print("Saved Models:")
for m in saved_models:
    print(f"  - {m.name}")
""")
    ]
    path = NOTEBOOKS_DIR / "04_model_training.ipynb"
    nbf.write(create_nb(cells), path)
    print(f"Created {path}")


def build_nb5():
    cells = [
        nbf.v4.new_markdown_cell("""# 05 - Model Evaluation & Baseline Comparison
## Research: Predictive Network- and Contention-Aware Concurrency Control Switching

1. Rigorous time-series evaluation (chronological hold-out test set).
2. Evaluation metrics: MAE, RMSE, R², MAPE.
3. System benchmark comparison:
   - Static Protocol Allocation (OCC, 2PL, MVCC)
   - Reactive Threshold Controller
   - Predictive Controller with Switching-Cost Optimization
"""),
        nbf.v4.new_code_cell("""import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(PROJECT_ROOT))

# Load model evaluation comparison
comp_df = pd.read_csv(PROJECT_ROOT / "results" / "model_comparison.csv")
comp_df
"""),
        nbf.v4.new_code_cell("""# Load controller baseline benchmark comparison
bench_df = pd.read_csv(PROJECT_ROOT / "results" / "benchmark_comparison.csv")
bench_df
""")
    ]
    path = NOTEBOOKS_DIR / "05_model_evaluation.ipynb"
    nbf.write(create_nb(cells), path)
    print(f"Created {path}")


def main():
    build_nb1()
    build_nb2()
    build_nb3()
    build_nb4()
    build_nb5()
    print("All 5 Jupyter notebooks generated successfully.")


if __name__ == "__main__":
    main()

