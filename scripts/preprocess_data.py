"""
scripts/preprocess_data.py
Script to run the preprocessing pipeline from the command line.

Usage:
    python scripts/preprocess_data.py
    python scripts/preprocess_data.py --input data/sample/synthetic_experiment_data.csv
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocessing import run_preprocessing_pipeline
from src.data.validation import validate_dataset, save_quality_report
import pandas as pd


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Preprocess experimental data")
    parser.add_argument("--input", type=str,
                        default="data/sample/synthetic_experiment_data.csv",
                        help="Path to raw data CSV")
    parser.add_argument("--output", type=str,
                        default="data/processed/processed_data.csv",
                        help="Path for processed output")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--report", type=str,
                        default="reports/data_quality_report.md",
                        help="Path for data quality report")
    args = parser.parse_args()

    # Validate first
    print("Running data validation...")
    raw_df = pd.read_csv(args.input)
    if "timestamp" in raw_df.columns:
        raw_df["timestamp"] = pd.to_datetime(raw_df["timestamp"])
    report = validate_dataset(raw_df)
    save_quality_report(report, args.report)

    # Then preprocess
    print("\nRunning preprocessing pipeline...")
    df = run_preprocessing_pipeline(
        args.input,
        config_path=args.config,
        output_path=args.output,
    )

    print(f"\nDone. Processed data: {args.output}")
    print(f"Quality report: {args.report}")


if __name__ == "__main__":
    main()

