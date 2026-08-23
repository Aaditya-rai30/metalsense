from __future__ import annotations

import math
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN


class SpatialEngine:
    def _valid_points(self, records):
        out = []
        for record in records:
            try:
                lat = float(record["latitude"])
                lon = float(record["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    out.append(record)
            except (KeyError, TypeError, ValueError):
                pass
        return out

    @staticmethod
    def _risk_score(record: dict[str, Any]) -> float:
        analysis = record.get("analysis", {})
        status = str(analysis.get("status", "UNKNOWN")).upper()
        status_score = {
            "SAFE": 0.0,
            "LOW": 25.0,
            "MODERATE": 50.0,
            "HIGH": 75.0,
            "CRITICAL": 100.0,
        }.get(status, 0.0)
        hpi = min(max(float(analysis.get("hpi") or 0), 0), 200) / 2
        hei = min(max(float(analysis.get("hei") or 0), 0), 20) * 5
        cd = min(max(float(analysis.get("cd") or 0), 0), 20) * 5
        return round(max(status_score, hpi * 0.50 + hei * 0.25 + cd * 0.25), 2)

    def points(self, records, dataset_id):
        points = []
        for record in self._valid_points(records):
            analysis = record.get("analysis", {})
            points.append({
                "sample_id": record.get("sample_id"),
                "latitude": float(record["latitude"]),
                "longitude": float(record["longitude"]),
                "country": record.get("country", "Unknown"),
                "region": record.get("region", "Unknown"),
                "area": record.get("area", "Unknown"),
                "date": record.get("date"),
                "season": record.get("season"),
                "date_inferred": bool(record.get("date_inferred", False)),
                "hpi": analysis.get("hpi"),
                "hei": analysis.get("hei"),
                "cd": analysis.get("cd"),
                "status": analysis.get("status", "UNKNOWN"),
                "highest_metal": analysis.get("highest_metal"),
                "standard": analysis.get("standard", record.get("standard")),
                "authority": record.get("authority"),
                "risk_score": self._risk_score(record),
            })
        return {"dataset_id": dataset_id, "points": points, "count": len(points)}

    def summary(self, records, dataset_id):
        pts = self._valid_points(records)
        lats = [float(x["latitude"]) for x in pts]
        lons = [float(x["longitude"]) for x in pts]
        statuses = [str(x.get("analysis", {}).get("status", "UNKNOWN")).upper() for x in pts]
        return {
            "dataset_id": dataset_id,
            "count": len(pts),
            "high_risk_count": sum(s in {"HIGH", "CRITICAL"} for s in statuses),
            "moderate_count": statuses.count("MODERATE"),
            "low_risk_count": statuses.count("LOW"),
            "safe_count": statuses.count("SAFE"),
            "center": {"latitude": float(np.mean(lats)), "longitude": float(np.mean(lons))} if pts else None,
            "bounds": {"north": max(lats), "south": min(lats), "east": max(lons), "west": min(lons)} if pts else None,
        }

    def hotspots(self, records, dataset_id, radius_km=5.0):
        pts = [p for p in self._valid_points(records) if str(p.get("analysis", {}).get("status", "UNKNOWN")).upper() in {"HIGH", "CRITICAL"}]
        if len(pts) < 3:
            return {"dataset_id": dataset_id, "radius_km": radius_km, "hotspots": [], "count": 0}
        coords = np.radians(np.array([[float(r["latitude"]), float(r["longitude"])] for r in pts]))
        labels = DBSCAN(eps=radius_km / 6371.0088, min_samples=3, metric="haversine").fit(coords).labels_
        result = []
        for label in sorted(set(labels)):
            if label < 0:
                continue
            cluster = [r for r, lab in zip(pts, labels) if lab == label]
            risk = [self._risk_score(r) for r in cluster]
            hpi = [float(r.get("analysis", {}).get("hpi")) for r in cluster if r.get("analysis", {}).get("hpi") is not None]
            result.append({
                "hotspot_id": f"H{label + 1}",
                "center": {
                    "latitude": float(np.mean([float(r["latitude"]) for r in cluster])),
                    "longitude": float(np.mean([float(r["longitude"]) for r in cluster])),
                },
                "sample_count": len(cluster),
                "samples": [str(r.get("sample_id")) for r in cluster],
                "max_risk_score": max(risk) if risk else 0,
                "average_hpi": float(np.mean(hpi)) if hpi else None,
                "radius_km": radius_km,
            })
        return {"dataset_id": dataset_id, "radius_km": radius_km, "hotspots": result, "count": len(result)}

    @staticmethod
    def haversine_km(lat1, lon1, lat2, lon2):
        radius_km = 6371.0088
        lat1r, lat2r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
        return 2 * radius_km * math.asin(math.sqrt(a))
