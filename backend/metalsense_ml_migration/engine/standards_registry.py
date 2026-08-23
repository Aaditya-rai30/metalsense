from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import pandas as pd

METALS = ["Pb", "Cd", "As", "Cr", "Hg", "Ni"]

class Standard:
    id: str
    name: str
    country: str = ""
    agency: str = ""
    water_types: List[str] = field(default_factory=list)
    metals: List[str] = field(default_factory=list)
    limits: Dict[str, Dict[str, float]] = field(default_factory=dict)
    source: str = ""
    version: str = ""

class StandardsRegistry:
    def __init__(self, directory="standards"):
        self.db = {
            c: Standard(c, n, country, agency, water_types, METALS.copy(), source=n)
            for c, n, country, agency, water_types in BUILTIN
        }
        self._builtin_limits()
        self._load_csvs(Path(directory))

    def _builtin_limits(self):
        self.db["BIS_CPCB"].limits = {
            "drinking water": {"Pb": .01, "Cd": .003, "As": .01, "Cr": .05, "Hg": .001, "Ni": .02},
            "groundwater": {"Pb": .01, "Cd": .003, "As": .01, "Cr": .05, "Hg": .001, "Ni": .02},
            "freshwater": {"Pb": .02, "Cd": .005, "As": .02, "Cr": .10, "Hg": .002, "Ni": .05},
            "industrial wastewater": {"Pb": .1, "Cd": .05, "As": .2, "Cr": .1, "Hg": .01, "Ni": .3},
            "agricultural water": {"Pb": .1, "Cd": .01, "As": .1, "Cr": .10, "Hg": .01, "Ni": .2},
        }
        self.db["BIS_CPCB"].version = "2012 / 2023"
        self.db["WHO"].limits = {
            "drinking water": {"Pb": .01, "Cd": .003, "As": .01, "Cr": .05, "Hg": .006, "Ni": .07},
            "groundwater": {"Pb": .01, "Cd": .003, "As": .01, "Cr": .05, "Hg": .006, "Ni": .07},
            "marine water": {"Pb": .05, "Cd": .01, "As": .05, "Cr": .15, "Hg": .01, "Ni": .10},
            "coastal water": {"Pb": .05, "Cd": .01, "As": .05, "Cr": .15, "Hg": .01, "Ni": .10},
        }
        self.db["WHO"].version = "2022 + addenda"

    def _load_csvs(self, directory: Path):
        if not directory.exists():
            return
        for path in directory.glob("*.csv"):
            try:
                df = pd.read_csv(path)
                cols = {norm(c): c for c in df.columns}
                std_col = next((cols[k] for k in ["standard", "standardid", "authority", "framework"] if k in cols), None)
                metal_col = next((cols[k] for k in ["metal", "parameter", "analyte", "pollutant"] if k in cols), None)
                limit_col = next((cols[k] for k in ["limit", "permissiblelimit", "referencevalue", "value", "standardvalue"] if k in cols), None)
                water_col = next((cols[k] for k in ["watertype", "watercontext", "context", "scenario"] if k in cols), None)
                if not (std_col and metal_col and limit_col):
                    continue
                for _, r in df.iterrows():
                    sid = str(r[std_col]).strip().upper()
                    metal = str(r[metal_col]).strip()
                    try:
                        value = float(r[limit_col])
                    except Exception:
                        continue
                    context = str(r[water_col]).strip() if water_col else "drinking water"
                    if sid not in self.db:
                        self.db[sid] = Standard(sid, sid)
                    self.db[sid].limits.setdefault(context, {})[metal] = value
                    if metal not in self.db[sid].metals:
                        self.db[sid].metals.append(metal)
                    self.db[sid].source = str(path)
            except Exception:
                continue

    def get_limits(self, standard, water_type):
        s = self.db.get(str(standard).upper())
        if not s:
            return {}
        target = norm(water_type)
        for ctx, limits in s.limits.items():
            if norm(ctx) == target:
                return limits
        return {}

    def select(self, country, water_type, metals):
        country_key = norm(country)
        sid = COUNTRY_STANDARDS.get(country_key)
        if sid and sid in self.db:
            s = self.db[sid]
            limits = self.get_limits(sid, water_type)
            if limits and set(metals) & set(limits):
                return {"standard": sid, "name": s.name, "level": "COUNTRY", "calculation_standard": sid, "reason": "Country-specific standard matched context and supplied metal limits."}
            if sid == "BIS_CPCB" and water_type in {"industrial wastewater", "agricultural water"}:
                return {"standard": sid, "name": s.name, "level": "COUNTRY", "calculation_standard": sid, "reason": "Country-specific discharge/water standard matched the selected context."}
        candidates = []
        for sid in GLOBAL:
            if sid not in self.db:
                continue
            s = self.db[sid]
            limits = self.get_limits(sid, water_type)
            if limits and set(metals) & set(limits):
                score = len(set(metals) & set(limits)) / max(len(metals), 1)
                candidates.append((score, sid))
        if candidates:
            sid = max(candidates)[1]
            return {"standard": sid, "name": self.db[sid].name, "level": "GLOBAL", "calculation_standard": sid, "reason": "Best available global framework with numerical limits for the selected context and metals."}
        return {"standard": "WHO", "name": self.db["WHO"].name, "level": "WHO_FALLBACK", "calculation_standard": "WHO", "reason": "No suitable country-specific or global numerical standard was available; WHO was used as the generalized fallback."}

    def compare(self, water_type, metal):
        return {
            sid: self.get_limits(sid, water_type).get(metal)
            for sid in self.db
        }

    def list_metadata(self):
        return [{
            "id": s.id, "name": s.name, "country": s.country, "agency": s.agency,
            "water_types": s.water_types, "metals": s.metals, "source": s.source,
            "version": s.version, "has_numeric_limits": bool(s.limits)
        } for s in self.db.values()]
