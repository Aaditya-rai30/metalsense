"""
MetalSense measurement qualifier handling.

Preserves laboratory reporting conventions such as:
    ND       -> Not Detected
    BDL      -> Below Detection Limit
    <0.005   -> Less than 0.005
    >0.05    -> Greater than 0.05

The original text is always retained. Numeric values are used only when a
numeric boundary is actually present, and the calculation status records
whether the number is exact or a bound.
"""

from __future__ import annotations

import math
import re
from typing import Any


QUALIFIER_ALIASES = {
    "ND": {
        "nd",
        "n/d",
        "not detected",
        "not detected*",
        "not detected.”",
        "non detect",
        "non-detect",
        "non detected",
    },
    "BDL": {
        "bdl",
        "below detection limit",
        "below detectable limit",
        "below reporting limit",
        "below quantification limit",
        "bql",
    },
}

_RE_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def parse_measurement(value: Any) -> dict[str, Any]:
    """Parse a laboratory measurement without destroying its original form."""
    raw = _clean_text(value)

    if raw == "":
        return {
            "raw_value": None,
            "qualifier": "MISSING",
            "numeric_value": None,
            "calculation_value": None,
            "calculation_status": "NOT_CALCULATED",
            "is_qualified": False,
            "recognized": True,
        }

    normalized = raw.lower().strip()

    if normalized in {"na", "n/a", "null", "none", "missing", "not available", "-", "—"}:
        return {
            "raw_value": raw,
            "qualifier": "MISSING",
            "numeric_value": None,
            "calculation_value": None,
            "calculation_status": "NOT_CALCULATED",
            "is_qualified": False,
            "recognized": True,
        }

    # Explicit less-than / greater-than reporting.
    if normalized.startswith("<"):
        match = _RE_NUMBER.search(normalized[1:])
        if match:
            number = float(match.group(0))
            return {
                "raw_value": raw,
                "qualifier": "LT",
                "numeric_value": number,
                "calculation_value": number,
                "calculation_status": "UPPER_BOUND",
                "is_qualified": True,
                "recognized": True,
            }

    if normalized.startswith(">"):
        match = _RE_NUMBER.search(normalized[1:])
        if match:
            number = float(match.group(0))
            return {
                "raw_value": raw,
                "qualifier": "GT",
                "numeric_value": number,
                "calculation_value": number,
                "calculation_status": "LOWER_BOUND",
                "is_qualified": True,
                "recognized": True,
            }

    # BDL / ND with an explicit detection/reporting boundary, e.g.
    # "BDL <0.005" or "ND (<0.005)".
    for qualifier, aliases in QUALIFIER_ALIASES.items():
        if normalized in aliases:
            return {
                "raw_value": raw,
                "qualifier": qualifier,
                "numeric_value": None,
                "calculation_value": None,
                "calculation_status": "NOT_CALCULATED",
                "is_qualified": True,
                "recognized": True,
            }

        if any(alias in normalized for alias in aliases):
            match = _RE_NUMBER.search(normalized)
            if match:
                number = float(match.group(0))
                return {
                    "raw_value": raw,
                    "qualifier": qualifier,
                    "numeric_value": number,
                    "calculation_value": number,
                    "calculation_status": "UPPER_BOUND",
                    "is_qualified": True,
                    "recognized": True,
                }

            return {
                "raw_value": raw,
                "qualifier": qualifier,
                "numeric_value": None,
                "calculation_value": None,
                "calculation_status": "NOT_CALCULATED",
                "is_qualified": True,
                "recognized": True,
            }

    # Normal exact numeric result.
    try:
        number = float(normalized.replace(",", ""))
        if math.isfinite(number):
            return {
                "raw_value": raw,
                "qualifier": "EXACT",
                "numeric_value": number,
                "calculation_value": number,
                "calculation_status": "EXACT",
                "is_qualified": False,
                "recognized": True,
            }
    except ValueError:
        pass

    return {
        "raw_value": raw,
        "qualifier": "INVALID",
        "numeric_value": None,
        "calculation_value": None,
        "calculation_status": "NOT_CALCULATED",
        "is_qualified": False,
        "recognized": False,
    }


def is_recognized_qualifier(value: Any) -> bool:
    parsed = parse_measurement(value)
    return bool(parsed["is_qualified"] and parsed["recognized"])
