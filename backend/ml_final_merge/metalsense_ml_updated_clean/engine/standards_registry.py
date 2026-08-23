from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


METALS = ["Pb", "Cd", "As", "Cr", "Hg", "Ni", "Cu", "Zn", "Fe", "Mn"]


@dataclass
class Standard:
    id: str
    name: str
    country: str = ""
    agency: str = ""
    water_types: list[str] = field(default_factory=list)
    metals: list[str] = field(default_factory=list)
    limits: dict[str, dict[str, float]] = field(default_factory=dict)
    source: str = ""
    version: str = ""


class StandardsRegistry:
    """Metadata registry for Final-ML explainability/RAG.

    Numerical country-specific limits remain sourced from MetalSense's
    existing `standard.csv` through `services.standards_service`.
    This avoids replacing the live registry with a second competing source.
    """

    def __init__(self, standards: dict[str, Standard] | None = None):
        self.db = standards or {
            "BIS": Standard(
                "BIS",
                "BIS drinking-water/discharge registry",
                country="India",
                agency="BIS/CPCB",
                water_types=["drinking water", "groundwater", "freshwater", "industrial wastewater", "agricultural water"],
                metals=METALS.copy(),
                version="MetalSense standard.csv",
            ),
            "WHO": Standard(
                "WHO",
                "WHO Guidelines for Drinking-water Quality",
                country="WHO Default",
                agency="WHO",
                water_types=["drinking water", "groundwater", "marine water", "coastal water"],
                metals=METALS.copy(),
                version="MetalSense standard.csv",
            ),
        }

    def list_metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "id": s.id,
                "name": s.name,
                "country": s.country,
                "agency": s.agency,
                "water_types": s.water_types,
                "metals": s.metals,
                "source": s.source,
                "version": s.version,
                "has_numeric_limits": bool(s.limits),
            }
            for s in self.db.values()
        ]

    def compare(self, water_type: str, metal: str) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for sid, standard in self.db.items():
            result[sid] = standard.limits.get(water_type, {}).get(metal)
        return result
