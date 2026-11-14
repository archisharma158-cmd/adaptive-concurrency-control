"""
src/models/evaluate.py
Model evaluation module.

Evaluates trained models using:
  - MAE (Mean Absolute Error)
  - RMSE (Root Mean Squared Error)
  - R² (Coefficient of Determination)
  - Comparison against persistence baseline

Uses the chronological test split to prevent data leakage.
Generates comparison tables and prediction plots.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
import json
import yaml
import joblib

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.data.preprocessing import (
    get_feature_columns,
    chronological_experiment_split,
)
from src.models.train import PersistenceBaseline, prepare_training_data


def compute_regression_metrics(y_true: np.ndarray,
                               y_pred: np.ndarray) -> dict:
    """Compute standard regression evaluation metrics.

    Parameters
    ----------
    y_true : array-like
        Ground truth values.
    y_pred : array-like
        Predicted values.

    Returns
    -------
    dict with MAE, RMSE, R², and MAPE.
    """
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    # Mean Absolute Percentage Error (avoid division by zero)
    nonzero = np.abs(y_true) > 1e-8
    if nonzero.sum() > 0:
        mape = np.mean(np.abs((y_true[nonzero] - y_pred[nonzero])
                              / y_true[nonzero])) * 100
    else:
        mape = float("nan")

    return {
        "MAE": round(mae, 6),
        "RMSE": round(rmse, 6),
        "R2": round(r2, 6),
        "MAPE_%": round(mape, 2),
        "n_samples": len(y_true),
    }


def evaluate_models(
    df: pd.DataFrame,
    target_name: str,
    target_col: str,
    models: dict,
    config: dict,
    figure_dir: str = "results/figures",
) -> pd.DataFrame:
    """Evaluate all models for a target on the test split.

    Parameters
    ----------
    df : pd.DataFrame
        Full processed dataset.
    target_name : str
        e.g. 'contention', 'network'
    target_col : str
        e.g. 'target_conflict_rate'
    models : dict
        {model_name: {"model": ..., "feature_cols": [...]}}
    config : dict
    figure_dir : str

    Returns
    -------
    pd.DataFrame with one row per model and metric columns.
    """
    pred_cfg = config.get("prediction", {})

    # Get the test split
    _, _, test_df = chronological_experiment_split(
        df,
        train_ratio=pred_cfg.get("train_ratio", 0.6),
        val_ratio=pred_cfg.get("val_ratio", 0.2),
        test_ratio=pred_cfg.get("test_ratio", 0.2),
    )

    feature_cols = get_feature_columns(df)
    X_test, y_test, _ = prepare_training_data(test_df, target_col, feature_cols)

    if len(X_test) == 0:
        print(f"  WARNING: No test data available for {target_name}")
        return pd.DataFrame()

    print(f"\n{'='*60}")
    print(f"EVALUATING MODELS FOR: {target_name.upper()}")
    print(f"Test samples: {len(X_test)}")
    print(f"{'='*60}")

    results_rows = []
    predictions = {}

    for model_name, model_info in models.items():
        model = model_info["model"]
        y_pred = model.predict(X_test)
        metrics = compute_regression_metrics(y_test.values, y_pred)
        metrics["model"] = model_name
        metrics["target"] = target_name
        results_rows.append(metrics)
        predictions[model_name] = y_pred

        print(f"\n  {model_name}:")
        print(f"    MAE  = {metrics['MAE']:.6f}")
        print(f"    RMSE = {metrics['RMSE']:.6f}")
        print(f"    R²   = {metrics['R2']:.6f}")
        print(f"    MAPE = {metrics['MAPE_%']:.2f}%")

    results_df = pd.DataFrame(results_rows)

    # --- Generate prediction plots ---
    fig_path = Path(figure_dir)
    fig_path.mkdir(parents=True, exist_ok=True)

    # 1. Actual vs Predicted scatter for each model
    n_models = len(predictions)
    fig, axes = plt.subplots(1, n_models, figsize=(6 * n_models, 5))
    if n_models == 1:
        axes = [axes]

    for ax, (name, y_pred) in zip(axes, predictions.items()):
        ax.scatter(y_test, y_pred, alpha=0.3, s=10)
        lims = [
            min(y_test.min(), y_pred.min()),
            max(y_test.max(), y_pred.max()),
        ]
        ax.plot(lims, lims, "r--", linewidth=1, label="Perfect prediction")
        ax.set_xlabel("Actual")
        ax.set_ylabel("Predicted")
        ax.set_title(f"{name}\n(R²={r2_score(y_test, y_pred):.4f})")
        ax.legend()

    plt.suptitle(f"Actual vs Predicted — {target_name.title()} Prediction",
                 fontsize=14)
    plt.tight_layout()
    scatter_path = fig_path / f"actual_vs_predicted_{target_name}.png"
    plt.savefig(scatter_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Scatter plot saved to {scatter_path}")

    # 2. Time-series prediction plot (first test experiment)
    test_experiments = test_df["experiment_id"].unique()
    if len(test_experiments) > 0:
        first_exp = test_experiments[0]
        exp_mask = test_df["experiment_id"] == first_exp
        exp_df = test_df[exp_mask].copy()

        if target_col in exp_df.columns and exp_df[target_col].notna().any():
            valid = exp_df[target_col].notna()
            X_exp = exp_df.loc[valid, feature_cols]
            y_exp = exp_df.loc[valid, target_col]

            fig, ax = plt.subplots(figsize=(12, 5))
            x_axis = range(len(y_exp))
            ax.plot(x_axis, y_exp.values, "k-", label="Actual", linewidth=1.5)

            for name, model_info in models.items():
                y_pred_exp = model_info["model"].predict(X_exp)
                ax.plot(x_axis, y_pred_exp, "--", alpha=0.7, label=name)

            ax.set_xlabel("Time Step")
            ax.set_ylabel(target_col.replace("target_", ""))
            ax.set_title(f"Prediction over Time — {target_name.title()} "
                         f"(Experiment: {first_exp})")
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            ts_path = fig_path / f"prediction_timeseries_{target_name}.png"
            plt.savefig(ts_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"  Time-series plot saved to {ts_path}")

    # 3. Residual distribution
    fig, axes = plt.subplots(1, n_models, figsize=(6 * n_models, 4))
    if n_models == 1:
        axes = [axes]

    for ax, (name, y_pred) in zip(axes, predictions.items()):
        residuals = y_test.values - y_pred
        ax.hist(residuals, bins=50, alpha=0.7, edgecolor="black")
        ax.axvline(0, color="r", linestyle="--")
        ax.set_xlabel("Residual (Actual - Predicted)")
        ax.set_ylabel("Count")
        ax.set_title(f"{name}\nMean residual: {residuals.mean():.4f}")

    plt.suptitle(f"Residual Distribution — {target_name.title()}", fontsize=14)
    plt.tight_layout()
    resid_path = fig_path / f"residuals_{target_name}.png"
    plt.savefig(resid_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Residual plot saved to {resid_path}")

    return results_df


def evaluate_pipeline(
    processed_data_path: str,
    config_path: str = "config.yaml",
    model_dir: str = "models/saved",
    results_dir: str = "results",
) -> pd.DataFrame:
    """Run the full evaluation pipeline.

    Parameters
    ----------
    processed_data_path : str
    config_path : str
    model_dir : str
    results_dir : str

    Returns
    -------
    pd.DataFrame with all model comparison results.
    """
    config_path_obj = Path(config_path)
    with open(config_path_obj, "r") as f:
        config = yaml.safe_load(f)

    pred_cfg = config.get("prediction", {})
    df = pd.read_csv(processed_data_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    all_results = []
    model_path = Path(model_dir)

    for target_name, target_base in [
        ("contention", pred_cfg.get("contention_target", "conflict_rate")),
        ("network", pred_cfg.get("network_target", "network_rtt_ms")),
    ]:
        target_col = f"target_{target_base}"
        if target_col not in df.columns:
            print(f"  Skipping {target_name}: target column not found")
            continue

        # Load models
        models = {}

        # Persistence baseline
        models["persistence_baseline"] = {
            "model": PersistenceBaseline(target_base),
            "feature_cols": get_feature_columns(df),
        }

        # Random Forest
        rf_file = model_path / f"rf_{target_name}.joblib"
        if rf_file.exists():
            models["random_forest"] = {
                "model": joblib.load(rf_file),
                "feature_cols": get_feature_columns(df),
            }

        # XGBoost
        xgb_file = model_path / f"xgb_{target_name}.joblib"
        if xgb_file.exists():
            models["xgboost"] = {
                "model": joblib.load(xgb_file),
                "feature_cols": get_feature_columns(df),
            }

        if models:
            result_df = evaluate_models(
                df, target_name, target_col, models, config,
                figure_dir=str(Path(results_dir) / "figures"),
            )
            all_results.append(result_df)

    if all_results:
        comparison = pd.concat(all_results, ignore_index=True)
        comp_path = Path(results_dir) / "model_comparison.csv"
        comparison.to_csv(comp_path, index=False)
        print(f"\nModel comparison saved to {comp_path}")
        print(f"\n{comparison.to_string(index=False)}")
        return comparison

    return pd.DataFrame()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate ML models")
    parser.add_argument("--data", type=str,
                        default="data/processed/processed_data.csv")
    parser.add_argument("--config", type=str, default="config.yaml")
    parser.add_argument("--model-dir", type=str, default="models/saved")
    parser.add_argument("--results-dir", type=str, default="results")
    args = parser.parse_args()

    evaluate_pipeline(args.data, args.config, args.model_dir, args.results_dir)

