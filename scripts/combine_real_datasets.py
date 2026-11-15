"""
scripts/combine_real_datasets.py
Aggregates verified real-world experimental datasets into a single combined CSV.

Academic Integrity & Filtering Rules:
  - Excludes pilot/synthetic files (e.g. exp_test_pilot.csv).
  - Excludes exp_real_0002.csv and exp_real_0003.csv due to documented
    concurrent background collision during previous unisolated runs.
  - Retains all genuine, verified runs: exp_real_0001, exp_real_0004, exp_real_0005,
    exp_real_0006, exp_real_0007, exp_real_0008, exp_real_0009.
  - Generates data/raw/combined_real_dataset.csv and reports data quality.
"""

import sys
import glob
from pathlib import Path
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.validation import validate_dataset


def main():
    raw_dir = PROJECT_ROOT / "data" / "raw"
    csv_files = sorted(raw_dir.glob("exp_real_*.csv"))

    valid_dfs = []
    excluded = []

    for path in csv_files:
        meta_path = raw_dir / f"{path.stem}_metadata.yaml"
        exclude = False
        reason = "No reason specified"

        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as yf:
                meta = yaml.safe_load(yf)
                if meta and meta.get("excluded_from_clean_training", False):
                    exclude = True
                    reason = meta.get("exclusion_reason", "Flagged in metadata")

        if exclude:
            excluded.append((path.name, reason))
            print(f"[COMBINE] EXCLUDING {path.name}: {reason}")
        else:
            df = pd.read_csv(path)
            valid_dfs.append(df)
            print(f"[COMBINE] INCLUDED  {path.name}: {len(df)} rows, workload={df['workload_type'].iloc[0]}, concurrency={df['concurrent_transactions'].iloc[0]}")

    if not valid_dfs:
        print("[COMBINE] ERROR: No valid datasets found!")
        sys.exit(1)

    combined_df = pd.concat(valid_dfs, ignore_index=True)
    out_path = raw_dir / "combined_real_dataset.csv"
    combined_df.to_csv(out_path, index=False)
    print(f"\n[COMBINE] Successfully created {out_path}")
    print(f"          Total rows: {len(combined_df)}")
    print(f"          Experiments included: {combined_df['experiment_id'].nunique()} ({list(combined_df['experiment_id'].unique())})")
    print(f"          Experiments excluded: {len(excluded)} ({[e[0] for e in excluded]})")

    # Validate the combined dataset
    report = validate_dataset(combined_df)
    errors = [f for f in report.findings if f["severity"] == "ERROR"]
    warnings = [f for f in report.findings if f["severity"] == "WARNING"]
    print(f"[COMBINE] Validation complete: {len(errors)} errors, {len(warnings)} warnings.")
    if errors:
        print(f"[COMBINE] Validation errors: {errors}")
        sys.exit(1)


if __name__ == "__main__":
    main()

