from __future__ import annotations

import re
from typing import Any

import pandas as pd


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


def _normalise_season(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"[^a-z]", "", str(value).strip().lower())


def _season_anchor(season: Any):
    return SEASON_DATE_ANCHORS.get(_normalise_season(season))


def fill_missing_dates_from_season(
    df: pd.DataFrame,
    reference_year: int | None = None,
) -> pd.DataFrame:
    """Infer representative dates only for missing/unparseable dates."""
    out = df.copy()

    if "date" not in out.columns:
        out["date"] = pd.NaT

    parsed = pd.to_datetime(out["date"], errors="coerce", utc=True)

    out["date_inferred"] = (
        out.get("date_inferred", False)
        if "date_inferred" in out.columns
        else False
    )
    out["date_inferred"] = out["date_inferred"].fillna(False).astype(bool)

    out["date_inference_source"] = (
        out.get("date_inference_source", "")
        if "date_inference_source" in out.columns
        else ""
    )
    out["date_inference_source"] = out["date_inference_source"].fillna("").astype(str)

    if "season" not in out.columns:
        return out

    if reference_year is None:
        years = parsed.dropna().dt.year
        reference_year = int(years.median()) if len(years) else pd.Timestamp.now(tz="UTC").year

    for idx in out.index:
        if pd.notna(parsed.loc[idx]):
            continue

        anchor = _season_anchor(out.at[idx, "season"])
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
            continue

        out.at[idx, "date"] = inferred
        out.at[idx, "date_inferred"] = True
        out.at[idx, "date_inference_source"] = f"season:{str(out.at[idx, 'season']).strip()}"

    out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    return out


def temporal_series(records, dataset_id):
    rows = []
    for record in records:
        date = pd.to_datetime(record.get("date"), errors="coerce")
        if pd.isna(date):
            continue
        analysis = record.get("analysis", {})
        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "season": record.get("season"),
            "date_inferred": bool(record.get("date_inferred", False)),
            "hpi": analysis.get("hpi"),
            "hei": analysis.get("hei"),
            "cd": analysis.get("cd"),
        })

    if not rows:
        return {"dataset_id": dataset_id, "series": []}

    df = pd.DataFrame(rows)
    grouped = df.groupby("date", as_index=False).mean(numeric_only=True)
    return {"dataset_id": dataset_id, "series": grouped.to_dict(orient="records")}
