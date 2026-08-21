"""
Data Quality & Validation Engine
================================

MetalSense Module 2:
Data Quality & Validation Engine.

Runs a water-sample dataset through 7 validation checks:

    1. Missing values
    2. Invalid units
    3. Outliers / anomalies
    4. Duplicates
    5. Invalid coordinates
    6. Temporal consistency
    7. Unexpected changes

Produces:

    - Data Quality Score: 0-100
    - Detailed issue report
    - Recommendations

Important MetalSense data model:

A single physical water sample can contain multiple metals.

Example:

    S001 + Pb
    S001 + Cd
    S001 + As

These are NOT duplicate samples.

Therefore duplicate detection uses:

    sample_id + metal

instead of:

    sample_id
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


# ============================================================
# OPTIONAL MACHINE LEARNING DEPENDENCY
# ============================================================

try:
    from sklearn.ensemble import IsolationForest

    _HAS_SKLEARN = True

except ImportError:
    _HAS_SKLEARN = False


# ============================================================
# CONFIGURATION
# ============================================================

# Required columns for a valid metal observation.
#
# These are the fields needed for core validation and
# pollution-index calculations.
REQUIRED_COLUMNS = [
    "sample_id",
    "latitude",
    "longitude",
    "metal",
    "value",
    "unit",
]


# Optional metadata.
#
# Missing values here should NOT automatically reduce the
# data-quality score.
OPTIONAL_COLUMNS = [
    "date",
    "water_type",
    "country",
]


# ------------------------------------------------------------
# Metals understood by the validation engine
# ------------------------------------------------------------

METAL_PLAUSIBLE_RANGE_MGL = {
    "Pb": (0.0, 5.0),       # Lead
    "As": (0.0, 5.0),       # Arsenic
    "Cd": (0.0, 2.0),       # Cadmium
    "Cr": (0.0, 10.0),      # Chromium
    "Hg": (0.0, 1.0),       # Mercury
    "Ni": (0.0, 10.0),      # Nickel
    "Zn": (0.0, 50.0),      # Zinc
    "Cu": (0.0, 20.0),      # Copper
    "Fe": (0.0, 50.0),      # Iron
    "Mn": (0.0, 20.0),      # Manganese
    "Al": (0.0, 50.0),      # Aluminium
    "Co": (0.0, 5.0),       # Cobalt
    "Ti": (0.0, 5.0),       # Titanium
    "Mg": (0.0, 500.0),     # Magnesium
    "Sn": (0.0, 5.0),       # Tin
    "Ag": (0.0, 1.0),       # Silver
    "Au": (0.0, 1.0),       # Gold
}


# ------------------------------------------------------------
# Reference information
# ------------------------------------------------------------

METAL_REFERENCE_INFO = {
    "Fe": {
        "name": "Iron",
        "atomic_number": 26,
        "common_purity_ref": "≥99%",
    },
    "Cu": {
        "name": "Copper",
        "atomic_number": 29,
        "common_purity_ref": "≥99.9%",
    },
    "Al": {
        "name": "Aluminium",
        "atomic_number": 13,
        "common_purity_ref": "≥99.5%",
    },
    "Zn": {
        "name": "Zinc",
        "atomic_number": 30,
        "common_purity_ref": "≥99.9%",
    },
    "Ni": {
        "name": "Nickel",
        "atomic_number": 28,
        "common_purity_ref": "≥99%",
    },
    "Cr": {
        "name": "Chromium",
        "atomic_number": 24,
        "common_purity_ref": "≥99%",
    },
    "Co": {
        "name": "Cobalt",
        "atomic_number": 27,
        "common_purity_ref": "≥99%",
    },
    "Ti": {
        "name": "Titanium",
        "atomic_number": 22,
        "common_purity_ref": "≥99%",
    },
    "Mg": {
        "name": "Magnesium",
        "atomic_number": 12,
        "common_purity_ref": "≥99.5%",
    },
    "Mn": {
        "name": "Manganese",
        "atomic_number": 25,
        "common_purity_ref": "≥99%",
    },
    "Pb": {
        "name": "Lead",
        "atomic_number": 82,
        "common_purity_ref": "≥99.9%",
    },
    "Sn": {
        "name": "Tin",
        "atomic_number": 50,
        "common_purity_ref": "≥99.8%",
    },
    "Ag": {
        "name": "Silver",
        "atomic_number": 47,
        "common_purity_ref": "≥99.9%",
    },
    "Au": {
        "name": "Gold",
        "atomic_number": 79,
        "common_purity_ref": "≥99.9%",
    },
    "As": {
        "name": "Arsenic",
        "atomic_number": 33,
        "common_purity_ref": None,
    },
    "Cd": {
        "name": "Cadmium",
        "atomic_number": 48,
        "common_purity_ref": None,
    },
    "Hg": {
        "name": "Mercury",
        "atomic_number": 80,
        "common_purity_ref": None,
    },
}


# ------------------------------------------------------------
# Unit conversion
# ------------------------------------------------------------

UNIT_TO_MGL = {
    "mg/L": 1.0,
    "mg/l": 1.0,
    "µg/L": 0.001,
    "ug/L": 0.001,
    "ug/l": 0.001,
    "ppm": 1.0,
    "ppb": 0.001,
}


# ------------------------------------------------------------
# Valid water types
# ------------------------------------------------------------

VALID_WATER_TYPES = {
    "freshwater",
    "groundwater",
    "drinking water",
    "industrial wastewater",
    "agricultural water",
    "marine water",
    "coastal water",
}


# ------------------------------------------------------------
# India bounding box
# ------------------------------------------------------------

INDIA_BBOX = {
    "lat_min": 6.0,
    "lat_max": 38.0,
    "lon_min": 68.0,
    "lon_max": 98.0,
}


# ============================================================
# SCORING
# ============================================================

SCORING_WEIGHTS = {
    "missing_values": {
        "max_penalty": 20,
        "scale": 40,
    },
    "invalid_units": {
        "max_penalty": 15,
        "scale": 60,
    },
    "outliers_anomalies": {
        "max_penalty": 15,
        "scale": 30,
    },
    "duplicates": {
        "max_penalty": 15,
        "scale": 50,
    },
    "invalid_coordinates": {
        "max_penalty": 15,
        "scale": 60,
    },
    "temporal_consistency": {
        "max_penalty": 10,
        "scale": 50,
    },
    "unexpected_changes": {
        "max_penalty": 10,
        "scale": 30,
    },
}


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class IssueGroup:
    """Stores findings for one validation category."""

    name: str
    label: str

    affected_rows: list[int] = field(
        default_factory=list
    )

    details: list[dict[str, Any]] = field(
        default_factory=list
    )

    pct_affected: float = 0.0
    penalty: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.label,
            "affected_row_count": len(
                self.affected_rows
            ),
            "pct_affected": round(
                self.pct_affected,
                2,
            ),
            "score_penalty": round(
                self.penalty,
                2,
            ),
            "sample_issues": self.details[:10],
            "recommendation":
                self.recommendation,
        }


# ============================================================
# ENGINE
# ============================================================

class DataQualityEngine:
    """
    Validate a water heavy-metal dataset.

    Returns a 0-100 quality score together with
    detailed validation findings.

    Usage:

        engine = DataQualityEngine(df)

        report = engine.run()

        print(report["overall_score"])
    """

    def __init__(
        self,
        df: pd.DataFrame,
        use_ml_outliers: bool = True,
        restrict_to_india: bool = False,
    ):

        self.raw_df = df.copy()

        self.df = df.copy()

        self.use_ml_outliers = (
            use_ml_outliers
            and _HAS_SKLEARN
        )

        self.restrict_to_india = (
            restrict_to_india
        )

        self.n_rows = len(df)

        self.issues: dict[
            str,
            IssueGroup,
        ] = {}

    # ========================================================
    # PUBLIC API
    # ========================================================

    def run(self) -> dict[str, Any]:
        """Run all seven validation checks."""

        self._check_missing_values()

        self._check_invalid_units()

        self._check_duplicates()

        self._check_invalid_coordinates()

        self._check_temporal_consistency()

        self._check_outliers_anomalies()

        self._check_unexpected_changes()

        score = self._compute_score()

        return self._build_report(
            score
        )

    # ========================================================
    # ISSUE RECORDING
    # ========================================================

    def _record_issue(
        self,
        key: str,
        label: str,
        rows: list[int],
        details: list[dict],
        recommendation: str,
    ):

        pct = (
            len(rows)
            / self.n_rows
            * 100
            if self.n_rows
            else 0.0
        )

        weight = SCORING_WEIGHTS[key]

        penalty = min(
            weight["max_penalty"],
            (
                pct / 100
            ) * weight["scale"],
        )

        self.issues[key] = IssueGroup(
            name=key,
            label=label,
            affected_rows=rows,
            details=details,
            pct_affected=pct,
            penalty=penalty,
            recommendation=recommendation,
        )

    # ========================================================
    # 1. MISSING VALUES
    # ========================================================

    def _check_missing_values(self):

        missing_rows = []
        details = []

        # ----------------------------------------------------
        # Check required columns themselves
        # ----------------------------------------------------

        present_required = [
            column
            for column in REQUIRED_COLUMNS
            if column in self.df.columns
        ]

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in self.df.columns
        ]

        # ----------------------------------------------------
        # Missing required columns
        # ----------------------------------------------------

        if missing_columns:

            details.append(
                {
                    "missing_columns_entirely":
                        missing_columns
                }
            )

        # ----------------------------------------------------
        # Missing values in required columns
        # ----------------------------------------------------

        for idx, row in self.df.iterrows():

            blanks = []

            for column in present_required:

                value = row.get(column)

                if (
                    pd.isna(value)
                    or str(value).strip() == ""
                ):
                    blanks.append(column)

            if blanks:

                missing_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "sample_id":
                            row.get("sample_id"),
                        "missing_fields":
                            blanks,
                    }
                )

        self._record_issue(
            "missing_values",
            "Missing Values",
            missing_rows,
            details,
            (
                "Fill in required measurement fields "
                "(sample_id, coordinates, metal, value, "
                "unit) before index calculations. "
                "Date and water_type are optional metadata "
                "unless temporal/context-specific analysis "
                "has been requested."
            ),
        )

    # ========================================================
    # 2. INVALID UNITS
    # ========================================================

    def _check_invalid_units(self):

        bad_rows = []
        details = []

        if "unit" in self.df.columns:

            for idx, row in self.df.iterrows():

                unit = str(
                    row.get(
                        "unit",
                        "",
                    )
                ).strip()

                if unit not in UNIT_TO_MGL:

                    bad_rows.append(idx)

                    details.append(
                        {
                            "row": int(idx),
                            "sample_id":
                                row.get(
                                    "sample_id"
                                ),
                            "unit_found":
                                unit,
                            "accepted_units":
                                list(
                                    UNIT_TO_MGL.keys()
                                ),
                        }
                    )

        else:

            for idx in self.df.index:
                bad_rows.append(idx)

            details.append(
                {
                    "missing_column":
                        "unit"
                }
            )

        self._record_issue(
            "invalid_units",
            "Invalid Units",
            bad_rows,
            details,
            (
                "Standardize every concentration "
                "to mg/L at ingestion using a controlled "
                "unit list (mg/L, µg/L, ppm, ppb)."
            ),
        )

    # ========================================================
    # 3. DUPLICATES
    # ========================================================

    def _check_duplicates(self):
        """
        Detect duplicate sample-metal observations.

        IMPORTANT:

        A single physical sample can contain many metals.

        Therefore:

            S001 + Pb
            S001 + Cd
            S001 + As

        are valid separate observations.

        The duplicate key is:

            sample_id + metal

        Exact duplicated rows are also detected.
        """

        dup_rows = []
        details = []

        # ----------------------------------------------------
        # Sample + metal duplicate detection
        # ----------------------------------------------------

        if (
            "sample_id" in self.df.columns
            and "metal" in self.df.columns
        ):

            dup_mask = self.df.duplicated(
                subset=[
                    "sample_id",
                    "metal",
                ],
                keep=False,
            )

            for idx in self.df.index[
                dup_mask
            ]:

                dup_rows.append(idx)

                details.append(
                    {
                        "row":
                            int(idx),

                        "sample_id":
                            self.df.loc[
                                idx,
                                "sample_id",
                            ],

                        "metal":
                            self.df.loc[
                                idx,
                                "metal",
                            ],

                        "reason":
                            (
                                "duplicate "
                                "sample-metal observation"
                            ),
                    }
                )

        # ----------------------------------------------------
        # Exact full-row duplicate detection
        # ----------------------------------------------------

        exact_duplicate_mask = (
            self.df.duplicated(
                keep=False
            )
        )

        for idx in self.df.index[
            exact_duplicate_mask
        ]:

            if idx not in dup_rows:

                dup_rows.append(idx)

                details.append(
                    {
                        "row":
                            int(idx),

                        "sample_id":
                            self.df.loc[
                                idx,
                                "sample_id",
                            ],

                        "reason":
                            "exact duplicate record",
                    }
                )

        self._record_issue(
            "duplicates",
            "Duplicate Records",
            dup_rows,
            details,
            (
                "Deduplicate repeated observations "
                "using (sample_id, metal). Exact duplicate "
                "rows should also be removed before analysis."
            ),
        )

    # ========================================================
    # 4. INVALID COORDINATES
    # ========================================================

    def _check_invalid_coordinates(self):

        bad_rows = []
        details = []

        if not {
            "latitude",
            "longitude",
        }.issubset(
            self.df.columns
        ):

            missing = [
                column
                for column in [
                    "latitude",
                    "longitude",
                ]
                if column not in self.df.columns
            ]

            details.append(
                {
                    "missing_columns":
                        missing
                }
            )

            for idx in self.df.index:
                bad_rows.append(idx)

        else:

            for idx, row in self.df.iterrows():

                lat = row.get(
                    "latitude"
                )

                lon = row.get(
                    "longitude"
                )

                reason = None

                try:

                    lat_f = float(lat)

                    lon_f = float(lon)

                    if not (
                        -90
                        <= lat_f
                        <= 90
                    ):

                        reason = (
                            "out of valid "
                            "latitude range"
                        )

                    elif not (
                        -180
                        <= lon_f
                        <= 180
                    ):

                        reason = (
                            "out of valid "
                            "longitude range"
                        )

                    elif (
                        lat_f == 0
                        and lon_f == 0
                    ):

                        reason = (
                            "null island "
                            "(0,0) - likely placeholder"
                        )

                    elif (
                        self.restrict_to_india
                        and INDIA_BBOX
                        and not (
                            INDIA_BBOX[
                                "lat_min"
                            ]
                            <= lat_f
                            <= INDIA_BBOX[
                                "lat_max"
                            ]
                            and
                            INDIA_BBOX[
                                "lon_min"
                            ]
                            <= lon_f
                            <= INDIA_BBOX[
                                "lon_max"
                            ]
                        )
                    ):

                        reason = (
                            "outside expected "
                            "India bounding box"
                        )

                except (
                    TypeError,
                    ValueError,
                ):

                    reason = (
                        "non-numeric coordinate"
                    )

                if reason:

                    bad_rows.append(idx)

                    details.append(
                        {
                            "row": int(idx),
                            "sample_id":
                                row.get(
                                    "sample_id"
                                ),
                            "latitude":
                                lat,
                            "longitude":
                                lon,
                            "reason":
                                reason,
                        }
                    )

        self._record_issue(
            "invalid_coordinates",
            "Invalid Coordinates",
            bad_rows,
            details,
            (
                "Validate GPS input client-side "
                "(range + non-zero) and cross-check "
                "coordinates against the expected "
                "region before accepting a sample."
            ),
        )

    # ========================================================
    # 5. TEMPORAL CONSISTENCY
    # ========================================================

    def _check_temporal_consistency(self):

        bad_rows = []
        details = []

        # ----------------------------------------------------
        # No date column
        # ----------------------------------------------------

        if "date" not in self.df.columns:

            self._record_issue(
                "temporal_consistency",
                "Temporal Consistency",
                [],
                [],
                (
                    "No date field supplied. "
                    "Temporal validation was skipped. "
                    "Provide dates when temporal or seasonal "
                    "analysis is required."
                ),
            )

            return

        # ----------------------------------------------------
        # Parse dates
        # ----------------------------------------------------

        parsed = pd.to_datetime(
            self.df["date"],
            errors="coerce",
            utc=True,
        )

        # ----------------------------------------------------
        # Entire date column empty
        # ----------------------------------------------------

        if not parsed.notna().any():

            self._record_issue(
                "temporal_consistency",
                "Temporal Consistency",
                [],
                [],
                (
                    "No usable dates were supplied. "
                    "Temporal validation was skipped "
                    "for this dataset."
                ),
            )

            return

        now = pd.Timestamp.now(
            tz="UTC"
        )

        for idx, ts in parsed.items():

            raw_value = self.df.loc[
                idx,
                "date",
            ]

            # ------------------------------------------------
            # Only flag unparseable values if the field
            # actually contains something.
            # ------------------------------------------------

            if (
                pd.isna(ts)
                and not (
                    pd.isna(raw_value)
                    or str(raw_value).strip()
                    == ""
                    or str(raw_value).strip()
                    == "None"
                )
            ):

                bad_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "reason":
                            "unparseable date",
                        "raw_value":
                            str(raw_value),
                    }
                )

                continue

            # Completely missing dates are optional,
            # therefore they are not penalized.

            if pd.isna(ts):
                continue

            # ------------------------------------------------
            # Future date
            # ------------------------------------------------

            if ts > now:

                bad_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "reason":
                            "future-dated sample",
                        "date":
                            str(ts.date()),
                    }
                )

                continue

            # ------------------------------------------------
            # Implausibly old date
            # ------------------------------------------------

            if ts.year < 1990:

                bad_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "reason":
                            "implausibly old date",
                        "date":
                            str(ts.date()),
                    }
                )

        self._record_issue(
            "temporal_consistency",
            "Temporal Consistency",
            bad_rows,
            details,
            (
                "Reject future-dated samples and flag "
                "dates outside the configured monitoring "
                "window for manual review. Missing dates "
                "are allowed unless temporal analysis "
                "has been requested."
            ),
        )

    # ========================================================
    # 6. OUTLIERS / ANOMALIES
    # ========================================================

    def _check_outliers_anomalies(self):

        bad_rows = []
        details = []

        required = {
            "metal",
            "value",
            "unit",
        }

        if not required.issubset(
            self.df.columns
        ):

            self._record_issue(
                "outliers_anomalies",
                "Outliers / Anomalies",
                [],
                [],
                (
                    "N/A - required concentration "
                    "columns are missing."
                ),
            )

            return

        work = self.df.copy()

        work["value_mgl"] = work.apply(
            self._to_mgl,
            axis=1,
        )

        # ----------------------------------------------------
        # Domain plausibility check
        # ----------------------------------------------------

        for idx, row in work.iterrows():

            metal = row.get(
                "metal"
            )

            value_mgl = row.get(
                "value_mgl"
            )

            plausible_range = (
                METAL_PLAUSIBLE_RANGE_MGL.get(
                    metal
                )
            )

            if (
                plausible_range is not None
                and pd.notna(value_mgl)
                and not (
                    plausible_range[0]
                    <= value_mgl
                    <= plausible_range[1]
                )
            ):

                bad_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "sample_id":
                            row.get(
                                "sample_id"
                            ),
                        "metal":
                            metal,
                        "value_mgl":
                            round(
                                float(
                                    value_mgl
                                ),
                                4,
                            ),
                        "reason":
                            (
                                "outside plausible "
                                f"range {plausible_range} "
                                "mg/L"
                            ),
                    }
                )

        # ----------------------------------------------------
        # Statistical / ML detection
        # ----------------------------------------------------

        for metal, group in work.groupby(
            "metal"
        ):

            values = (
                group["value_mgl"]
                .dropna()
            )

            # Need enough observations.
            if len(values) < 5:
                continue

            if self.use_ml_outliers:

                try:

                    clf = IsolationForest(
                        contamination=0.1,
                        random_state=42,
                    )

                    predictions = (
                        clf.fit_predict(
                            values.values.reshape(
                                -1,
                                1,
                            )
                        )
                    )

                    method = (
                        "IsolationForest"
                    )

                    outlier_indices = (
                        values.index[
                            predictions == -1
                        ]
                    )

                except Exception:

                    # Fall back to IQR if the ML model
                    # can't be trained on the supplied data.
                    q1 = values.quantile(
                        0.25
                    )

                    q3 = values.quantile(
                        0.75
                    )

                    iqr = q3 - q1

                    lower = (
                        q1 - 1.5 * iqr
                    )

                    upper = (
                        q3 + 1.5 * iqr
                    )

                    method = "IQR"

                    outlier_indices = (
                        values.index[
                            (
                                values < lower
                            )
                            |
                            (
                                values > upper
                            )
                        ]
                    )

            else:

                q1 = values.quantile(
                    0.25
                )

                q3 = values.quantile(
                    0.75
                )

                iqr = q3 - q1

                lower = (
                    q1 - 1.5 * iqr
                )

                upper = (
                    q3 + 1.5 * iqr
                )

                method = "IQR"

                outlier_indices = (
                    values.index[
                        (
                            values < lower
                        )
                        |
                        (
                            values > upper
                        )
                    ]
                )

            for idx in outlier_indices:

                if idx in bad_rows:
                    continue

                bad_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "sample_id":
                            work.loc[
                                idx,
                                "sample_id",
                            ],
                        "metal":
                            metal,
                        "value_mgl":
                            round(
                                float(
                                    work.loc[
                                        idx,
                                        "value_mgl",
                                    ]
                                ),
                                4,
                            ),
                        "reason":
                            (
                                "statistical outlier "
                                f"({method})"
                            ),
                    }
                )

        self._record_issue(
            "outliers_anomalies",
            "Outliers / Anomalies",
            bad_rows,
            details,
            (
                "Route flagged samples to analyst review "
                "rather than automatically discarding them. "
                "A true contamination spike may resemble "
                "a data-entry error until verified."
            ),
        )

    # ========================================================
    # 7. UNEXPECTED CHANGES
    # ========================================================

    def _check_unexpected_changes(self):

        bad_rows = []
        details = []

        required = {
            "latitude",
            "longitude",
            "metal",
            "value",
            "unit",
            "date",
        }

        if not required.issubset(
            self.df.columns
        ):

            self._record_issue(
                "unexpected_changes",
                "Unexpected Changes",
                [],
                [],
                (
                    "Historical change detection requires "
                    "date, location, metal, value and unit."
                ),
            )

            return

        # ----------------------------------------------------
        # Parse dates
        # ----------------------------------------------------

        parsed_dates = pd.to_datetime(
            self.df["date"],
            errors="coerce",
            utc=True,
        )

        # ----------------------------------------------------
        # No usable dates
        # ----------------------------------------------------

        if not parsed_dates.notna().any():

            self._record_issue(
                "unexpected_changes",
                "Unexpected Changes",
                [],
                [],
                (
                    "No usable historical dates were supplied. "
                    "Unexpected-change detection was skipped."
                ),
            )

            return

        work = self.df.copy()

        work["value_mgl"] = work.apply(
            self._to_mgl,
            axis=1,
        )

        work["date_parsed"] = (
            parsed_dates
        )

        # ----------------------------------------------------
        # Build spatial site identifier
        # ----------------------------------------------------

        work["site"] = (
            work["latitude"]
            .round(3)
            .astype(str)
            + "_"
            + work["longitude"]
            .round(3)
            .astype(str)
        )

        # ----------------------------------------------------
        # Compare same site + same metal over time
        # ----------------------------------------------------

        for (
            site,
            metal,
        ), group in work.groupby(
            [
                "site",
                "metal",
            ]
        ):

            group = group.dropna(
                subset=[
                    "date_parsed",
                    "value_mgl",
                ]
            ).sort_values(
                "date_parsed"
            )

            if len(group) < 3:
                continue

            differences = (
                group["value_mgl"]
                .diff()
                .abs()
            )

            standard_deviation = (
                group["value_mgl"]
                .std()
            )

            if (
                not standard_deviation
                or np.isnan(
                    standard_deviation
                )
                or standard_deviation == 0
            ):

                continue

            z_scores = (
                differences
                / standard_deviation
            )

            jump_indices = group.index[
                z_scores > 3
            ]

            for idx in jump_indices:

                bad_rows.append(idx)

                details.append(
                    {
                        "row": int(idx),
                        "sample_id":
                            work.loc[
                                idx,
                                "sample_id",
                            ],
                        "metal":
                            metal,
                        "site":
                            site,
                        "value_mgl":
                            round(
                                float(
                                    work.loc[
                                        idx,
                                        "value_mgl",
                                    ]
                                ),
                                4,
                            ),
                        "reason":
                            (
                                "abrupt change vs. "
                                "site historical trend "
                                "(>3σ)"
                            ),
                    }
                )

        self._record_issue(
            "unexpected_changes",
            "Unexpected Changes",
            bad_rows,
            details,
            (
                "Trigger change-detection alerts when "
                "historical data is available. Analysts "
                "should confirm whether a large change "
                "represents a genuine pollution event or "
                "a sampling/laboratory issue."
            ),
        )

    # ========================================================
    # UNIT CONVERSION
    # ========================================================

    @staticmethod
    def _to_mgl(
        row,
    ) -> float:

        try:

            unit = str(
                row.get(
                    "unit",
                    "",
                )
            ).strip()

            factor = UNIT_TO_MGL.get(
                unit
            )

            if factor is None:
                return np.nan

            value = float(
                row.get("value")
            )

            return (
                value
                * factor
            )

        except (
            TypeError,
            ValueError,
        ):

            return np.nan

    # ========================================================
    # SCORE
    # ========================================================

    def _compute_score(
        self,
    ) -> float:

        total_penalty = sum(
            issue.penalty
            for issue in self.issues.values()
        )

        return round(
            max(
                0.0,
                100.0 - total_penalty,
            ),
            1,
        )

    # ========================================================
    # REPORT
    # ========================================================

    def _build_report(
        self,
        score: float,
    ) -> dict[str, Any]:

        flagged_rows = {
            row
            for issue in self.issues.values()
            for row in issue.affected_rows
        }

        n_flagged_rows = len(
            flagged_rows
        )

        pct_clean = (
            100
            * (
                self.n_rows
                - n_flagged_rows
            )
            / self.n_rows
            if self.n_rows
            else 0.0
        )

        return {
            "generated_at":
                datetime.now().isoformat(
                    timespec="seconds"
                ),

            "n_records":
                self.n_rows,

            "n_records_with_issues":
                n_flagged_rows,

            "pct_clean_records":
                round(
                    pct_clean,
                    1,
                ),

            "overall_score":
                score,

            "grade":
                self._grade(score),

            "outlier_method":
                (
                    "IsolationForest (ML)"
                    if self.use_ml_outliers
                    else "IQR (statistical)"
                ),

            "checks":
                {
                    key:
                        issue.to_dict()
                    for key, issue
                    in self.issues.items()
                },
        }

    # ========================================================
    # GRADE
    # ========================================================

    @staticmethod
    def _grade(
        score: float,
    ) -> str:

        if score >= 90:
            return "Excellent"

        if score >= 75:
            return "Good"

        if score >= 50:
            return "Fair"

        return "Poor"


# ============================================================
# CSV CONVENIENCE FUNCTION
# ============================================================

def run_from_csv(
    path: str,
    use_ml_outliers: bool = True,
    restrict_to_india: bool = False,
) -> dict[str, Any]:

    df = pd.read_csv(path)

    engine = DataQualityEngine(
        df,
        use_ml_outliers=use_ml_outliers,
        restrict_to_india=restrict_to_india,
    )

    return engine.run()


# ============================================================
# CONSOLE SUMMARY
# ============================================================

def print_summary(
    report: dict[str, Any],
):

    print("=" * 60)

    print(
        "DATA QUALITY & VALIDATION ENGINE - REPORT"
    )

    print("=" * 60)

    print(
        f"Records analyzed : "
        f"{report['n_records']}"
    )

    print(
        f"Records w/ issues: "
        f"{report['n_records_with_issues']} "
        f"({100 - report['pct_clean_records']:.1f}% "
        f"of dataset)"
    )

    print(
        f"Outlier method   : "
        f"{report['outlier_method']}"
    )

    print("-" * 60)

    print(
        f"DATA QUALITY SCORE: "
        f"{report['overall_score']} / 100 "
        f"[{report['grade']}]"
    )

    print("-" * 60)

    for check in report[
        "checks"
    ].values():

        print(
            f"- {check['check']:<24} "
            f"{check['affected_row_count']:>4} rows "
            f"({check['pct_affected']:>5.1f}%) "
            f"-{check['score_penalty']:.1f} pts"
        )

    print("=" * 60)


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) < 2:

        print(
            "Usage: "
            "python data_quality_engine.py "
            "<path_to_csv>"
        )

        sys.exit(1)

    report = run_from_csv(
        sys.argv[1]
    )

    print_summary(
        report
    )

    output_path = (
        sys.argv[1]
        .rsplit(
            ".",
            1,
        )[0]
        + "_quality_report.json"
    )

    with open(
        output_path,
        "w",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    print(
        f"\nFull report saved to: "
        f"{output_path}"
    )
