from __future__ import annotations

from typing import Any

from engine.anomaly_engine import annotate_records
from engine.explainability_engine import ExplainabilityEngine
from engine.rag_engine import RAGEngine
from engine.spatial_engine import SpatialEngine
from engine.temporal_engine import temporal_series


class MetalSenseMLEngine:
    """Post-calculation ML orchestration layer.

    The live dataset service remains responsible for secure ingestion,
    standards selection and HPI/HEI/Cd calculation. This layer adds the
    Final-ML analytical capabilities without changing the existing API
    contract.
    """

    def __init__(self, rag_dir="rag_docs", standards_dir="standards"):
        self.explainability = ExplainabilityEngine()
        self.spatial = SpatialEngine()
        self.rag = RAGEngine(rag_dir=rag_dir, standards_dir=standards_dir)

    def enrich_records(self, records: list[dict[str, Any]], dataset: dict[str, Any]) -> dict[str, Any]:
        anomaly = annotate_records(records)
        explanations = [self.explainability.explain_sample(r) for r in records]
        summary = _summary(records)
        report = self.explainability.report(records, dataset, summary)
        dataset_id = str(dataset.get("dataset_id", ""))
        return {
            "records": records,
            "anomaly_scores": anomaly,
            "explanations": explanations,
            "spatial": self.spatial.points(records, dataset_id),
            "spatial_summary": self.spatial.summary(records, dataset_id),
            "hotspots": self.spatial.hotspots(records, dataset_id),
            "temporal": temporal_series(records, dataset_id),
            "report": report,
            "rag_sources": self.rag.sources(),
        }

    def rag_answer(self, question: str, context: dict | None = None, top_k: int = 6):
        return self.rag.answer(question, context=context, top_k=top_k)


def _summary(records):
    hpi = [r.get("analysis", {}).get("hpi") for r in records if r.get("analysis", {}).get("hpi") is not None]
    hei = [r.get("analysis", {}).get("hei") for r in records if r.get("analysis", {}).get("hei") is not None]
    cd = [r.get("analysis", {}).get("cd") for r in records if r.get("analysis", {}).get("cd") is not None]
    statuses = [str(r.get("analysis", {}).get("status", "UNKNOWN")).upper() for r in records]
    order = {"UNKNOWN": 0, "SAFE": 1, "LOW": 2, "MODERATE": 3, "HIGH": 4, "CRITICAL": 5}
    return {
        "record_count": len(records),
        "average_hpi": sum(hpi) / len(hpi) if hpi else None,
        "average_hei": sum(hei) / len(hei) if hei else None,
        "average_cd": sum(cd) / len(cd) if cd else None,
        "overall_status": max(statuses, key=lambda s: order.get(s, 0)) if statuses else "UNKNOWN",
        "high_samples": sum(s in {"HIGH", "CRITICAL"} for s in statuses),
    }
