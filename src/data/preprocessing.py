"""
src/data/preprocessing.py
Data cleaning and feature engineering for the adaptive concurrency control
research.

Responsibilities:
  - Clean raw experimental data (handle missing, sort, deduplicate).
  - Engineer lag features and rolling statistics for time-series prediction.
  - Create prediction targets (shifted future values).
  - Perform chronological, experiment-aware train/val/test splitting.

IMPORTANT: This module never fabricates data. It transforms existing
observations and clearly marks derived columns.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    """Load the project configuration file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_raw_data(path: str) -> pd.DataFrame:
    """Load raw CSV data and parse timestamps.

    Parameters
    ----------
    path : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
    """
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def remove_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove exact duplicate rows, keeping the first occurrence."""
    n_before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    n_removed = n_before - len(df)
    if n_removed > 0:
        print(f"  Removed {n_removed} exact duplicate rows.")
    return df


def sort_by_experiment_and_time(df: pd.DataFrame) -> pd.DataFrame:
    """Sort the dataset by experiment_id and timestamp."""
    sort_cols = []
    if "experiment_id" in df.columns:
        sort_cols.append("experiment_id")
    if "timestamp" in df.columns:
        sort_cols.append("timestamp")
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Handle missing values conservatively.

    Strategy:
    - Numeric columns: forward-fill within each experiment, then fill
      remaining with column median.
    - Categorical columns: fill with 'unknown'.

    No rows are deleted — the researcher can filter later.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns

    if "experiment_id" in df.columns:
        # Forward-fill within experiments (time series)
        df[numeric_cols] = df.groupby("experiment_id")[numeric_cols].transform(
            lambda g: g.ffill()
        )

    # Fill remaining numeric NaNs with column median
    for col in numeric_cols:
        if df[col].isna().any():
            median_val = df[col].median()
            n_filled = df[col].isna().sum()
            df[col] = df[col].fillna(median_val)
            print(f"  Filled {n_filled} NaN in '{col}' with median={median_val:.4f}")

    # Fill categorical NaNs
    for col in categorical_cols:
        if df[col].isna().any():
            n_filled = df[col].isna().sum()
            df[col] = df[col].fillna("unknown")
            print(f"  Filled {n_filled} NaN in '{col}' with 'unknown'")

    return df


def add_lag_features(df: pd.DataFrame,
                     columns: list[str],
                     lags: list[int],
                     group_col: str = "experiment_id") -> pd.DataFrame:
    """Add lagged versions of specified columns.

    Creates columns named '{col}_lag_{k}' for each column and lag value.
    Lags are computed within each experiment to prevent data leakage.

    Parameters
    ----------
    df : pd.DataFrame
    columns : list[str]
        Columns to create lags for.
    lags : list[int]
        Lag steps (e.g. [1, 2, 3]).
    group_col : str
        Grouping column (usually 'experiment_id').

    Returns
    -------
    pd.DataFrame with new lag columns.
    """
    for col in columns:
        if col not in df.columns:
            continue
        for lag in lags:
            lag_col = f"{col}_lag_{lag}"
            if group_col in df.columns:
                df[lag_col] = df.groupby(group_col)[col].shift(lag)
            else:
                df[lag_col] = df[col].shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame,
                         columns: list[str],
                         windows: list[int],
                         group_col: str = "experiment_id") -> pd.DataFrame:
    """Add rolling mean and std for specified columns.

    Creates columns '{col}_rmean_{w}' and '{col}_rstd_{w}'.
    Rolling windows are computed within each experiment.

    Parameters
    ----------
    df : pd.DataFrame
    columns : list[str]
    windows : list[int]
        Window sizes.
    group_col : str

    Returns
    -------
    pd.DataFrame with new rolling columns.
    """
    for col in columns:
        if col not in df.columns:
            continue
        for w in windows:
            mean_col = f"{col}_rmean_{w}"
            std_col = f"{col}_rstd_{w}"
            if group_col in df.columns:
                grouped = df.groupby(group_col)[col]
                df[mean_col] = grouped.transform(
                    lambda s: s.rolling(window=w, min_periods=1).mean()
                )
                df[std_col] = grouped.transform(
                    lambda s: s.rolling(window=w, min_periods=1).std().fillna(0)
                )
            else:
                df[mean_col] = df[col].rolling(window=w, min_periods=1).mean()
                df[std_col] = df[col].rolling(window=w, min_periods=1).std().fillna(0)
    return df


def create_prediction_targets(df: pd.DataFrame,
                              target_cols: list[str],
                              horizon: int = 1,
                              group_col: str = "experiment_id") -> pd.DataFrame:
    """Create prediction targets by shifting future values backward.

    For each target column, creates 'target_{col}' which is the value
    `horizon` steps into the future. This is what the model will predict.

    IMPORTANT: The target is a FUTURE value. It must NEVER be used as an
    input feature — that would be data leakage.

    Parameters
    ----------
    df : pd.DataFrame
    target_cols : list[str]
        Columns whose future values become targets.
    horizon : int
        Number of steps ahead to predict.
    group_col : str
        Experiments are shifted independently.

    Returns
    -------
    pd.DataFrame with new target columns. Rows without a valid future
    value (end of each experiment) will have NaN targets.
    """
    for col in target_cols:
        if col not in df.columns:
            print(f"  WARNING: Target column '{col}' not found in data.")
            continue
        target_name = f"target_{col}"
        if group_col in df.columns:
            df[target_name] = df.groupby(group_col)[col].shift(-horizon)
        else:
            df[target_name] = df[col].shift(-horizon)
        n_valid = df[target_name].notna().sum()
        print(f"  Created target '{target_name}': {n_valid} valid values "
              f"(horizon={horizon} steps)")
    return df


def create_classification_targets(df: pd.DataFrame,
                                  contention_col: str = "target_conflict_rate",
                                  network_col: str = "target_network_rtt_ms",
                                  contention_threshold: float = 0.15,
                                  network_threshold: float = 20.0) -> pd.DataFrame:
    """Create binary classification targets from regression targets.

    Parameters
    ----------
    df : pd.DataFrame
    contention_col : str
        Regression target for contention.
    network_col : str
        Regression target for network.
    contention_threshold : float
        Values above this are 'high' contention (1), else 'low' (0).
    network_threshold : float
        Values above this are 'degraded' network (1), else 'normal' (0).
    """
    if contention_col in df.columns:
        df["target_contention_class"] = (
            df[contention_col] > contention_threshold
        ).astype("Int64")
        print(f"  Created 'target_contention_class' "
              f"(threshold={contention_threshold})")

    if network_col in df.columns:
        df["target_network_class"] = (
            df[network_col] > network_threshold
        ).astype("Int64")
        print(f"  Created 'target_network_class' "
              f"(threshold={network_threshold})")

    return df


def get_feature_columns(df: pd.DataFrame,
                        exclude_prefixes: tuple = ("target_",),
                        exclude_cols: tuple = ("timestamp", "experiment_id",
                                               "workload_type",
                                               "active_protocol")
                        ) -> list[str]:
    """Return the list of numeric feature columns for ML.

    Excludes target columns, identifiers, and non-numeric columns.
    """
    features = []
    for col in df.select_dtypes(include=[np.number]).columns:
        if any(col.startswith(p) for p in exclude_prefixes):
            continue
        if col in exclude_cols:
            continue
        features.append(col)
    return features


def chronological_experiment_split(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    group_col: str = "experiment_id",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data chronologically by experiment.

    Entire experiments are assigned to train, val, or test — no experiment
    spans multiple splits. Experiments are ordered by their earliest
    timestamp, then split by the specified ratios.

    This prevents data leakage between splits.

    Parameters
    ----------
    df : pd.DataFrame
    train_ratio, val_ratio, test_ratio : float
        Must sum to 1.0.
    group_col : str

    Returns
    -------
    (train_df, val_df, test_df)
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        "Split ratios must sum to 1.0"

    if group_col not in df.columns:
        # Fallback: simple chronological split on rows
        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]

    # Order experiments by their earliest timestamp
    if "timestamp" in df.columns:
        exp_order = (
            df.groupby(group_col)["timestamp"]
            .min()
            .sort_values()
            .index.tolist()
        )
    else:
        exp_order = sorted(df[group_col].unique())

    n_exp = len(exp_order)
    train_end = int(n_exp * train_ratio)
    val_end = int(n_exp * (train_ratio + val_ratio))

    train_exps = set(exp_order[:train_end])
    val_exps = set(exp_order[train_end:val_end])
    test_exps = set(exp_order[val_end:])

    train_df = df[df[group_col].isin(train_exps)].reset_index(drop=True)
    val_df = df[df[group_col].isin(val_exps)].reset_index(drop=True)
    test_df = df[df[group_col].isin(test_exps)].reset_index(drop=True)

    print(f"  Split: train={len(train_df)} rows ({len(train_exps)} exps), "
          f"val={len(val_df)} rows ({len(val_exps)} exps), "
          f"test={len(test_df)} rows ({len(test_exps)} exps)")

    return train_df, val_df, test_df


def run_preprocessing_pipeline(
    raw_path: str,
    config_path: str = "config.yaml",
    save_processed: bool = True,
    output_path: Optional[str] = None,
) -> pd.DataFrame:
    """Run the full preprocessing pipeline.

    Parameters
    ----------
    raw_path : str
        Path to raw CSV data.
    config_path : str
        Path to config.yaml.
    save_processed : bool
        Whether to save the processed dataset.
    output_path : str, optional
        Where to save. Defaults to data/processed/processed_data.csv.

    Returns
    -------
    pd.DataFrame
        Processed dataset with features and targets.
    """
    config = load_config(config_path)
    pred_cfg = config.get("prediction", {})

    print("=" * 60)
    print("PREPROCESSING PIPELINE")
    print("=" * 60)

    # 1. Load
    print("\n[1/7] Loading raw data...")
    df = load_raw_data(raw_path)
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

    # 2. Sort
    print("\n[2/7] Sorting by experiment and time...")
    df = sort_by_experiment_and_time(df)

    # 3. Deduplicate
    print("\n[3/7] Removing duplicates...")
    df = remove_exact_duplicates(df)

    # 4. Handle missing values
    print("\n[4/7] Handling missing values...")
    df = handle_missing_values(df)

    # 5. Feature engineering: lags and rolling stats
    print("\n[5/7] Engineering features...")
    feature_cols = ["conflict_rate", "abort_rate", "network_rtt_ms",
                    "network_jitter_ms", "throughput_tps", "average_latency_ms",
                    "transaction_rate", "queue_length"]
    lag_steps = pred_cfg.get("lag_features", [1, 2, 3, 5])
    rolling_windows = pred_cfg.get("rolling_windows", [3, 5, 10])

    df = add_lag_features(df, feature_cols, lag_steps)
    df = add_rolling_features(df, feature_cols, rolling_windows)
    print(f"  Total columns after feature engineering: {len(df.columns)}")

    # 6. Create prediction targets
    print("\n[6/7] Creating prediction targets...")
    contention_target = pred_cfg.get("contention_target", "conflict_rate")
    network_target = pred_cfg.get("network_target", "network_rtt_ms")
    horizon = pred_cfg.get("horizon_steps", 1)

    df = create_prediction_targets(
        df, [contention_target, network_target], horizon=horizon
    )

    # Classification targets
    df = create_classification_targets(
        df,
        contention_threshold=pred_cfg.get("contention_threshold", 0.15),
        network_threshold=pred_cfg.get("network_rtt_threshold", 20.0),
    )

    # 7. Save
    if save_processed:
        if output_path is None:
            output_path = str(
                Path(config["data"]["processed_dir"]) / "processed_data.csv"
            )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"\n[7/7] Saved processed data to {output_path}")
        print(f"  Final shape: {df.shape}")

    print("\n" + "=" * 60)
    print("PREPROCESSING COMPLETE")
    print("=" * 60)

    return df

