from typing import Any

import pandas as pd


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


def calculate_indices(
    row: pd.Series | dict,
    metal_columns: dict[str, str],
    standards: pd.DataFrame,
) -> dict[str, Any]:

    hpi_numerator = 0.0
    hpi_denominator = 0.0

    HEI = 0.0
    CD = 0.0

    results = []

    for metal, column in metal_columns.items():

        measured = pd.to_numeric(
            row.get(column),
            errors="coerce",
        )

        if pd.isna(measured):
            continue

        if measured < 0:
            continue

        aliases = METALS.get(
            metal,
            [metal],
        )

        allowed = {
            str(x).strip().lower()
            for x in aliases + [metal]
        }

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
            standard_row["PermissibleLimit"],
            errors="coerce",
        )

        if pd.isna(standard) or standard <= 0:
            continue

        # ======================================
        # HPI
        # ======================================

        Wi = 1 / float(standard)

        Qi = (
            float(measured)
            / float(standard)
        ) * 100

        hpi_numerator += Wi * Qi
        hpi_denominator += Wi

        # ======================================
        # HEI
        # ======================================

        HEI_value = (
            float(measured)
            / float(standard)
        )

        HEI += HEI_value

        # ======================================
        # CD
        # ======================================

        Cf = (
            float(measured)
            / float(standard)
        )

        CD += Cf

        results.append(
            {
                "metal": metal,
                "measured": float(measured),
                "standard": float(standard),
                "unit": str(
                    standard_row["Unit"]
                ),
                "Qi": round(Qi, 4),
                "HEI": round(HEI_value, 4),
                "Cf": round(Cf, 4),
                "ratio": round(Cf, 4),
                "exceedance": round(
                    max(0, Cf - 1) * 100,
                    2,
                ),
                "status": (
                    "HIGH"
                    if Cf > 1
                    else "SAFE"
                ),
            }
        )

    # ==========================================
    # FINAL HPI
    # ==========================================

    if hpi_denominator > 0:
        HPI = (
            hpi_numerator
            / hpi_denominator
        )
    else:
        HPI = None

    if not results:
        status = "UNKNOWN"
        highest_metal = "Unknown"
    else:
        highest = max(
            results,
            key=lambda x: x["ratio"],
        )

        highest_metal = highest["metal"]

        if HPI is None:
            status = "UNKNOWN"
        elif HPI >= 100:
            status = "HIGH"
        elif HPI >= 50:
            status = "MODERATE"
        elif HPI >= 25:
            status = "LOW"
        else:
            status = "SAFE"

    return {
        "hpi": (
            round(HPI, 2)
            if HPI is not None
            else None
        ),
        "hei": round(HEI, 2),
        "cd": round(CD, 2),
        "status": status,
        "metals": results,
        "highest_metal": highest_metal,
    }
