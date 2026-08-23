from __future__ import annotations

import math
from typing import Any

import numpy as np

from engine.standards_registry import METALS, StandardsRegistry

class PollutionEngine:
    def __init__(self, registry: StandardsRegistry):
        self.registry = registry

    @staticmethod
    def status(hpi, hei, cd):
        h = 0 if hpi is None else float(hpi)
        e = 0 if hei is None else float(hei)
        c = 0 if cd is None else float(cd)
        h_level = 0 if h < 100 else 1 if h < 200 else 2 if h < 300 else 3
        e_level = 0 if e < 10 else 1 if e < 20 else 2 if e < 40 else 3
        c_level = 0 if c < 1 else 1 if c < 3 else 2 if c < 6 else 3
        level = max(h_level, e_level, c_level)
        return ["SAFE", "LOW", "MODERATE", "HIGH"][level] if level < 3 else "CRITICAL"

    def sample(self, row):
        metals = []
        for m in METALS:
            if m in row:
                try:
                    v = float(row[m])
                    if math.isfinite(v) and v >= 0:
                        metals.append((m, v))
                except Exception:
                    pass
        country = row.get("country", "")
        water = row.get("water_type", "drinking water") or "drinking water"
        choice = self.registry.select(country, water, [m for m, _ in metals])
        limits = self.registry.get_limits(choice["calculation_standard"], water)
        values = [(m, v, limits.get(m)) for m, v in metals if limits.get(m) is not None and limits.get(m) > 0]
        if not values:
            return {**row, "analysis": {"status": "LOW", "hpi": None, "hei": None, "cd": None, "standard": choice["standard"], "calculation_standard": choice["calculation_standard"], "standard_level": choice["level"], "metals": []}}

        n = len(values)
        wi = {m: 1 / s for m, _, s in values}
        wsum = sum(wi.values())
        qi = {m: 100 * v / s for m, v, s in values}
        hpi = sum(wi[m] * qi[m] for m, _, _ in values) / wsum if wsum else None
        hei = sum(v / s for _, v, s in values)
        cd = sum(max(v / s - 1, 0) for _, v, s in values)
        metal_results = []
        for m, v, s in values:
            ratio = v / s
            metal_results.append({
                "metal": m, "measured": v, "limit": s, "ratio": ratio,
                "exceedance": max(ratio - 1, 0),
                "exceeds": ratio > 1,
            })
        metal_results.sort(key=lambda x: x["ratio"], reverse=True)
        status = self.status(hpi, hei, cd)
        analysis = {
            "hpi": round(hpi, 6), "hei": round(hei, 6), "cd": round(cd, 6),
            "status": status, "standard": choice["standard"],
            "calculation_standard": choice["calculation_standard"],
            "standard_level": choice["level"], "standard_reason": choice["reason"],
            "highest_metal": metal_results[0]["metal"] if metal_results else None,
            "metals": metal_results,
        }
        return {**row, "analysis": analysis}

    def analyze_records(self, records, default_country="", default_water_type="drinking water"):
        out = []
        for row in records:
            r = dict(row)
            r.setdefault("country", default_country)
            r.setdefault("water_type", default_water_type)
            out.append(self.sample(r))
        hpis = [r["analysis"]["hpi"] for r in out if r["analysis"].get("hpi") is not None]
        heis = [r["analysis"]["hei"] for r in out if r["analysis"].get("hei") is not None]
        cds = [r["analysis"]["cd"] for r in out if r["analysis"].get("cd") is not None]
        statuses = [r["analysis"]["status"] for r in out]
        summary = {
            "record_count": len(out),
            "average_hpi": float(np.mean(hpis)) if hpis else None,
            "average_hei": float(np.mean(heis)) if heis else None,
            "average_cd": float(np.mean(cds)) if cds else None,
            "max_hpi": float(np.max(hpis)) if hpis else None,
            "min_hpi": float(np.min(hpis)) if hpis else None,
            "overall_status": max(set(statuses), key=lambda s: ["LOW", "MODERATE", "HIGH", "CRITICAL"].index(s)) if statuses else "LOW",
            "high_samples": sum(s in {"HIGH", "CRITICAL"} for s in statuses),
            "moderate_samples": statuses.count("MODERATE"),
            "low_samples": statuses.count("LOW"),
            "safe_samples": statuses.count("LOW"),
        }
        metal_stats = {}
        for r in out:
            for m in r["analysis"].get("metals", []):
                metal_stats.setdefault(m["metal"], []).append(m["measured"])
        metals = [{
            "metal": m, "sample_count": len(v), "average_measured": float(np.mean(v)),
            "maximum_measured": float(np.max(v)), "average_ratio": float(np.mean([
                x["ratio"] for r in out for x in r["analysis"].get("metals", []) if x["metal"] == m
            ])), "maximum_exceedance": float(np.max([
                x["exceedance"] for r in out for x in r["analysis"].get("metals", []) if x["metal"] == m
            ])), "high_samples": sum(
                any(x["metal"] == m and x["exceeds"] for x in r["analysis"].get("metals", [])) for r in out
            )
        } for m, v in metal_stats.items()]
        return {"records": out, "summary": summary, "metals": metals, "dataset": {"record_count": len(out), "standards_used": sorted(set(r["analysis"]["calculation_standard"] for r in out))}}

