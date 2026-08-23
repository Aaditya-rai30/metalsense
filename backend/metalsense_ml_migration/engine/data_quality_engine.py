from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd

class CheckResult:
    name: str
    passed: bool
    issues_found: int
    message: str
    severity: str = "warning"
    affected_rows: List[int] = field(default_factory=list)

    def as_dict(self):
        return {
            "name": self.name,
            "passed": self.passed,
            "issues_found": self.issues_found,
            "message": self.message,
            "severity": self.severity,
            "affected_rows": self.affected_rows,
        }

class QualityReport:
    total_records: int
    valid_records: int
    score: float
    checks: List[CheckResult]
    flagged_row_indices: List[int] = field(default_factory=list)
    rejected_row_indices: List[int] = field(default_factory=list)
    warning_row_indices: List[int] = field(default_factory=list)
    column_issues: Dict[str, int] = field(default_factory=dict)

    @property
    def status(self):
        return "GOOD" if self.score >= 90 else "ACCEPTABLE" if self.score >= 75 else "REVIEW" if self.score >= 50 else "POOR"

    def as_dict(self):
        return {
            "data_quality_score": round(self.score, 1),
            "quality_status": self.status,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.total_records - self.valid_records,
            "checks_needing_review": sum(not c.passed for c in self.checks),
            "checks": [c.as_dict() for c in self.checks],
            "flagged_rows": self.flagged_row_indices,
            "rejected_rows": self.rejected_row_indices,
            "warning_rows": self.warning_row_indices,
            "column_issues": self.column_issues,
        }

