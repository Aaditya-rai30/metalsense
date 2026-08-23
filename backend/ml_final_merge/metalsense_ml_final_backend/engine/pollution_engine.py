from __future__ import annotations

from typing import Any

import math
import pandas as pd


# Keep the existing MetalSense METALS mapping/API.
METALS = {
    "Pb": ["pb", "lead"],
    "Cd": ["cd", "cadmium"],
    "As": ["as", "arsenic"],
    "Cr": ["cr", "chromium"],
    "Cu": ["cu", "copper"],
    "Zn": ["zn", "zinc"],
    "Ni": ["ni", "nickel"],
    "Fe": ["fe", "iron"],
    "Mn": ["mn", "manganese"],
}


def _status(hpi: float | None, hei: float, cd: float) -> str:
    """
    Final-ML status classification.

    Uses the most severe level produced by HPI, HEI or contamination degree.
    """
    h = 0 if hpi is None else float(hpi)
    e = float(hei)
    c = float(cd)

    h_level = (
        0 if h < 100
        else 1 if h < 200
        else 2 if h < 300
        else 3
    )

    e_level = (
        0 if e < 10
        else 1 if e < 20
        else 2 if e < 40
        else 3
    )

    c_level = (
        0 if c < 1
        else 1 if c < 3
        else 2 if c < 6
        else 3
    )

    level = max(
        h_level,
        e_level,
        c_level,
    )

    return (
        ["SAFE", "LOW", "MODERATE", "HIGH"][level]
        if level < 3
        else "CRITICAL"
    )


def calculate_indices(
    row: pd.Series | dict,
    metal_columns: dict[str, str],
    standards: pd.DataFrame,
) -> dict[str, Any]:
    """
    Drop-in MetalSense API using the Final ML calculation logic.

    Input contract remains:
        row
        metal_columns
        standards

    Output contract keeps the fields already expected by MetalSense:
        hpi, hei, cd, status, metals, highest_metal

    Formulae:
        Wi = 1 / Si
        Qi = 100 * Ci / Si
        HPI = sum(Wi * Qi) / sum(Wi)
        HEI = sum(Ci / Si)
        Cd = sum(max(Ci / Si - 1, 0))

    Unlike the old implementation, invalid/negative/non-finite measurements
    are ignored here because upload/data-quality validation is responsible
    for rejecting those rows before calculation.
    """
    hpi_numerator = 0.0
    hpi_denominator = 0.0

    hei = 0.0
    cd = 0.0

    results: list[dict[str, Any]] = []

    if standards is None or standards.empty:
        return {
            "hpi": None,
            "hei": 0.0,
            "cd": 0.0,
            "status": "UNKNOWN",
            "metals": [],
            "highest_metal": "Unknown",
        }

    for metal, column in metal_columns.items():
        try:
            measured = pd.to_numeric(
                row.get(column),
                errors="coerce",
            )
        except Exception:
            continue

        if pd.isna(measured):
            continue

        try:
            measured = float(measured)
        except (TypeError, ValueError):
            continue

        if not math.isfinite(measured) or measured < 0:
            continue

        aliases = METALS.get(
            metal,
            [metal],
        )

        allowed = {
            str(x).strip().lower()
            for x in aliases + [metal]
        }

        if "Symbol" not in standards.columns:
            continue

        standard_rows = standards[
            standards["Symbol"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(allowed)
        ]

        if standard_rows.empty:
            continue

        standard_row = standard_rows.iloc[0]

        standard = pd.to_numeric(
            standard_row.get("PermissibleLimit"),
            errors="coerce",
        )

        if pd.isna(standard):
            continue

        standard = float(standard)

        if not math.isfinite(standard) or standard <= 0:
            continue

        # --------------------------------------------------------
        # HPI
        # --------------------------------------------------------

        wi = 1.0 / standard

        qi = (
            measured / standard
        ) * 100.0

        hpi_numerator += wi * qi
        hpi_denominator += wi

        # --------------------------------------------------------
        # HEI
        # --------------------------------------------------------

        ratio = measured / standard

        hei_value = ratio
        hei += hei_value

        # --------------------------------------------------------
        # FINAL-ML CONTAMINATION DEGREE
        # --------------------------------------------------------

        cd += max(
            ratio - 1.0,
            0.0,
        )

        results.append(
            {
                "metal": metal,
                "measured": measured,
                "standard": standard,
                "unit": str(
                    standard_row.get(
                        "Unit",
                        "mg/L",
                    )
                ),
                "Qi": round(qi, 4),
                "HEI": round(
                    hei_value,
                    4,
                ),
                "Cf": round(
                    ratio,
                    4,
                ),
                "ratio": round(
                    ratio,
                    4,
                ),
                "exceedance": round(
                    max(
                        ratio - 1.0,
                        0.0,
                    ) * 100.0,
                    2,
                ),
                "status": (
                    "HIGH"
                    if ratio > 1
                    else "SAFE"
                ),
            }
        )

    if hpi_denominator > 0:
        hpi = (
            hpi_numerator
            / hpi_denominator
        )
    else:
        hpi = None

    if not results:
        status = "UNKNOWN"
        highest_metal = "Unknown"
    else:
        highest = max(
            results,
            key=lambda x: x["ratio"],
        )

        highest_metal = highest["metal"]

        if hpi is None:
            status = "UNKNOWN"
        else:
            status = _status(
                hpi,
                hei,
                cd,
            )

    return {
        "hpi": (
            round(hpi, 2)
            if hpi is not None
            else None
        ),
        "hei": round(
            hei,
            2,
        ),
        "cd": round(
            cd,
            2,
        ),
        "status": status,
        "metals": results,
        "highest_metal": highest_metal,
    }
