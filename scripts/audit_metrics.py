"""
scripts/audit_metrics.py
Standalone script to audit and recalculate ML metrics directly from
saved joblib models and the processed holdout test dataset.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocessing import chronological_experiment_split, get_feature_columns


def main():
    processed_csv = PROJECT_ROOT / "data" / "processed" / "processed_real_data.csv"
    if not processed_csv.exists():
        print(f"Error: {processed_csv} not found.")
        sys.exit(1)

    df = pd.read_csv(processed_csv)
    train_df, val_df, test_df = chronological_experiment_split(
        df, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2
    )

    print("=" * 70)
    print("DATASET SPLIT AUDIT")
    print("=" * 70)
    print(f"Total Rows: {len(df)}")
    print(f"Train Rows: {len(train_df)} | Exps: {list(train_df['experiment_id'].unique())}")
    print(f"Val Rows:   {len(val_df)} | Exps: {list(val_df['experiment_id'].unique())}")
    print(f"Test Rows:  {len(test_df)} | Exps: {list(test_df['experiment_id'].unique())}")

    feature_cols = get_feature_columns(df)
    print(f"Feature count: {len(feature_cols)}")

    models_dir = PROJECT_ROOT / "models" / "saved"

    for target_name, target_col in [("contention", "target_conflict_rate"), ("network", "target_network_rtt_ms")]:
        print("\n" + "=" * 70)
        print(f"TARGET AUDIT: {target_name.upper()} ({target_col})")
        print("=" * 70)

        test_clean = test_df.dropna(subset=[target_col]).copy()
        y_test = test_clean[target_col].values
        X_test = test_clean[feature_cols]

        print(f"Evaluated Test Samples: {len(test_clean)}")
        print(f"Ground Truth Statistics: Mean={y_test.mean():.4f}, Std={y_test.std():.4f}, Min={y_test.min():.4f}, Max={y_test.max():.4f}")

        # Persistence baseline
        source_col = target_col.replace("target_", "")
        y_pred_base = test_clean[source_col].values
        mae_base = mean_absolute_error(y_test, y_pred_base)
        rmse_base = np.sqrt(mean_squared_error(y_test, y_pred_base))
        r2_base = r2_score(y_test, y_pred_base)

        print("\n[Persistence Baseline]")
        print(f"  MAE:  {mae_base:.6f}")
        print(f"  RMSE: {rmse_base:.6f}")
        print(f"  R^2:  {r2_base:.6f}")

        # Random Forest
        rf_path = models_dir / f"rf_{target_name}.joblib"
        if rf_path.exists():
            rf_model = joblib.load(rf_path)
            y_pred_rf = rf_model.predict(X_test)
            mae_rf = mean_absolute_error(y_test, y_pred_rf)
            rmse_rf = np.sqrt(mean_squared_error(y_test, y_pred_rf))
            r2_rf = r2_score(y_test, y_pred_rf)
            print("\n[Random Forest Regressor]")
            print(f"  MAE:  {mae_rf:.6f}")
            print(f"  RMSE: {rmse_rf:.6f}")
            print(f"  R^2:  {r2_rf:.6f}")
            print(f"  Predictions: Mean={y_pred_rf.mean():.4f}, Std={y_pred_rf.std():.4f}, Min={y_pred_rf.min():.4f}, Max={y_pred_rf.max():.4f}")

        # XGBoost
        xgb_path = models_dir / f"xgb_{target_name}.joblib"
        if xgb_path.exists():
            xgb_model = joblib.load(xgb_path)
            y_pred_xgb = xgb_model.predict(X_test)
            mae_xgb = mean_absolute_error(y_test, y_pred_xgb)
            rmse_xgb = np.sqrt(mean_squared_error(y_test, y_pred_xgb))
            r2_xgb = r2_score(y_test, y_pred_xgb)
            print("\n[XGBoost Regressor]")
            print(f"  MAE:  {mae_xgb:.6f}")
            print(f"  RMSE: {rmse_xgb:.6f}")
            print(f"  R^2:  {r2_xgb:.6f}")
            print(f"  Predictions: Mean={y_pred_xgb.mean():.4f}, Std={y_pred_xgb.std():.4f}, Min={y_pred_xgb.min():.4f}, Max={y_pred_xgb.max():.4f}")


if __name__ == "__main__":
    main()
