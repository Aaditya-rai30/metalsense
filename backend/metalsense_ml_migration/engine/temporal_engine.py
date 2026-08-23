from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd

# STEP 0A: SEASON-AWARE SAMPLE DATE INFERENCE

SEASON_DATE_ANCHORS = {
    # Indian/common field-monitoring seasons. The generated date is
    # a representative anchor, not a claim about the actual sampling day.
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


def _normalise_season(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"[^a-z]", "", str(value).strip().lower())


def _season_anchor(season: str):
    key = _normalise_season(season)
    aliases = {
        "winter": "winter",
        "summer": "summer",
        "spring": "spring",
        "premonsoon": "premonsoon",
        "monsoon": "monsoon",
        "rainy": "rainy",
        "wet": "wet",
        "postmonsoon": "postmonsoon",
        "autumn": "autumn",
        "fall": "fall",
        "dry": "dry",
    }
    canonical = aliases.get(key)
    return SEASON_DATE_ANCHORS.get(canonical) if canonical else None


def fill_missing_dates_from_season(
    df: pd.DataFrame,
    reference_year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fill missing/invalid sample dates when a season field is available.

    Existing valid dates are preserved. For a missing date, a representative
    midpoint date for the supplied season is inserted and the row is marked
    with ``date_inferred=True``. The inferred date is metadata for temporal
    grouping/visualisation; it is NOT presented as the actual laboratory
    sampling date.
    """
    out = df.copy()

    if "date" not in out.columns:
        out["date"] = pd.NaT

    parsed = pd.to_datetime(out["date"], errors="coerce")

    if "date_inferred" not in out.columns:
        out["date_inferred"] = False
    else:
        out["date_inferred"] = out["date_inferred"].fillna(False).astype(bool)

    if "season" not in out.columns:
        out["season"] = pd.NA

    valid_years = parsed.dropna().dt.year
    if reference_year is None:
        reference_year = int(valid_years.median()) if not valid_years.empty else pd.Timestamp.utcnow().year

    for idx in out.index[parsed.isna()]:
        anchor = _season_anchor(out.at[idx, "season"])
        if anchor is None:
            continue

        month, day = anchor
        out.at[idx, "date"] = pd.Timestamp(
            year=reference_year,
            month=month,
            day=day,
        )
        out.at[idx, "date_inferred"] = True

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out


def temporal_series(records, dataset_id):
        rows = []
        for r in records:
            try:
                d = pd.to_datetime(r.get("date"), errors="coerce")
                if pd.isna(d):
                    continue
                a = r.get("analysis", {})
                rows.append({"date": d.strftime("%Y-%m-%d"), "hpi": a.get("hpi"), "hei": a.get("hei"), "cd": a.get("cd")})
            except Exception:
                pass
        if not rows:
            return {"dataset_id": dataset_id, "series": []}
        df = pd.DataFrame(rows)
        g = df.groupby("date", as_index=False).mean(numeric_only=True)
        return {"dataset_id": dataset_id, "series": g.to_dict(orient="records")}