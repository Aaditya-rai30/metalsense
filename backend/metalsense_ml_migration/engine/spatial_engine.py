from __future__ import annotations

import numpy as np
from sklearn.cluster import DBSCAN

class SpatialEngine:
    def _valid_points(self, records):
        out = []
        for r in records:
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    out.append(r)
            except Exception:
                pass
        return out

    def points(self, records, dataset_id):
        points = []
        for r in self._valid_points(records):
            a = r.get("analysis", {})
            points.append({
                "sample_id": r.get("sample_id"),
                "latitude": float(r["latitude"]), "longitude": float(r["longitude"]),
                "country": r.get("country"), "region": r.get("region"), "area": r.get("area"),
                "water_body": r.get("water_body"), "water_type": r.get("water_type"),
                "date": r.get("date"), "hpi": a.get("hpi"), "hei": a.get("hei"), "cd": a.get("cd"),
                "status": a.get("status"), "highest_metal": a.get("highest_metal"),
                "standard": a.get("standard"), "authority": r.get("authority") or a.get("standard"),
            })
        return {"dataset_id": dataset_id, "points": points, "count": len(points)}

    def summary(self, records, dataset_id):
        pts = self._valid_points(records)
        lats = [float(x["latitude"]) for x in pts]
        lons = [float(x["longitude"]) for x in pts]
        statuses = [x.get("analysis", {}).get("status") for x in pts]
        return {
            "dataset_id": dataset_id, "count": len(pts),
            "high_risk_count": sum(s in {"HIGH", "CRITICAL"} for s in statuses),
            "moderate_count": statuses.count("MODERATE"), "low_risk_count": statuses.count("LOW"),
            "safe_count": statuses.count("LOW"),
            "center": {"latitude": float(np.mean(lats)), "longitude": float(np.mean(lons))} if pts else None,
            "bounds": {"north": max(lats), "south": min(lats), "east": max(lons), "west": min(lons)} if pts else None,
        }

    def hotspots(self, records, dataset_id, radius_km=5):
        pts = self._valid_points(records)
        if len(pts) < 3:
            return {"dataset_id": dataset_id, "radius_km": radius_km, "hotspots": [], "count": 0}
        coords = np.radians(np.array([[float(r["latitude"]), float(r["longitude"])] for r in pts]))
        eps = radius_km / 6371.0088
        labels = DBSCAN(eps=eps, min_samples=3, metric="haversine").fit(coords).labels_
        result = []
        for label in sorted(set(labels)):
            if label < 0:
                continue
            cluster = [r for r, lab in zip(pts, labels) if lab == label]
            lat = float(np.mean([float(r["latitude"]) for r in cluster]))
            lon = float(np.mean([float(r["longitude"]) for r in cluster]))
            risks = [float(r.get("analysis", {}).get("hpi") or 0) for r in cluster]
            result.append({
                "hotspot_id": f"H{label + 1}", "center": {"latitude": lat, "longitude": lon},
                "sample_count": len(cluster), "samples": [str(r.get("sample_id")) for r in cluster],
                "max_risk_score": max(risks) if risks else 0,
                "average_hpi": float(np.mean(risks)) if risks else None, "radius_km": radius_km,
            })
        return {"dataset_id": dataset_id, "radius_km": radius_km, "hotspots": result, "count": len(result)}


