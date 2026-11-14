"""
tests/test_pipeline.py
Unit and integration tests for the adaptive concurrency control pipeline.

Tests cover:
  - Data validation
  - Preprocessing and feature engineering
  - Target generation
  - Chronological splitting
  - Model training and prediction
  - Controller decisions
  - Switching cost estimation

Run with: python -m pytest tests/ -v
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import sys
import tempfile
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_data():
    """Create a small sample dataset for testing."""
    n = 100
    rng = np.random.default_rng(42)
    base_time = datetime(2026, 1, 1)
    
    data = {
        "timestamp": [base_time + timedelta(seconds=5 * i) for i in range(n)],
        "experiment_id": ["exp_0001"] * 50 + ["exp_0002"] * 50,
        "workload_type": ["read_heavy"] * 50 + ["write_heavy"] * 50,
        "read_write_ratio": [0.95] * 50 + [0.1] * 50,
        "concurrent_transactions": rng.integers(10, 100, n),
        "transaction_rate": rng.uniform(100, 1000, n).round(2),
        "conflict_rate": rng.uniform(0.01, 0.5, n).round(4),
        "abort_rate": rng.uniform(0.005, 0.3, n).round(4),
        "queue_length": rng.integers(0, 50, n),
        "network_rtt_ms": rng.uniform(0.5, 100, n).round(2),
        "network_jitter_ms": rng.uniform(0.1, 20, n).round(2),
        "packet_loss_rate": rng.uniform(0, 0.05, n).round(6),
        "throughput_tps": rng.uniform(50, 500, n).round(2),
        "average_latency_ms": rng.uniform(1, 50, n).round(2),
        "p95_latency_ms": rng.uniform(5, 100, n).round(2),
        "p99_latency_ms": rng.uniform(10, 200, n).round(2),
        "active_protocol": rng.choice(["OCC", "2PL", "MVCC"], n),
        "protocol_switch_count": [0] * n,
        "switching_overhead_ms": [0.0] * n,
    }
    
    df = pd.DataFrame(data)
    # Ensure latency ordering: p99 > p95 > average
    df["p95_latency_ms"] = df["average_latency_ms"] * rng.uniform(1.5, 3, n)
    df["p99_latency_ms"] = df["p95_latency_ms"] * rng.uniform(1.2, 2.5, n)
    # Ensure abort <= conflict
    df["abort_rate"] = np.minimum(df["abort_rate"], df["conflict_rate"])
    
    return df


@pytest.fixture
def config():
    """Load the project config."""
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {
        "prediction": {
            "horizon_steps": 1,
            "contention_target": "conflict_rate",
            "network_target": "network_rtt_ms",
            "lag_features": [1, 2, 3],
            "rolling_windows": [3, 5],
            "train_ratio": 0.6,
            "val_ratio": 0.2,
            "test_ratio": 0.2,
            "contention_threshold": 0.15,
            "network_rtt_threshold": 20.0,
        }
    }


# ── Validation Tests ─────────────────────────────────────────────────────

class TestValidation:
    def test_validate_schema_complete(self, sample_data):
        from src.data.validation import validate_dataset
        report = validate_dataset(sample_data)
        # Should find all columns present
        schema_findings = [f for f in report.findings
                          if f["category"] == "schema"]
        has_all_cols = any("All expected columns present" in f["message"]
                         for f in schema_findings)
        assert has_all_cols, "Should detect all columns present"

    def test_validate_schema_missing_column(self, sample_data):
        from src.data.validation import validate_dataset
        df = sample_data.drop(columns=["conflict_rate"])
        report = validate_dataset(df)
        error_findings = [f for f in report.findings
                         if f["severity"] == "ERROR"]
        assert len(error_findings) > 0, "Should flag missing column"

    def test_validate_bounds(self, sample_data):
        from src.data.validation import validate_dataset
        # Add an impossible value
        df = sample_data.copy()
        df.loc[0, "conflict_rate"] = 1.5  # above max 1.0
        report = validate_dataset(df)
        bounds_warnings = [f for f in report.findings
                          if f["category"] == "bounds" and
                          f["severity"] == "WARNING"]
        assert len(bounds_warnings) > 0

    def test_validate_no_duplicates(self, sample_data):
        from src.data.validation import validate_dataset
        report = validate_dataset(sample_data)
        dup_findings = [f for f in report.findings
                       if f["category"] == "duplicates"]
        no_dup = any("No exact duplicate" in f["message"]
                    for f in dup_findings)
        assert no_dup

    def test_quality_report_markdown(self, sample_data):
        from src.data.validation import validate_dataset
        report = validate_dataset(sample_data)
        md = report.to_markdown()
        assert "# Data Quality Report" in md
        assert "Summary" in md


# ── Preprocessing Tests ──────────────────────────────────────────────────

class TestPreprocessing:
    def test_remove_duplicates(self, sample_data):
        from src.data.preprocessing import remove_exact_duplicates
        df = pd.concat([sample_data, sample_data.iloc[:5]])
        cleaned = remove_exact_duplicates(df)
        assert len(cleaned) == len(sample_data)

    def test_sort_by_experiment_and_time(self, sample_data):
        from src.data.preprocessing import sort_by_experiment_and_time
        shuffled = sample_data.sample(frac=1, random_state=42)
        sorted_df = sort_by_experiment_and_time(shuffled)
        # Check that within each experiment, timestamps are ascending
        for exp in sorted_df["experiment_id"].unique():
            exp_df = sorted_df[sorted_df["experiment_id"] == exp]
            assert exp_df["timestamp"].is_monotonic_increasing

    def test_add_lag_features(self, sample_data):
        from src.data.preprocessing import add_lag_features
        df = add_lag_features(sample_data, ["conflict_rate"], [1, 2])
        assert "conflict_rate_lag_1" in df.columns
        assert "conflict_rate_lag_2" in df.columns
        # First lag should be NaN for the first row of each experiment
        exp1 = df[df["experiment_id"] == "exp_0001"]
        assert pd.isna(exp1.iloc[0]["conflict_rate_lag_1"])

    def test_add_rolling_features(self, sample_data):
        from src.data.preprocessing import add_rolling_features
        df = add_rolling_features(sample_data, ["throughput_tps"], [3])
        assert "throughput_tps_rmean_3" in df.columns
        assert "throughput_tps_rstd_3" in df.columns

    def test_create_prediction_targets(self, sample_data):
        from src.data.preprocessing import create_prediction_targets
        df = create_prediction_targets(
            sample_data, ["conflict_rate"], horizon=1)
        assert "target_conflict_rate" in df.columns
        # Last row of each experiment should have NaN target
        for exp in df["experiment_id"].unique():
            exp_df = df[df["experiment_id"] == exp]
            assert pd.isna(exp_df.iloc[-1]["target_conflict_rate"])

    def test_no_data_leakage_in_targets(self, sample_data):
        """Verify target is a future value, not current."""
        from src.data.preprocessing import create_prediction_targets
        df = create_prediction_targets(
            sample_data.copy(), ["conflict_rate"], horizon=1)
        exp1 = df[df["experiment_id"] == "exp_0001"].reset_index(drop=True)
        # target at row i should equal actual at row i+1
        for i in range(len(exp1) - 1):
            expected = exp1.loc[i + 1, "conflict_rate"]
            actual = exp1.loc[i, "target_conflict_rate"]
            assert abs(expected - actual) < 1e-10, \
                f"Target at row {i} should be value at row {i+1}"

    def test_chronological_split(self, sample_data):
        from src.data.preprocessing import chronological_experiment_split
        train, val, test = chronological_experiment_split(
            sample_data, 0.5, 0.25, 0.25)
        # Experiments should not overlap between splits
        train_exps = set(train["experiment_id"].unique())
        val_exps = set(val["experiment_id"].unique())
        test_exps = set(test["experiment_id"].unique())
        assert len(train_exps & val_exps) == 0
        assert len(train_exps & test_exps) == 0
        assert len(val_exps & test_exps) == 0

    def test_get_feature_columns(self, sample_data):
        from src.data.preprocessing import get_feature_columns
        features = get_feature_columns(sample_data)
        assert "conflict_rate" in features
        assert "timestamp" not in features
        assert "experiment_id" not in features


# ── Controller Tests ─────────────────────────────────────────────────────

class TestController:
    def test_static_controller(self):
        from src.controller.decision_engine import StaticController
        ctrl = StaticController("MVCC", config_path=None)
        decision = ctrl.decide(
            current_protocol="OCC",
            current_time=datetime(2026, 1, 1),
        )
        assert decision.action == "maintain"
        assert decision.controller_type == "static"

    def test_reactive_controller_high_contention(self):
        from src.controller.decision_engine import ReactiveController
        ctrl = ReactiveController(config_path=None)
        decision = ctrl.decide(
            current_protocol="OCC",
            current_contention=0.5,  # high
            current_network_rtt=2.0,  # normal
            current_time=datetime(2026, 1, 1),
        )
        assert decision.recommended_protocol == "2PL"

    def test_reactive_controller_high_network(self):
        from src.controller.decision_engine import ReactiveController
        ctrl = ReactiveController(config_path=None)
        decision = ctrl.decide(
            current_protocol="OCC",
            current_contention=0.02,
            current_network_rtt=100.0,  # high RTT
            current_time=datetime(2026, 1, 1),
        )
        assert decision.recommended_protocol == "MVCC"

    def test_predictive_controller_fallback(self):
        from src.controller.decision_engine import PredictiveController
        ctrl = PredictiveController(config_path=None)
        decision = ctrl.decide(
            current_protocol="OCC",
            predicted_contention=None,  # missing
            predicted_network_rtt=None,
            current_contention=0.05,
            current_network_rtt=3.0,
            current_time=datetime(2026, 1, 1),
        )
        assert "FALLBACK" in decision.reason

    def test_hysteresis(self):
        from src.controller.decision_engine import ReactiveController
        ctrl = ReactiveController(config_path=None)
        t1 = datetime(2026, 1, 1, 0, 0, 0)
        t2 = datetime(2026, 1, 1, 0, 0, 10)  # 10 seconds later

        # First decision: switch
        d1 = ctrl.decide(
            current_protocol="OCC",
            current_contention=0.5,
            current_network_rtt=2.0,
            current_time=t1,
        )
        assert d1.action == "switch"

        # Second decision too soon: should be blocked
        d2 = ctrl.decide(
            current_protocol="2PL",
            current_contention=0.01,  # now low → wants OCC
            current_network_rtt=2.0,
            current_time=t2,
        )
        assert d2.action == "maintain"
        assert "hysteresis" in d2.reason.lower()

    def test_decision_logging(self):
        from src.controller.decision_engine import StaticController
        ctrl = StaticController("OCC", config_path=None)
        for i in range(5):
            ctrl.decide(
                current_protocol="OCC",
                current_time=datetime(2026, 1, 1, 0, i),
            )
        log_df = ctrl.get_decision_log_df()
        assert len(log_df) == 5


# ── Switching Cost Tests ─────────────────────────────────────────────────

class TestSwitchingCost:
    def test_same_protocol_zero_cost(self):
        from src.controller.switching_cost import SwitchingCostEstimator
        estimator = SwitchingCostEstimator()
        assert estimator.get_cost("OCC", "OCC") == 0.0

    def test_different_protocol_nonzero_cost(self):
        from src.controller.switching_cost import SwitchingCostEstimator
        estimator = SwitchingCostEstimator()
        cost = estimator.get_cost("OCC", "2PL")
        assert cost > 0

    def test_transition_requirements(self):
        from src.controller.switching_cost import SwitchingCostEstimator
        estimator = SwitchingCostEstimator()
        reqs = estimator.get_transition_requirements("OCC", "2PL")
        assert "steps" in reqs
        assert len(reqs["steps"]) > 0


# ── Integration Test ─────────────────────────────────────────────────────

class TestIntegration:
    def test_full_pipeline_with_sample_data(self, sample_data, tmp_path):
        """Test the full pipeline: save → preprocess → check."""
        from src.data.preprocessing import (
            run_preprocessing_pipeline,
            add_lag_features,
            add_rolling_features,
            create_prediction_targets,
            get_feature_columns,
            chronological_experiment_split,
        )
        from src.data.validation import validate_dataset

        # Save sample data
        raw_path = tmp_path / "test_raw.csv"
        sample_data.to_csv(raw_path, index=False)

        # Create a minimal config
        import yaml
        config = {
            "data": {"processed_dir": str(tmp_path / "processed"),
                     "sample_dir": str(tmp_path / "sample")},
            "prediction": {
                "horizon_steps": 1,
                "contention_target": "conflict_rate",
                "network_target": "network_rtt_ms",
                "lag_features": [1, 2],
                "rolling_windows": [3],
                "train_ratio": 0.5,
                "val_ratio": 0.25,
                "test_ratio": 0.25,
                "contention_threshold": 0.15,
                "network_rtt_threshold": 20.0,
            },
        }
        config_path = tmp_path / "test_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)

        # Run preprocessing
        output_path = tmp_path / "processed" / "processed.csv"
        processed = run_preprocessing_pipeline(
            str(raw_path),
            config_path=str(config_path),
            output_path=str(output_path),
        )

        # Verify outputs
        assert output_path.exists()
        assert "target_conflict_rate" in processed.columns
        assert "target_network_rtt_ms" in processed.columns
        assert "conflict_rate_lag_1" in processed.columns

        # Verify split
        train, val, test = chronological_experiment_split(
            processed, 0.5, 0.25, 0.25)
        total = len(train) + len(val) + len(test)
        assert total == len(processed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

