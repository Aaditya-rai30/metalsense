from __future__ import annotations

from typing import Any


class ExplainabilityEngine:
    def explain_sample(self, row: dict[str, Any]) -> dict[str, Any]:
        analysis = row.get("analysis", {}) if isinstance(row.get("analysis"), dict) else {}
        metals = [m for m in analysis.get("metals", []) if isinstance(m, dict)]
        contributing = [m for m in metals if self._number(m.get("ratio")) is not None]
        exceeded = [m for m in contributing if self._number(m.get("ratio")) > 1]

        decision_factors = []
        for m in sorted(contributing, key=lambda x: self._number(x.get("ratio")) or 0, reverse=True):
            decision_factors.append({
                "metal": m.get("metal"),
                "measured": m.get("measured"),
                "limit": m.get("standard", m.get("limit")),
                "ratio": m.get("ratio"),
                "exceedance": m.get("exceedance"),
                "impact": "exceeds reference limit" if self._number(m.get("ratio")) > 1 else "within reference limit",
            })

        return {
            "sample_id": row.get("sample_id"),
            "status": analysis.get("status"),
            "standard": analysis.get("standard", row.get("standard")),
            "calculation_standard": analysis.get("calculation_standard"),
            "reason": analysis.get("standard_reason", row.get("standard_reason")),
            "indices": {
                "HPI": analysis.get("hpi"),
                "HEI": analysis.get("hei"),
                "Cd": analysis.get("cd"),
            },
            "all_metals_considered": contributing,
            "exceeding_metals": exceeded,
            "decision_factors": decision_factors,
            "explanation": self._text(analysis, contributing, exceeded),
        }

    @staticmethod
    def _number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _text(self, analysis, metals, exceeded):
        if not metals:
            return "No metal had a valid numerical reference limit, so no numerical pollution decision was made."
        standard = analysis.get("calculation_standard") or analysis.get("standard") or "the selected standard"
        parts = [f"The sample is classified {analysis.get('status', 'UNKNOWN')} using {standard}."]
        parts.append("All measured metals with valid reference limits were included in the decision.")
        if exceeded:
            parts.append(
                "The following metals exceed their selected reference limits: "
                + ", ".join(str(m.get("metal")) for m in exceeded) + "."
            )
        lead = max(metals, key=lambda x: self._number(x.get("ratio")) or 0)
        parts.append(
            "The strongest metal-level contribution by measured-to-limit ratio is "
            + str(lead.get("metal")) + "."
        )
        return " ".join(parts)

    def report(self, records, dataset, summary):
        metal_totals = {}
        for record in records:
            for metal in record.get("analysis", {}).get("metals", []):
                if not isinstance(metal, dict):
                    continue
                value = self._number(metal.get("measured"))
                if value is not None:
                    metal_totals.setdefault(str(metal.get("metal")), []).append(value)

        leading = (
            max(metal_totals, key=lambda m: sum(metal_totals[m]) / len(metal_totals[m]))
            if metal_totals else None
        )

        high_count = summary.get("high_samples", 0)
        return {
            "dataset_id": dataset.get("dataset_id"),
            "filename": dataset.get("filename", ""),
            "metadata": {
                k: dataset.get(k)
                for k in ["data_source", "laboratory_organization", "report_id", "analytical_method", "detection_limit"]
            },
            "summary": summary,
            "leading_metal": leading,
            "decision_support": [
                {
                    "title": f"Prioritize {high_count} high-risk site(s)" if high_count else "No high-risk sites detected",
                    "text": "Re-sampling and source investigation should be prioritized for samples classified HIGH or CRITICAL." if high_count else "No HIGH or CRITICAL sample was produced by the deterministic analysis.",
                    "severity": "HIGH" if high_count else "LOW",
                },
                {
                    "title": f"{leading} leads aggregate concentration" if leading else "No leading metal available",
                    "text": "Use the complete metal profile for source investigation; the leading metal is not treated as the only decision variable.",
                    "severity": "MODERATE",
                },
                {
                    "title": "Review data quality before decisions",
                    "text": "Statistical and ML outliers are retained as warnings because an extreme environmental measurement can be a genuine pollution event.",
                    "severity": "WARNING",
                },
            ],
        }
