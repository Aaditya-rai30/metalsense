from __future__ import annotations

import numpy as np

class ExplainabilityEngine:
    def __init__(self, registry):
        self.registry = registry

    def explain_sample(self, row):
        a = row.get("analysis", {})
        metals = a.get("metals", [])
        contributing = [m for m in metals if m["ratio"] > 0]
        exceeded = [m for m in metals if m["exceeds"]]
        return {
            "sample_id": row.get("sample_id"),
            "status": a.get("status"),
            "standard": a.get("standard"),
            "calculation_standard": a.get("calculation_standard"),
            "reason": a.get("standard_reason"),
            "indices": {"HPI": a.get("hpi"), "HEI": a.get("hei"), "Cd": a.get("cd")},
            "all_metals_considered": contributing,
            "exceeding_metals": exceeded,
            "decision_factors": [
                {
                    "metal": m["metal"],
                    "measured": m["measured"],
                    "limit": m["limit"],
                    "ratio": m["ratio"],
                    "exceedance": m["exceedance"],
                    "impact": "exceeds reference limit" if m["exceeds"] else "within reference limit",
                } for m in contributing
            ],
            "explanation": self._text(a, contributing, exceeded),
        }

    def _text(self, a, metals, exceeded):
        if not metals:
            return "No metal had a valid numerical reference limit, so no numerical pollution decision was made."
        lead = sorted(metals, key=lambda x: x["ratio"], reverse=True)
        parts = [f"The sample is classified {a.get('status')} using {a.get('calculation_standard')}."]
        parts.append("All measured metals with valid reference limits were included in the decision.")
        if exceeded:
            parts.append("The following metals exceed their selected reference limits: " + ", ".join(m["metal"] for m in exceeded) + ".")
        parts.append("The strongest metal-level contribution by measured-to-limit ratio is " + lead[0]["metal"] + ".")
        return " ".join(parts)

    def report(self, records, dataset, summary):
        metal_totals = {}
        for r in records:
            for m in r.get("analysis", {}).get("metals", []):
                metal_totals.setdefault(m["metal"], []).append(m["measured"])
        leading = max(metal_totals, key=lambda m: np.mean(metal_totals[m])) if metal_totals else None
        return {
            "dataset_id": dataset["dataset_id"],
            "filename": dataset["filename"],
            "metadata": {k: dataset.get(k) for k in ["data_source", "laboratory_organization", "report_id", "analytical_method", "detection_limit"]},
            "summary": summary,
            "leading_metal": leading,
            "decision_support": [
                {
                    "title": f"Prioritize {summary['high_samples']} high-risk site(s)" if summary["high_samples"] else "No high-risk sites detected",
                    "text": "Re-sampling and source investigation should be prioritized for samples classified HIGH or CRITICAL." if summary["high_samples"] else "No HIGH or CRITICAL sample was produced by the deterministic analysis.",
                    "severity": "HIGH" if summary["high_samples"] else "LOW",
                },
                {
                    "title": f"{leading} leads aggregate concentration" if leading else "No leading metal available",
                    "text": "Use the complete metal profile for source investigation; the leading metal is not treated as the only decision variable.",
                    "severity": "MODERATE",
                },
                {
                    "title": "Review data quality before decisions",
                    "text": "Statistical outliers are retained as warnings because an extreme environmental measurement can be a real pollution event.",
                    "severity": "WARNING",
                },
            ],
        }
