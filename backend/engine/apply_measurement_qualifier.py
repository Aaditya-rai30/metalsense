from pathlib import Path
import re

BACKEND = Path.cwd()
ENGINE = BACKEND / "engine"
DATASET = BACKEND / "services" / "dataset_service.py"

ENGINE.mkdir(exist_ok=True)

MEASUREMENT_CODE = r'''"""
MetalSense laboratory measurement qualifier handling.

Preserves raw laboratory conventions such as:
    ND       -> Not Detected
    BDL      -> Below Detection Limit
    <0.005   -> Less than 0.005
    >0.05    -> Greater than 0.05

The original value is never discarded.
"""

from __future__ import annotations

import math
import re
from typing import Any


ND_ALIASES = {
    "nd",
    "n/d",
    "not detected",
    "non detect",
    "non-detect",
    "non detected",
}

BDL_ALIASES = {
    "bdl",
    "below detection limit",
    "below detectable limit",
    "below reporting limit",
    "below quantification limit",
    "bql",
}

NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _base(raw: str, qualifier: str, number, status: str, qualified: bool, recognized: bool):
    return {
        "raw_value": raw or None,
        "qualifier": qualifier,
        "numeric_value": number,
        "calculation_value": number,
        "calculation_status": status if number is not None else "NOT_CALCULATED",
        "is_qualified": qualified,
        "recognized": recognized,
    }


def parse_measurement(value: Any) -> dict[str, Any]:
    """Parse a laboratory concentration without converting ND/BDL to zero."""
    raw = _text(value)
    normalized = raw.lower()

    if not raw:
        return _base(raw, "MISSING", None, "NOT_CALCULATED", False, True)

    if normalized in {"na", "n/a", "null", "none", "missing", "-", "—"}:
        return _base(raw, "MISSING", None, "NOT_CALCULATED", False, True)

    if normalized.startswith("<"):
        match = NUMBER_RE.search(normalized[1:])
        if match:
            return _base(raw, "LT", float(match.group()), "UPPER_BOUND", True, True)

    if normalized.startswith(">"):
        match = NUMBER_RE.search(normalized[1:])
        if match:
            return _base(raw, "GT", float(match.group()), "LOWER_BOUND", True, True)

    if normalized in ND_ALIASES:
        return _base(raw, "ND", None, "NOT_CALCULATED", True, True)

    if normalized in BDL_ALIASES:
        return _base(raw, "BDL", None, "NOT_CALCULATED", True, True)

    # e.g. "ND <0.005" / "BDL (<0.005)"
    if any(alias in normalized for alias in ND_ALIASES):
        match = NUMBER_RE.search(normalized)
        return _base(raw, "ND", float(match.group()) if match else None, "UPPER_BOUND", True, True)

    if any(alias in normalized for alias in BDL_ALIASES):
        match = NUMBER_RE.search(normalized)
        return _base(raw, "BDL", float(match.group()) if match else None, "UPPER_BOUND", True, True)

    try:
        number = float(normalized.replace(",", ""))
        if math.isfinite(number):
            return _base(raw, "EXACT", number, "EXACT", False, True)
    except ValueError:
        pass

    return _base(raw, "INVALID", None, "NOT_CALCULATED", False, False)
'''

qualifier_path = ENGINE / "measurement_qualifier.py"
qualifier_path.write_text(MEASUREMENT_CODE)

text = DATASET.read_text()

# ------------------------------------------------------------------
# 1. Import qualifier parser.
# ------------------------------------------------------------------
if "from engine.measurement_qualifier import parse_measurement" not in text:
    anchor = "from engine.pollution_engine import calculate_indices, METALS\n"
    if anchor not in text:
        raise SystemExit("Could not locate pollution_engine import in dataset_service.py")
    text = text.replace(
        anchor,
        anchor + "from engine.measurement_qualifier import parse_measurement\n",
        1,
    )

# ------------------------------------------------------------------
# 2. Build quality rows with raw + qualifier + numeric value.
# ------------------------------------------------------------------
old = '''            value = pd.to_numeric(
                source_row[column],
                errors="coerce",
            )

            rows.append(
                {
'''
new = '''            parsed = parse_measurement(source_row[column])
            value = parsed["numeric_value"]

            rows.append(
                {
'''
if old in text:
    text = text.replace(old, new, 1)

old = '''                    "value":
                        value,

                    "unit":
                        unit,
'''
new = '''                    "value":
                        value,

                    "numeric_value":
                        parsed["numeric_value"],

                    "calculation_value":
                        parsed["calculation_value"],

                    "measurement_qualifier":
                        parsed["qualifier"],

                    "raw_value":
                        parsed["raw_value"],

                    "unit":
                        unit,
'''
if old in text and '"measurement_qualifier":' not in text:
    text = text.replace(old, new, 1)