class DataValidator:
    Z_SCORE_THRESHOLD = 2.0
    IQR_FACTOR = 1.5
    MAX_PLAUSIBLE_CONCENTRATION_MG_L = 1000.0

    def __init__(self, z_threshold=2.0, max_concentration_mg_l=1000.0):
        self.Z_SCORE_THRESHOLD = z_threshold
        self.MAX_PLAUSIBLE_CONCENTRATION_MG_L = max_concentration_mg_l

    def validate(self, df: pd.DataFrame) -> QualityReport:
        if not isinstance(df, pd.DataFrame):
            raise TypeError("validate() expects a pandas DataFrame")
        if df.empty:
            return QualityReport(0, 0, 0, [])

        # Season-aware date completion happens before validation so that
        # a missing date can be recovered when reliable season metadata
        # is available. Rows without a usable date AND without a usable
        # season remain invalid and are reported by the Sample dates check.
        df = fill_missing_dates_from_season(df)

        df = df.replace(["", " ", "NA", "N/A", "na", "n/a", "null", "NULL", "None", "none", "-", "--"], np.nan)
        n = len(df)
        checks, flagged, rejected, warnings, column_issues = [], set(), set(), set(), {}

        def add(name, passed, issues, message, severity, rows):
            rows = list(rows)
            checks.append(CheckResult(name, passed, issues, message, severity, rows))
            flagged.update(rows)
            (rejected if severity == "error" else warnings).update(rows)

        required = {"sample_id", "date", "latitude", "longitude"}
        missing_cols = sorted(required - set(df.columns))
        rows = df.index.tolist() if missing_cols else []
        add("Required columns", not missing_cols, len(missing_cols), "All required columns are present" if not missing_cols else f"Missing columns: {', '.join(missing_cols)}", "error", rows)

        missing = df.isna().any(axis=1)
        missing_cells = int(df.isna().sum().sum())
        for c, v in df.isna().sum().items():
            if v:
                column_issues[f"missing:{c}"] = int(v)
        add("Missing values", missing_cells == 0, missing_cells, "No missing values detected" if not missing_cells else f"{missing_cells} missing cell(s)", "error", df.index[missing].tolist())

        if "sample_id" in df:
            ids = df["sample_id"].astype("string").str.strip()
            blank = ids.isna() | ids.eq("")
            dup = ids.notna() & ids.duplicated(keep=False)
            bad = blank | dup
            column_issues["blank_sample_id"] = int(blank.sum())
            column_issues["duplicate_sample_id"] = int(dup.sum())
            add("Sample IDs", not bad.any(), int(bad.sum()), "All sample IDs are valid and unique" if not bad.any() else f"{int(bad.sum())} row(s) have blank or duplicate sample IDs", "error", df.index[bad].tolist())

        metal_cols = [m for m in METALS if m in df.columns]
        numeric = {m: pd.to_numeric(df[m], errors="coerce") for m in metal_cols}

        non_numeric = pd.Series(False, index=df.index)
        for m, s in numeric.items():
            bad = s.isna() & df[m].notna()
            non_numeric |= bad
            if bad.any():
                column_issues[f"non_numeric:{m}"] = int(bad.sum())
        add("Numeric metal concentrations", not non_numeric.any(), int(non_numeric.sum()), "All metal concentrations are numeric" if not non_numeric.any() else f"{int(non_numeric.sum())} row(s) contain non-numeric concentrations", "error", df.index[non_numeric].tolist())

        invalid_range = pd.Series(False, index=df.index)
        for m, s in numeric.items():
            bad = (s < 0) | (s > self.MAX_PLAUSIBLE_CONCENTRATION_MG_L)
            invalid_range |= bad.fillna(False)
            if bad.any():
                column_issues[f"range:{m}"] = int(bad.sum())
        add("Concentration range", not invalid_range.any(), int(invalid_range.sum()), "All concentrations are within the plausible range" if not invalid_range.any() else f"{int(invalid_range.sum())} row(s) contain negative or implausible values", "error", df.index[invalid_range].tolist())

        if {"latitude", "longitude"} <= set(df.columns):
            lat, lon = pd.to_numeric(df.latitude, errors="coerce"), pd.to_numeric(df.longitude, errors="coerce")
            bad = lat.isna() | lon.isna() | ~lat.between(-90, 90) | ~lon.between(-180, 180)
        else:
            bad = pd.Series(True, index=df.index)
        add("Coordinates", not bad.any(), int(bad.sum()), "All coordinates are valid" if not bad.any() else f"{int(bad.sum())} row(s) have invalid or missing coordinates", "error", df.index[bad].tolist())

        if "date" in df:
            dates = pd.to_datetime(df["date"], errors="coerce")
            bad = dates.isna()
        else:
            bad = pd.Series(True, index=df.index)
        add("Sample dates", not bad.any(), int(bad.sum()), "All sample dates are valid" if not bad.any() else f"{int(bad.sum())} row(s) have invalid or missing dates", "error", df.index[bad].tolist())

        outlier = pd.Series(False, index=df.index)
        for m, s in numeric.items():
            v = s.dropna()
            if len(v) >= 4 and v.std(ddof=0) > 0:
                z = (s - v.mean()) / v.std(ddof=0)
                outlier |= z.abs().gt(self.Z_SCORE_THRESHOLD).fillna(False)
        add(f"Statistical outliers (z > {self.Z_SCORE_THRESHOLD:g}σ)", not outlier.any(), int(outlier.sum()), "No statistical outliers detected" if not outlier.any() else f"{int(outlier.sum())} row(s) show unusual concentrations", "warning", df.index[outlier].tolist())

        iqr_outlier = pd.Series(False, index=df.index)
        for m, s in numeric.items():
            v = s.dropna()
            if len(v) >= 5:
                q1, q3 = v.quantile(.25), v.quantile(.75)
                iqr = q3 - q1
                if iqr > 0:
                    iqr_outlier |= ((s < q1 - self.IQR_FACTOR * iqr) | (s > q3 + self.IQR_FACTOR * iqr)).fillna(False)
        add("Robust statistical outliers (IQR)", not iqr_outlier.any(), int(iqr_outlier.sum()), "No IQR outliers detected" if not iqr_outlier.any() else f"{int(iqr_outlier.sum())} row(s) show robust outlier behaviour", "warning", df.index[iqr_outlier].tolist())

        inf = pd.Series(False, index=df.index)
        for s in numeric.values():
            inf |= np.isinf(s.fillna(0))
        add("Infinite values", not inf.any(), int(inf.sum()), "No infinite values detected" if not inf.any() else f"{int(inf.sum())} row(s) contain infinite values", "error", df.index[inf].tolist())

        row_score = (n - len(rejected)) / n * 100
        check_score = sum(c.passed for c in checks) / len(checks) * 100
        warning_penalty = min(20, len(warnings) / n * 20)
        score = max(0, min(100, .60 * row_score + .40 * check_score - warning_penalty))
        return QualityReport(n, n - len(rejected), score, checks, sorted(flagged), sorted(rejected), sorted(warnings), column_issues)

    def clean(self, df, report=None):
        report = report or self.validate(df)
        return df.drop(index=report.rejected_row_indices).copy()


def validate_dataframe(df: pd.DataFrame) -> QualityReport:
    """Validate a dataframe using the final ML validator, including seasonal date inference."""
    from engine.temporal_engine import fill_missing_dates_from_season
    normalized = fill_missing_dates_from_season(df)
    return DataValidator().validate(normalized)
