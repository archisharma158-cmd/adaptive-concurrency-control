"""
src/data/validation.py
Data validation module for the adaptive concurrency control research.

Validates raw experimental data against expected schemas, bounds, and
consistency rules. Generates a data-quality report.

All validation flags records but does NOT delete them — the researcher
decides what to do with flagged rows.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional


# ── Expected dataset schema ──────────────────────────────────────────────
EXPECTED_COLUMNS = [
    "timestamp",
    "experiment_id",
    "workload_type",
    "read_write_ratio",
    "concurrent_transactions",
    "transaction_rate",
    "conflict_rate",
    "abort_rate",
    "queue_length",
    "network_rtt_ms",
    "network_jitter_ms",
    "packet_loss_rate",
    "throughput_tps",
    "average_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "active_protocol",
    "protocol_switch_count",
    "switching_overhead_ms",
]

# Expected data types (after parsing)
EXPECTED_DTYPES = {
    "experiment_id": "object",
    "workload_type": "object",
    "read_write_ratio": "float64",
    "concurrent_transactions": "int64",
    "transaction_rate": "float64",
    "conflict_rate": "float64",
    "abort_rate": "float64",
    "queue_length": "int64",
    "network_rtt_ms": "float64",
    "network_jitter_ms": "float64",
    "packet_loss_rate": "float64",
    "throughput_tps": "float64",
    "average_latency_ms": "float64",
    "p95_latency_ms": "float64",
    "p99_latency_ms": "float64",
    "active_protocol": "object",
    "protocol_switch_count": "int64",
    "switching_overhead_ms": "float64",
}

# Valid categorical values
VALID_WORKLOAD_TYPES = {"read_heavy", "write_heavy", "mixed", "scan_heavy"}
VALID_PROTOCOLS = {"OCC", "2PL", "MVCC"}

# Default bounds for numeric validation
DEFAULT_BOUNDS = {
    "conflict_rate": (0.0, 1.0),
    "abort_rate": (0.0, 1.0),
    "packet_loss_rate": (0.0, 1.0),
    "read_write_ratio": (0.0, 1.0),
    "network_rtt_ms": (0.0, 10_000.0),
    "network_jitter_ms": (0.0, 5_000.0),
    "throughput_tps": (0.0, 1_000_000.0),
    "average_latency_ms": (0.0, 100_000.0),
    "p95_latency_ms": (0.0, 100_000.0),
    "p99_latency_ms": (0.0, 100_000.0),
    "concurrent_transactions": (1, 10_000),
    "transaction_rate": (0.0, 1_000_000.0),
    "queue_length": (0, 100_000),
    "switching_overhead_ms": (0.0, 100_000.0),
    "protocol_switch_count": (0, 100_000),
}


class DataQualityReport:
    """Collects and formats data quality findings."""

    def __init__(self):
        self.findings: list[dict] = []
        self.summary: dict = {}

    def add_finding(self, category: str, severity: str, message: str,
                    affected_rows: int = 0, details: str = ""):
        """Record a validation finding.

        Parameters
        ----------
        category : str
            e.g. 'schema', 'missing', 'bounds', 'duplicates', 'consistency'
        severity : str
            'INFO', 'WARNING', or 'ERROR'
        message : str
            Human-readable description.
        affected_rows : int
            Number of rows affected.
        details : str
            Additional detail string.
        """
        self.findings.append({
            "category": category,
            "severity": severity,
            "message": message,
            "affected_rows": affected_rows,
            "details": details,
        })

    def to_markdown(self) -> str:
        """Generate a Markdown report."""
        lines = [
            "# Data Quality Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if self.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for k, v in self.summary.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

        # Group findings by category
        categories = sorted(set(f["category"] for f in self.findings))
        for cat in categories:
            cat_findings = [f for f in self.findings if f["category"] == cat]
            lines.append(f"## {cat.replace('_', ' ').title()}")
            lines.append("")
            for f in cat_findings:
                icon = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(
                    f["severity"], "•"
                )
                lines.append(f"- {icon} **{f['severity']}**: {f['message']}")
                if f["affected_rows"]:
                    lines.append(f"  - Affected rows: {f['affected_rows']}")
                if f["details"]:
                    lines.append(f"  - {f['details']}")
            lines.append("")

        if not self.findings:
            lines.append("✅ No issues found.")
            lines.append("")

        return "\n".join(lines)


def validate_schema(df: pd.DataFrame, report: DataQualityReport) -> None:
    """Check that expected columns exist and flag extras / missing."""
    present = set(df.columns)
    expected = set(EXPECTED_COLUMNS)

    missing = expected - present
    extra = present - expected

    if missing:
        report.add_finding(
            "schema", "ERROR",
            f"Missing columns: {sorted(missing)}",
            details="These columns are required by the dataset schema."
        )
    if extra:
        report.add_finding(
            "schema", "INFO",
            f"Extra columns found: {sorted(extra)}",
            details="Extra columns are kept but not used by the pipeline."
        )
    if not missing:
        report.add_finding("schema", "INFO", "All expected columns present.")


def validate_dtypes(df: pd.DataFrame, report: DataQualityReport) -> pd.DataFrame:
    """Attempt to cast columns to expected types and report failures."""
    for col, expected_dtype in EXPECTED_DTYPES.items():
        if col not in df.columns:
            continue
        try:
            if expected_dtype == "int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif expected_dtype == "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            # 'object' columns are left as-is
        except Exception as e:
            report.add_finding(
                "schema", "WARNING",
                f"Column '{col}' could not be cast to {expected_dtype}: {e}"
            )
    report.add_finding("schema", "INFO", "Data type validation completed.")
    return df


def check_duplicates(df: pd.DataFrame, report: DataQualityReport) -> pd.DataFrame:
    """Detect duplicate records."""
    n_exact = df.duplicated().sum()
    if n_exact > 0:
        report.add_finding(
            "duplicates", "WARNING",
            f"Found {n_exact} exact duplicate rows.",
            affected_rows=int(n_exact),
        )
    else:
        report.add_finding("duplicates", "INFO", "No exact duplicate rows found.")

    # Check duplicates by (experiment_id, timestamp)
    if {"experiment_id", "timestamp"}.issubset(df.columns):
        n_key_dup = df.duplicated(subset=["experiment_id", "timestamp"]).sum()
        if n_key_dup > 0:
            report.add_finding(
                "duplicates", "WARNING",
                f"{n_key_dup} rows share (experiment_id, timestamp).",
                affected_rows=int(n_key_dup),
            )
    return df


def check_missing_values(df: pd.DataFrame, report: DataQualityReport) -> None:
    """Identify columns with missing values."""
    missing = df.isnull().sum()
    cols_with_missing = missing[missing > 0]

    if len(cols_with_missing) == 0:
        report.add_finding("missing", "INFO", "No missing values detected.")
    else:
        for col, count in cols_with_missing.items():
            pct = 100 * count / len(df)
            report.add_finding(
                "missing", "WARNING",
                f"Column '{col}' has {count} missing values ({pct:.1f}%).",
                affected_rows=int(count),
            )


def check_bounds(df: pd.DataFrame, report: DataQualityReport,
                 bounds: Optional[dict] = None) -> None:
    """Flag values outside expected numeric bounds."""
    bounds = bounds or DEFAULT_BOUNDS
    for col, (lo, hi) in bounds.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        below = (series < lo).sum()
        above = (series > hi).sum()
        if below > 0:
            report.add_finding(
                "bounds", "WARNING",
                f"Column '{col}': {below} values below minimum {lo}.",
                affected_rows=int(below),
            )
        if above > 0:
            report.add_finding(
                "bounds", "WARNING",
                f"Column '{col}': {above} values above maximum {hi}.",
                affected_rows=int(above),
            )
    report.add_finding("bounds", "INFO", "Bounds validation completed.")


def check_categorical_values(df: pd.DataFrame, report: DataQualityReport) -> None:
    """Validate that categorical columns contain only expected values."""
    if "workload_type" in df.columns:
        invalid = set(df["workload_type"].dropna().unique()) - VALID_WORKLOAD_TYPES
        if invalid:
            report.add_finding(
                "consistency", "WARNING",
                f"Unexpected workload_type values: {invalid}",
                affected_rows=int(df["workload_type"].isin(invalid).sum()),
            )
    if "active_protocol" in df.columns:
        invalid = set(df["active_protocol"].dropna().unique()) - VALID_PROTOCOLS
        if invalid:
            report.add_finding(
                "consistency", "WARNING",
                f"Unexpected active_protocol values: {invalid}",
                affected_rows=int(df["active_protocol"].isin(invalid).sum()),
            )


def check_latency_consistency(df: pd.DataFrame, report: DataQualityReport) -> None:
    """Check that p95 >= average and p99 >= p95 latency."""
    cols = {"average_latency_ms", "p95_latency_ms", "p99_latency_ms"}
    if not cols.issubset(df.columns):
        return

    p95_lt_avg = (df["p95_latency_ms"] < df["average_latency_ms"]).sum()
    p99_lt_p95 = (df["p99_latency_ms"] < df["p95_latency_ms"]).sum()

    if p95_lt_avg > 0:
        report.add_finding(
            "consistency", "WARNING",
            f"{p95_lt_avg} rows where p95_latency < average_latency.",
            affected_rows=int(p95_lt_avg),
        )
    if p99_lt_p95 > 0:
        report.add_finding(
            "consistency", "WARNING",
            f"{p99_lt_p95} rows where p99_latency < p95_latency.",
            affected_rows=int(p99_lt_p95),
        )


def check_abort_vs_conflict(df: pd.DataFrame, report: DataQualityReport) -> None:
    """Abort rate should generally not exceed conflict rate."""
    if {"abort_rate", "conflict_rate"}.issubset(df.columns):
        violations = (df["abort_rate"] > df["conflict_rate"]).sum()
        if violations > 0:
            report.add_finding(
                "consistency", "WARNING",
                f"{violations} rows where abort_rate > conflict_rate.",
                affected_rows=int(violations),
                details="Abort rate exceeding conflict rate is unusual but "
                        "possible if aborts occur for reasons beyond conflicts."
            )


def validate_dataset(df: pd.DataFrame,
                     bounds: Optional[dict] = None) -> DataQualityReport:
    """Run all validation checks and return a quality report.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to validate.
    bounds : dict, optional
        Custom numeric bounds. Falls back to DEFAULT_BOUNDS.

    Returns
    -------
    DataQualityReport
        Populated report object.
    """
    report = DataQualityReport()

    # Summary statistics
    report.summary = {
        "Total rows": len(df),
        "Total columns": len(df.columns),
        "Experiments": df["experiment_id"].nunique() if "experiment_id" in df.columns else "N/A",
        "Time range": (
            f"{df['timestamp'].min()} → {df['timestamp'].max()}"
            if "timestamp" in df.columns else "N/A"
        ),
    }

    validate_schema(df, report)
    df = validate_dtypes(df, report)
    check_duplicates(df, report)
    check_missing_values(df, report)
    check_bounds(df, report, bounds)
    check_categorical_values(df, report)
    check_latency_consistency(df, report)
    check_abort_vs_conflict(df, report)

    return report


def save_quality_report(report: DataQualityReport, path: str) -> None:
    """Write the quality report to a Markdown file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(report.to_markdown(), encoding="utf-8")
    print(f"Data quality report saved to {path}")

