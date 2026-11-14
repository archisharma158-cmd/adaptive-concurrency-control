"""
src/models/train.py
Model training module for contention and network prediction.

Trains and compares:
  1. Persistence baseline (predict last known value).
  2. Random Forest Regressor.
  3. XGBoost Regressor.

Each model is trained separately for:
  - Contention prediction (target: future conflict_rate).
  - Network prediction (target: future network_rtt_ms).

Uses chronological, experiment-aware splits to prevent data leakage.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
import joblib
import json
import yaml
import warnings

from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    warnings.warn("XGBoost not available. Skipping XGBoost models.")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.data.preprocessing import (
    get_feature_columns,
    chronological_experiment_split,
)


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class PersistenceBaseline:
    """Baseline model: predicts the last known value of the target.

    For time series, this means predicting that the next value equals
    the current value. This is a surprisingly strong baseline.
    """

    def __init__(self, target_col: str):
        self.target_col = target_col
        self.source_col = target_col  # current value column

    def fit(self, X: pd.DataFrame, y: pd.Series):
        """No fitting needed for persistence baseline."""
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict current value as next value."""
        if self.source_col in X.columns:
            return X[self.source_col].values.copy()
        # Fallback: use the first lag feature
        lag_col = f"{self.source_col}_lag_1"
        if lag_col in X.columns:
            return X[lag_col].values.copy()
        # Last resort: return zeros
        return np.zeros(len(X))


def build_rf_pipeline(config: dict) -> Pipeline:
    """Build a Random Forest regression pipeline."""
    rf_cfg = config["training"]["models"]["random_forest"]
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", RandomForestRegressor(
            n_estimators=rf_cfg.get("n_estimators", 200),
            max_depth=rf_cfg.get("max_depth", 15),
            min_samples_split=rf_cfg.get("min_samples_split", 5),
            min_samples_leaf=rf_cfg.get("min_samples_leaf", 2),
            n_jobs=rf_cfg.get("n_jobs", -1),
            random_state=config["training"]["random_seed"],
        )),
    ])


def build_xgb_pipeline(config: dict) -> Pipeline:
    """Build an XGBoost regression pipeline."""
    if not HAS_XGBOOST:
        raise ImportError("XGBoost is not installed.")
    xgb_cfg = config["training"]["models"]["xgboost"]
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", xgb.XGBRegressor(
            n_estimators=xgb_cfg.get("n_estimators", 200),
            max_depth=xgb_cfg.get("max_depth", 8),
            learning_rate=xgb_cfg.get("learning_rate", 0.1),
            subsample=xgb_cfg.get("subsample", 0.8),
            colsample_bytree=xgb_cfg.get("colsample_bytree", 0.8),
            n_jobs=xgb_cfg.get("n_jobs", -1),
            random_state=config["training"]["random_seed"],
            verbosity=0,
        )),
    ])


def prepare_training_data(
    df: pd.DataFrame,
    target_col: str,
    feature_cols: Optional[list[str]] = None,
) -> tuple:
    """Prepare X and y arrays, dropping rows with NaN targets.

    Parameters
    ----------
    df : pd.DataFrame
        Processed dataset with features and targets.
    target_col : str
        The target column name (e.g. 'target_conflict_rate').
    feature_cols : list[str], optional
        Feature columns. If None, auto-detected.

    Returns
    -------
    (X, y, feature_cols) where X is a DataFrame, y is a Series.
    """
    if feature_cols is None:
        feature_cols = get_feature_columns(df)

    # Only keep rows with valid targets
    valid_mask = df[target_col].notna()
    df_valid = df.loc[valid_mask].copy()

    X = df_valid[feature_cols]
    y = df_valid[target_col]

    return X, y, feature_cols