# ------------------------------------------------------------------
# 3. Replace the raw pollution-calculation block.
# ------------------------------------------------------------------
start_marker = '''        # ----------------------------------------------------
        # Pollution calculation
        # ----------------------------------------------------
'''
sample_marker = '''        # ----------------------------------------------------
        # Sample ID
        # ----------------------------------------------------
'''
if start_marker in text and sample_marker in text:
    start = text.index(start_marker)
    end = text.index(sample_marker, start)

    # Only patch if the block is still the old calculation block.
    current_block = text[start:end]
    if 'Measurement qualifiers + calculation row' not in current_block:
        replacement = '''        # ----------------------------------------------------
        # Measurement qualifiers + calculation row
        # ----------------------------------------------------
        calculation_row = source_row.copy()
        measurements = []
        qualified_measurements = []
        invalid_measurements = []

        for metal, column in metal_columns.items():
            parsed = parse_measurement(source_row[column])

            measurements.append({
                "metal": metal,
                "raw_value": parsed["raw_value"],
                "qualifier": parsed["qualifier"],
                "numeric_value": parsed["numeric_value"],
                "calculation_value": parsed["calculation_value"],
                "calculation_status": parsed["calculation_status"],
                "unit": (
                    str(source_row[unit_col]).strip()
                    if unit_col and pd.notna(source_row[unit_col])
                    else "mg/L"
                ),
            })

            if not parsed["recognized"]:
                invalid_measurements.append({
                    "metal": metal,
                    "raw_value": parsed["raw_value"],
                })
                calculation_row[column] = float("nan")
                continue

            if parsed["is_qualified"]:
                qualified_measurements.append({
                    "metal": metal,
                    "raw_value": parsed["raw_value"],
                    "qualifier": parsed["qualifier"],
                    "numeric_value": parsed["numeric_value"],
                    "calculation_status": parsed["calculation_status"],
                })

            calculation_row[column] = (
                parsed["calculation_value"]
                if parsed["calculation_value"] is not None
                else float("nan")
            )

            if parsed["qualifier"] == "MISSING":
                quality_missing += 1

        if invalid_measurements:
            errors.append({
                "row": row_number,
                "column": "metal measurement",
                "problem": "Unrecognized laboratory measurement value.",
                "measurements": invalid_measurements,
            })
            continue

        # ----------------------------------------------------
        # Pollution calculation
        # ----------------------------------------------------
        analysis = calculate_indices(
            row=calculation_row,
            metal_columns=metal_columns,
            standards=standards,
        )

        existing_metals = analysis.get("metals", [])
        by_metal = {
            str(item.get("metal", "")).strip().lower(): item
            for item in existing_metals
        }

        for measurement in measurements:
            item = by_metal.get(measurement["metal"].lower())

            if item is None:
                existing_metals.append({
                    "metal": measurement["metal"],
                    "measured": None,
                    "raw_value": measurement["raw_value"],
                    "qualifier": measurement["qualifier"],
                    "numeric_value": measurement["numeric_value"],
                    "calculation_value": measurement["calculation_value"],
                    "calculation_status": measurement["calculation_status"],
                    "status": "NOT_CALCULATED",
                })
            else:
                item.update({
                    "raw_value": measurement["raw_value"],
                    "qualifier": measurement["qualifier"],
                    "numeric_value": measurement["numeric_value"],
                    "calculation_value": measurement["calculation_value"],
                    "calculation_status": measurement["calculation_status"],
                })

        analysis["metals"] = existing_metals
        analysis["measurements"] = measurements
        analysis["qualified_measurements"] = qualified_measurements

        if qualified_measurements:
            analysis["calculation_note"] = (
                "Qualified laboratory values were preserved. Numeric bounds "
                "were used only where a numeric bound was present; ND/BDL "
                "without a numeric bound were excluded from index calculation."
            )

'''
        text = text[:start] + replacement + text[end:]

# ------------------------------------------------------------------
# 4. Make quality validation ignore ND/BDL rows that have no numeric bound.
# ------------------------------------------------------------------
anchor = '''    try:

        quality_engine = (
'''
insert = '''    # Recognized ND/BDL values without a numeric detection/reporting
    # limit are preserved but excluded from numeric-only quality checks.
    # They are not converted to zero and are not counted as ordinary missing
    # measurements.
    if "measurement_qualifier" in quality_df.columns:
        qualifier_mask = quality_df["measurement_qualifier"].isin({"ND", "BDL"})
        no_numeric_bound = quality_df["numeric_value"].isna()
        excluded_qualifier_rows = quality_df.loc[
            qualifier_mask & no_numeric_bound
        ].copy()
        numeric_quality_df = quality_df.loc[
            ~(qualifier_mask & no_numeric_bound)
        ].copy()
    else:
        excluded_qualifier_rows = pd.DataFrame()
        numeric_quality_df = quality_df

    qualifier_summary = {}
    if "measurement_qualifier" in quality_df.columns:
        qualifier_summary = {
            str(key): int(value)
            for key, value in quality_df["measurement_qualifier"].value_counts(dropna=False).items()
        }

    try:

        quality_engine = (
'''
if anchor in text and 'numeric_quality_df' not in text:
    text=text.replace(anchor,insert,1)
    text=text.replace('''                quality_df,
                use_ml_outliers=True,
''','''                numeric_quality_df,
                use_ml_outliers=True,
''',1)
    # Add qualifier metadata after quality_report creation.
    old_report='''        quality_report = (
            quality_engine.run()
        )
'''
    new_report='''        quality_report = (
            quality_engine.run()
        )

        quality_report["measurement_qualifiers"] = qualifier_summary
        quality_report["qualified_rows_excluded_from_numeric_checks"] = int(
            len(excluded_qualifier_rows)
        )
        quality_report["numeric_validation_records"] = int(
            len(numeric_quality_df)
        )
'''
    if old_report in text:
        text=text.replace(old_report,new_report,1)

# ------------------------------------------------------------------
# 5. Do not count ND/BDL as ordinary missing values in the top-level score.
#    Replace the old raw pd.isna loop if it still exists after the new block.
# ------------------------------------------------------------------
old_loop = '''        # ----------------------------------------------------
        # Quality missing count
        # ----------------------------------------------------

        for column in (
            metal_columns.values()
        ):

            if pd.isna(
                source_row[
                    column
                ]
            ):

                quality_missing += 1

'''
if old_loop in text:
    text=text.replace(old_loop,'',1)

DATASET.write_text(text)
print(f"Updated {DATASET}")
print(f"Created {qualifier_path}")
