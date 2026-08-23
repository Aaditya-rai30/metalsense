from __future__ import annotations

from typing import Any

import pandas as pd

from engine.anomaly_engine import anomaly_scores
from engine.data_quality_engine import validate_dataframe
from engine.explainability_engine import ExplainabilityEngine
from engine.pollution_engine import PollutionEngine
from engine.rag_engine import RAGEngine
from engine.spatial_engine import SpatialEngine
from engine.standards_registry import StandardsRegistry
from engine.temporal_engine import fill_missing_dates_from_season, temporal_series


class MetalSenseMLEngine:
    """Unified orchestration layer extracted from final_ml.py."""

    def __init__(self, standards_dir: str = "standards", rag_dir: str = "rag_docs"):
        self.registry = StandardsRegistry(standards_dir)
        self.pollution = PollutionEngine(self.registry)
        self.explainability = ExplainabilityEngine(self.registry)
        self.spatial = SpatialEngine()
        self.rag = RAGEngine(rag_dir=rag_dir, standards_dir=standards_dir)

    def run_dataframe(self, df: pd.DataFrame, dataset_id: str = "") -> dict[str, Any]:
        work = fill_missing_dates_from_season(df)
        quality = validate_dataframe(work)
        from engine.data_quality_engine import DataValidator
        clean = DataValidator().clean(work, quality)

        records = clean.to_dict(orient="records")
        analyzed = self.pollution.analyze_records(records)
        rows = analyzed["records"]

        anomalies = anomaly_scores(rows)
        for row in rows:
            sid = str(row.get("sample_id"))
            if sid in anomalies:
                row["anomaly_score"] = anomalies[sid]

        explanations = [self.explainability.explain_sample(r) for r in rows]
        spatial_points = self.spatial.points(rows, dataset_id)
        spatial_summary = self.spatial.summary(rows, dataset_id)
        hotspots = self.spatial.hotspots(rows, dataset_id)
        temporal = temporal_series(rows, dataset_id)
        report = self.explainability.report(rows, {"dataset_id": dataset_id, "filename": "", "data_source": "", "laboratory_organization": "", "report_id": "", "analytical_method": "", "detection_limit": ""}, analyzed["summary"])

        return {
            "records": rows,
            "summary": analyzed["summary"],
            "metals": analyzed["metals"],
            "quality": quality.as_dict(),
            "explanations": explanations,
            "report": report,
            "spatial": spatial_points,
            "spatial_summary": spatial_summary,
            "hotspots": hotspots,
            "temporal": temporal,
            "anomaly_scores": anomalies,
            "rag_sources": self.rag.sources(),
        }