def train_all_models(
    df: pd.DataFrame,
    target_name: str,
    target_col: str,
    config: dict,
    save_dir: str = "models/saved",
) -> dict:
    """Train all models for a single prediction target.

    Parameters
    ----------
    df : pd.DataFrame
        Full processed dataset.
    target_name : str
        Human-readable name (e.g. 'contention', 'network').
    target_col : str
        Column name (e.g. 'target_conflict_rate').
    config : dict
        Project configuration.
    save_dir : str
        Directory to save trained models.

    Returns
    -------
    dict with model names as keys and dicts of {model, feature_cols,
    train_metrics, val_metrics} as values.
    """
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # Get feature columns
    feature_cols = get_feature_columns(df)
    print(f"\n{'='*60}")
    print(f"TRAINING MODELS FOR: {target_name.upper()}")
    print(f"Target column: {target_col}")
    print(f"Features: {len(feature_cols)} columns")
    print(f"{'='*60}")

    # Split data
    pred_cfg = config.get("prediction", {})
    train_df, val_df, test_df = chronological_experiment_split(
        df,
        train_ratio=pred_cfg.get("train_ratio", 0.6),
        val_ratio=pred_cfg.get("val_ratio", 0.2),
        test_ratio=pred_cfg.get("test_ratio", 0.2),
    )

    # Prepare data
    X_train, y_train, _ = prepare_training_data(train_df, target_col, feature_cols)
    X_val, y_val, _ = prepare_training_data(val_df, target_col, feature_cols)

    print(f"  Training samples: {len(X_train)}")
    print(f"  Validation samples: {len(X_val)}")

    results = {}

    # --- 1. Persistence Baseline ---
    print(f"\n[1] Training Persistence Baseline...")
    source_col = target_col.replace("target_", "")
    baseline = PersistenceBaseline(source_col)
    baseline.fit(X_train, y_train)
    results["persistence_baseline"] = {
        "model": baseline,
        "feature_cols": feature_cols,
    }
    print(f"  Persistence baseline ready (predicts current {source_col})")

    # --- 2. Random Forest ---
    print(f"\n[2] Training Random Forest...")
    rf_pipeline = build_rf_pipeline(config)
    rf_pipeline.fit(X_train, y_train)
    results["random_forest"] = {
        "model": rf_pipeline,
        "feature_cols": feature_cols,
    }
    # Save
    rf_path = save_path / f"rf_{target_name}.joblib"
    joblib.dump(rf_pipeline, rf_path)
    print(f"  Saved to {rf_path}")

    # Feature importance
    rf_model = rf_pipeline.named_steps["model"]
    importances = pd.Series(
        rf_model.feature_importances_, index=feature_cols
    ).sort_values(ascending=False)
    print(f"  Top 5 features: {dict(importances.head(5).round(4))}")

    # --- 3. XGBoost ---
    if HAS_XGBOOST:
        print(f"\n[3] Training XGBoost...")
        xgb_pipeline = build_xgb_pipeline(config)
        xgb_pipeline.fit(X_train, y_train)
        results["xgboost"] = {
            "model": xgb_pipeline,
            "feature_cols": feature_cols,
        }
        xgb_path = save_path / f"xgb_{target_name}.joblib"
        joblib.dump(xgb_pipeline, xgb_path)
        print(f"  Saved to {xgb_path}")

        xgb_model = xgb_pipeline.named_steps["model"]
        xgb_importances = pd.Series(
            xgb_model.feature_importances_, index=feature_cols
        ).sort_values(ascending=False)
        print(f"  Top 5 features: {dict(xgb_importances.head(5).round(4))}")
    else:
        print(f"\n[3] Skipping XGBoost (not installed)")

    # Save feature list and metadata
    meta = {
        "target_name": target_name,
        "target_column": target_col,
        "feature_columns": feature_cols,
        "n_features": len(feature_cols),
        "n_train": len(X_train),
        "n_val": len(X_val),
        "models_trained": list(results.keys()),
    }
    meta_path = save_path / f"training_meta_{target_name}.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n  Training metadata saved to {meta_path}")

    return results


def train_pipeline(
    processed_data_path: str,
    config_path: str = "config.yaml",
) -> dict:
    """Run the full training pipeline for both prediction targets.

    Parameters
    ----------
    processed_data_path : str
        Path to the processed CSV.
    config_path : str

    Returns
    -------
    dict mapping target names to their model results.
    """
    config = load_config(config_path)
    pred_cfg = config.get("prediction", {})

    df = pd.read_csv(processed_data_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    all_results = {}

    # Train contention prediction models
    contention_target_col = f"target_{pred_cfg.get('contention_target', 'conflict_rate')}"
    if contention_target_col in df.columns:
        all_results["contention"] = train_all_models(
            df, "contention", contention_target_col, config
        )

    # Train network prediction models
    network_target_col = f"target_{pred_cfg.get('network_target', 'network_rtt_ms')}"
    if network_target_col in df.columns:
        all_results["network"] = train_all_models(
            df, "network", network_target_col, config
        )

    return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train ML models")
    parser.add_argument("--data", type=str,
                        default="data/processed/processed_data.csv",
                        help="Path to processed data CSV")
    parser.add_argument("--config", type=str, default="config.yaml")
    args = parser.parse_args()

    train_pipeline(args.data, args.config)

