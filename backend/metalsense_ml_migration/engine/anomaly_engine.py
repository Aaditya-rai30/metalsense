from __future__ import annotations

import math
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

METALS = ["Pb", "Cd", "As", "Cr", "Hg", "Ni"]

def anomaly_scores(records):
    rows, ids = [], []
    for r in records:
        vals = []
        ok = True
        for m in METALS:
            try:
                v = float(r.get(m))
                if not math.isfinite(v):
                    ok = False
                    break
                vals.append(v)
            except Exception:
                ok = False
                break
        if ok:
            rows.append(vals)
            ids.append(r.get("sample_id"))
    if len(rows) < 8:
        return {}
    x = StandardScaler().fit_transform(np.asarray(rows))
    model = IsolationForest(n_estimators=300, contamination="auto", random_state=42)
    model.fit(x)
    return {str(i): float(s) for i, s in zip(ids, model.decision_function(x))}
