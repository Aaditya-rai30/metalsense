from __future__ import annotations

import re
from typing import Any

import pandas as pd


# ============================================================
# SEASON → REPRESENTATIVE DATE
# ============================================================

SEASON_DATE_ANCHORS = {
    "winter": (1, 15),
    "summer": (4, 15),
    "spring": (4, 15),

    "pre-monsoon": (5, 15),
    "premonsoon": (5, 15),

    "monsoon": (8, 15),
    "rainy": (8, 15),
    "wet": (8, 15),

    "post-monsoon": (11, 15),
    "postmonsoon": (11, 15),
    "autumn": (11, 15),
    "fall": (11, 15),

    "dry": (1, 15),
}


# ============================================================
# HELPERS
# ============================================================

def _normalise_season(
    value: Any,
) -> str:
    """
    Normalize season labels so variants such as:

        Pre-Monsoon
        pre monsoon
        PREMONSOON

    resolve consistently.
    """

    if value is None or pd.isna(value):
        return ""

    return re.sub(
        r"[^a-z]",
        "",
        str(value).strip().lower(),
    )


def _season_anchor(
    season: Any,
):
    return SEASON_DATE_ANCHORS.get(
        _normalise_season(season)
    )


# ============================================================
# DATE INFERENCE
# ============================================================

def fill_missing_dates_from_season(
    df: pd.DataFrame,
    reference_year: int | None = None,
) -> pd.DataFrame:
    """
    Infer representative dates only for missing or
    unparseable dates.

    Existing valid dates are NEVER overwritten.

    Example:

        season = "Monsoon"
        date   = NaN

    becomes:

        date = 2026-08-15T00:00:00+00:00
        date_inferred = True
        date_inference_source = "season:Monsoon"

    The date column is explicitly converted to a UTC
    datetime dtype before assignment. This is important
    because pandas may infer a completely empty CSV date
    column as float64.
    """

    out = df.copy()

    # --------------------------------------------------------
    # DATE COLUMN
    # --------------------------------------------------------
    #
    # Always create/normalize the date column first.
    # This prevents:
    #
    #     TypeError:
    #     Invalid value '...' for dtype 'float64'
    #
    # when assigning an inferred datetime to an empty
    # CSV column.
    # --------------------------------------------------------

    if "date" not in out.columns:

        out["date"] = pd.Series(
            pd.NaT,
            index=out.index,
            dtype="datetime64[ns, UTC]",
        )

    else:

        out["date"] = pd.to_datetime(
            out["date"],
            errors="coerce",
            utc=True,
        )

    parsed = out["date"].copy()

    # --------------------------------------------------------
    # INFERENCE FLAGS
    # --------------------------------------------------------

    if "date_inferred" not in out.columns:

        out["date_inferred"] = False

    else:

        out["date_inferred"] = (
            out["date_inferred"]
            .fillna(False)
            .astype(bool)
        )

    if "date_inference_source" not in out.columns:

        out["date_inference_source"] = ""

    else:

        out["date_inference_source"] = (
            out["date_inference_source"]
            .fillna("")
            .astype(str)
        )

    # --------------------------------------------------------
    # NO SEASON COLUMN
    # --------------------------------------------------------

    if "season" not in out.columns:
        return out

    # --------------------------------------------------------
    # REFERENCE YEAR
    # --------------------------------------------------------

    if reference_year is None:

        years = (
            parsed
            .dropna()
            .dt.year
        )

        if len(years):

            reference_year = int(
                years.median()
            )

        else:

            reference_year = (
                pd.Timestamp
                .now(
                    tz="UTC"
                )
                .year
            )

    # --------------------------------------------------------
    # INFER MISSING DATES
    # --------------------------------------------------------

    for idx in out.index:

        # Keep existing valid dates untouched.
        if pd.notna(
            parsed.loc[idx]
        ):
            continue

        season_value = out.at[
            idx,
            "season",
        ]

        anchor = _season_anchor(
            season_value
        )

        # Unknown / empty season.
        if anchor is None:
            continue

        month, day = anchor

        try:

            inferred = pd.Timestamp(
                year=reference_year,
                month=month,
                day=day,
                tz="UTC",
            )

        except ValueError:

            # Invalid anchor/date.
            continue

        # ----------------------------------------------------
        # IMPORTANT:
        # date is already datetime64[ns, UTC], so assignment
        # is dtype-safe.
        # ----------------------------------------------------

        out.at[
            idx,
            "date",
        ] = inferred

        out.at[
            idx,
            "date_inferred",
        ] = True

        out.at[
            idx,
            "date_inference_source",
        ] = (
            "season:"
            f"{str(season_value).strip()}"
        )

    # --------------------------------------------------------
    # FINAL NORMALIZATION
    # --------------------------------------------------------

    out["date"] = pd.to_datetime(
        out["date"],
        errors="coerce",
        utc=True,
    )

    return out


# ============================================================
# TEMPORAL SERIES
# ============================================================

def temporal_series(
    records,
    dataset_id,
):
    """
    Build a date-based temporal series from analyzed records.

    Records without a usable date are skipped.
    """

    rows = []

    for record in records:

        date = pd.to_datetime(
            record.get("date"),
            errors="coerce",
            utc=True,
        )

        if pd.isna(date):
            continue

        analysis = record.get(
            "analysis",
            {},
        )

        rows.append(
            {
                "date":
                    date.strftime(
                        "%Y-%m-%d"
                    ),

                "season":
                    record.get(
                        "season"
                    ),

                "date_inferred":
                    bool(
                        record.get(
                            "date_inferred",
                            False,
                        )
                    ),

                "hpi":
                    analysis.get(
                        "hpi"
                    ),

                "hei":
                    analysis.get(
                        "hei"
                    ),

                "cd":
                    analysis.get(
                        "cd"
                    ),
            }
        )

    # --------------------------------------------------------
    # NO VALID DATES
    # --------------------------------------------------------

    if not rows:

        return {
            "dataset_id":
                dataset_id,

            "series":
                [],
        }

    df = pd.DataFrame(
        rows
    )

    # --------------------------------------------------------
    # GROUP BY DATE
    # --------------------------------------------------------
    #
    # Keep only numeric analysis fields in the mean.
    # date_inferred is converted to numeric automatically
    # by pandas here.
    # --------------------------------------------------------

    grouped = (
        df.groupby(
            "date",
            as_index=False,
        )
        .mean(
            numeric_only=True
        )
    )

    return {
        "dataset_id":
            dataset_id,

        "series":
            grouped.to_dict(
                orient="records"
            ),
    }