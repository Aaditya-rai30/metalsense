from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# The final ML design focuses on these six metals for multivariate anomaly scoring.
METALS = ["Pb", "Cd", "As", "Cr", "Hg", "Ni"]


def _measurement_map(record: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    analysis = record.get("analysis", {})
    for item in analysis.get("metals", []):
        if not isinstance(item, dict):
            continue
        metal = str(item.get("metal", "")).strip()
        raw = item.get("measured", item.get("value"))
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if metal and math.isfinite(value) and value >= 0:
            values[metal] = value
    for metal in METALS:
        if metal not in values and metal in record:
            try:
                value = float(record[metal])
                if math.isfinite(value) and value >= 0:
                    values[metal] = value
            except (TypeError, ValueError):
                pass
    return values


def anomaly_scores(records: list[dict[str, Any]]) -> dict[str, float]:
    rows: list[list[float]] = []
    ids: list[str] = []

    for record in records:
        values = _measurement_map(record)
        # Missing metals are represented as 0 only when the record otherwise
        # contains at least one supported measurement.
        if not values:
            continue
        rows.append([values.get(m, 0.0) for m in METALS])
        ids.append(str(record.get("sample_id", "")))

    if len(rows) < 8:
        return {}

    x = StandardScaler().fit_transform(np.asarray(rows, dtype=float))
    model = IsolationForest(
        n_estimators=300,
        contamination="auto",
        random_state=42,
    )
    model.fit(x)
    return {
        sample_id: float(score)
        for sample_id, score in zip(ids, model.decision_function(x))
    }


def annotate_records(records: list[dict[str, Any]]) -> dict[str, float]:
    scores = anomaly_scores(records)
    for record in records:
        sid = str(record.get("sample_id", ""))
        if sid in scores:
            record["anomaly_score"] = round(scores[sid], 6)
    return scores
