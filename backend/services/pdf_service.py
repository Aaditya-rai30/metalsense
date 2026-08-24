from __future__ import annotations

import re
from typing import Any

import pymupdf
import pandas as pd


METALS = {
    "pb": "Pb",
    "lead": "Pb",
    "cd": "Cd",
    "cadmium": "Cd",
    "as": "As",
    "arsenic": "As",
    "cr": "Cr",
    "chromium": "Cr",
    "hg": "Hg",
    "mercury": "Hg",
    "ni": "Ni",
    "nickel": "Ni",
    "cu": "Cu",
    "copper": "Cu",
    "zn": "Zn",
    "zinc": "Zn",
    "fe": "Fe",
    "iron": "Fe",
    "mn": "Mn",
    "manganese": "Mn",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip(),
    )


def normalize(value: Any) -> str:
    value = clean_text(value).lower()

    value = value.replace("µ", "u")

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    ).strip()


def detect_metal(value: Any) -> str | None:
    """
    Detect a supported metal from messy PDF headers.

    Examples:
        Cd
        Cadmium
        Cadmium (mg/L)
        Chromium Total (mg/L)
        Lead (mg/L)
        Zinc concentration
    """

    normalized = normalize(value)
    compact = normalized.replace(" ", "")

    # Exact matches first.
    exact = (
        METALS.get(normalized)
        or METALS.get(compact)
    )

    if exact:
        return exact

    # PDF headers frequently contain units or descriptors.
    # Example:
    # "Cadmium (mg/L)" -> "cadmium mg l"
    for alias, metal in METALS.items():
        alias_normalized = normalize(alias)
        alias_compact = alias_normalized.replace(" ", "")

        if alias_normalized in normalized:
            return metal

        if alias_compact and alias_compact in compact:
            return metal

    return None
# ============================================================
# VALUE PARSING
# ============================================================

def parse_numeric(value: Any):
    text = clean_text(value)

    if not text:
        return None

    if text.upper() in {
        "ND",
        "N.D.",
        "N/A",
        "NA",
        "BDL",
        "B.D.L.",
        "NOT DETECTED",
    }:
        return None

    match = re.search(
        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
        r"(?:[eE][-+]?\d+)?",
        text,
    )

    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


# ============================================================
# PDF TEXT
# ============================================================

def extract_text(
    pdf_bytes: bytes,
) -> tuple[str, list[int]]:

    document = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    pages = []

    try:
        for page_number, page in enumerate(
            document,
            start=1,
        ):
            text = page.get_text("text")

            if text.strip():
                pages.append(
                    (
                        page_number,
                        text,
                    )
                )
    finally:
        document.close()

    combined = "\n".join(
        text
        for _, text in pages
    )

    return combined, [
        page
        for page, _ in pages
    ]


# ============================================================
# METADATA EXTRACTION
# ============================================================

def _first_match(
    text: str,
    patterns: list[str],
) -> str | None:

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            value = clean_text(
                match.group(1)
            )

            if value:
                return value

    return None


def extract_metadata(
    text: str,
) -> dict[str, Any]:

    metadata = {}

    metadata["sample_id"] = _first_match(
        text,
        [
            r"(?:sample\s*id|sample\s*no|sample\s*number)"
            r"\s*[:\-]\s*([A-Za-z0-9._/-]+)",

            r"(?:sample)\s*[:\-]\s*([A-Za-z0-9._/-]+)",
        ],
    )

    metadata["date"] = _first_match(
        text,
        [
            r"(?:sample\s*date|sampling\s*date|date\s*of\s*sampling)"
            r"\s*[:\-]\s*([0-9]{1,4}[/-][0-9]{1,2}[/-][0-9]{1,4})",

            r"(?:date)"
            r"\s*[:\-]\s*([0-9]{1,4}[/-][0-9]{1,2}[/-][0-9]{1,4})",
        ],
    )

    metadata["season"] = _first_match(
        text,
        [
            r"(?:season|sampling\s*season)"
            r"\s*[:\-]\s*([A-Za-z -]+)",
        ],
    )

    metadata["country"] = _first_match(
        text,
        [
            r"(?:country)"
            r"\s*[:\-]\s*([A-Za-z .'-]+)",
        ],
    )

    metadata["region"] = _first_match(
        text,
        [
            r"(?:state|region|province)"
            r"\s*[:\-]\s*([A-Za-z .'-]+)",
        ],
    )

    metadata["area"] = _first_match(
        text,
        [
            r"(?:city|area|location|site)"
            r"\s*[:\-]\s*([A-Za-z0-9 .,'()/-]+)",
        ],
    )

    lat = _first_match(
        text,
        [
            r"(?:latitude|lat\.?)"
            r"\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        ],
    )

    lon = _first_match(
        text,
        [
            r"(?:longitude|long\.?|lon\.?)"
            r"\s*[:=]\s*([-+]?\d+(?:\.\d+)?)",
        ],
    )

    metadata["latitude"] = (
        float(lat)
        if lat is not None
        else None
    )

    metadata["longitude"] = (
        float(lon)
        if lon is not None
        else None
    )

    return metadata


# ============================================================
# TABLE EXTRACTION
# ============================================================

def extract_tables(
    pdf_bytes: bytes,
) -> list[dict[str, Any]]:

    document = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    tables = []

    try:
        for page_number, page in enumerate(
            document,
            start=1,
        ):

            try:
                finder = page.find_tables()

                for table in finder.tables:

                    rows = table.extract()

                    if not rows:
                        continue

                    tables.append(
                        {
                            "page":
                                page_number,
                            "rows":
                                rows,
                        }
                    )

            except Exception:
                continue

    finally:
        document.close()

    return tables

# ============================================================
# PDF COLUMN CANONICALIZATION
# ============================================================

def canonicalize_pdf_column(value: Any) -> str:
    """
    Convert messy laboratory/PDF headers into the canonical
    MetalSense column names.

    This is intentionally done only for PDF input.
    CSV/XLSX files continue using their original columns.
    """

    original = clean_text(value)

    if not original:
        return ""

    normalized = normalize(original)

    # --------------------------------------------------------
    # Basic metadata
    # --------------------------------------------------------

    if (
        normalized in {
            "s no",
            "serial no",
            "serial number",
            "sr no",
            "sr number",
        }
        or normalized.startswith("s no ")
    ):
        return "sample_id"

    if (
        "name of the location" in normalized
        or normalized == "location"
        or normalized == "location name"
        or normalized == "sampling location"
        or normalized == "site"
    ):
        return "location_name"

    if (
        normalized in {
            "state",
            "state ut",
            "state / ut",
            "state ut name",
        }
    ):
        return "region"

    if (
        normalized == "date time"
        or normalized == "date/time"
        or normalized == "sampling date"
        or normalized == "sample date"
    ):
        return "date"

    if (
        normalized == "source of sample"
        or normalized == "source of sample river lake pond sea coast artificial ponds"
        or normalized == "water source"
    ):
        return "water_type"

    if "festival" in normalized and "event" in normalized:
        return "event"

    # --------------------------------------------------------
    # Heavy metals
    # --------------------------------------------------------

    metal = detect_metal(original)

    if metal:
        return metal

    # --------------------------------------------------------
    # Keep the original header if it is not canonical.
    # --------------------------------------------------------

    return original

# ============================================================
# WIDE TABLE
# ============================================================

def parse_wide_table(
    rows: list[list[Any]],
) -> pd.DataFrame:

    if len(rows) < 2:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Find the most likely header row.
    #
    # Some PDFs have title/section rows before the actual
    # table header.
    # --------------------------------------------------------

    best_header_index = 0
    best_score = -1

    for index, candidate in enumerate(rows[:8]):
        if not candidate:
            continue

        text = " ".join(
            clean_text(value)
            for value in candidate
            if clean_text(value)
        )

        score = 0
        normalized = normalize(text)

        # Metadata/header signals
        header_signals = [
            "state",
            "location",
            "sample",
            "date",
            "time",
            "source",
            "water",
            "ph",
            "conductivity",
            "turbidity",
            "cadmium",
            "copper",
            "chromium",
            "manganese",
            "lead",
            "zinc",
            "mercury",
            "arsenic",
            "nickel",
            "iron",
        ]

        for signal in header_signals:
            if signal in normalized:
                score += 1

        # Prefer wide rows because these are the actual
        # laboratory measurement tables.
        score += min(len(candidate), 45) / 100

        if score > best_score:
            best_score = score
            best_header_index = index

    headers = [
        canonicalize_pdf_column(value)
        for value in rows[best_header_index]
    ]

    if not headers:
        return pd.DataFrame()

    records = []

    for row in rows[best_header_index + 1:]:

        values = list(row)

        # Pad short rows.
        if len(values) < len(headers):
            values += [""] * (
                len(headers) - len(values)
            )

        # Trim oversized rows.
        if len(values) > len(headers):
            values = values[:len(headers)]

        record = {}

        for header, value in zip(
            headers,
            values,
        ):
            if not header:
                continue

            record[header] = clean_text(value)

        if record:
            records.append(record)

    if not records:
        return pd.DataFrame()

    dataframe = pd.DataFrame(records)

    # --------------------------------------------------------
    # Canonicalize duplicate / messy column names again.
    # --------------------------------------------------------

    dataframe.columns = [
        canonicalize_pdf_column(column)
        for column in dataframe.columns
    ]

    return dataframe
    
# ============================================================
# LONG PARAMETER TABLE
# ============================================================

def parse_long_table(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:
        return df

    columns = {
        normalize(column): column
        for column in df.columns
    }

    parameter_col = None
    value_col = None
    unit_col = None

    for name in (
        "parameter",
        "analyte",
        "metal",
        "element",
        "test parameter",
        "test",
    ):
        if name in columns:
            parameter_col = columns[name]
            break

    for name in (
        "result",
        "value",
        "concentration",
        "measurement",
        "result value",
    ):
        if name in columns:
            value_col = columns[name]
            break

    for name in (
        "unit",
        "units",
    ):
        if name in columns:
            unit_col = columns[name]
            break

    if not parameter_col or not value_col:
        return df

    output = {}

    for _, row in df.iterrows():

        metal = detect_metal(
            row.get(parameter_col)
        )

        if not metal:
            continue

        value = parse_numeric(
            row.get(value_col)
        )

        output[metal] = value

        if unit_col:
            output["unit"] = clean_text(
                row.get(unit_col)
            )

    if not output:
        return df

    return pd.DataFrame(
        [output]
    )


# ============================================================
# METAL/VALUE TEXT FALLBACK
# ============================================================

def parse_text_measurements(
    text: str,
) -> dict[str, float]:

    result = {}

    metal_pattern = (
        r"\b(Pb|Cd|As|Cr|Hg|Ni|Cu|Zn|Fe|Mn)"
        r"\b"
    )

    number_pattern = (
        r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
        r"(?:[eE][-+]?\d+)?"
    )

    for match in re.finditer(
        rf"{metal_pattern}"
        rf".{{0,80}}?"
        rf"({number_pattern})",
        text,
        flags=re.IGNORECASE,
    ):

        metal = detect_metal(
            match.group(1)
        )

        value = parse_numeric(
            match.group(2)
        )

        if metal and value is not None:
            result[metal] = value

    return result


# ============================================================
# CANONICAL DATAFRAME
# ============================================================

def build_dataframe(
    tables: list[dict[str, Any]],
    metadata: dict[str, Any],
    text: str,
) -> pd.DataFrame:

    frames = []

    for table in tables:

        df = parse_wide_table(
            table["rows"]
        )

        if df.empty:
            continue

        long_df = parse_long_table(
            df
        )

        if not long_df.empty:
            df = long_df

        frames.append(df)

    # --------------------------------------------------------
    # Combine table results
    # --------------------------------------------------------

    if frames:

        combined = pd.concat(
            frames,
            ignore_index=True,
            sort=False,
        )

    else:

        measurements = (
            parse_text_measurements(
                text
            )
        )

        if not measurements:
            return pd.DataFrame()

        combined = pd.DataFrame(
            [measurements]
        )

    # --------------------------------------------------------
    # Normalize known metadata
    # --------------------------------------------------------

    metadata_map = {
        "sample_id": "sample_id",
        "date": "date",
        "season": "season",
        "latitude": "latitude",
        "longitude": "longitude",
        "country": "country",
        "region": "region",
        "area": "area",
    }

    for source, target in metadata_map.items():

        if target not in combined.columns:

            value = metadata.get(source)

            if value is not None:
                combined[target] = value

    # --------------------------------------------------------
    # Fill metadata for all rows
    # --------------------------------------------------------

    for key, value in metadata.items():

        if key not in combined.columns:
            combined[key] = value

    # --------------------------------------------------------
    # Clean obvious empty columns
    # --------------------------------------------------------

    for column in combined.columns:

        combined[column] = combined[
            column
        ].map(clean_text)

    return combined


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================

def parse_pdf(
    pdf_bytes: bytes,
    filename: str,
) -> dict[str, Any]:

    if not pdf_bytes:
        raise ValueError(
            "The uploaded PDF is empty."
        )

    text, text_pages = extract_text(
        pdf_bytes
    )

    if not text.strip():
        raise ValueError(
            "This PDF contains no extractable text. "
            "Scanned/image-only PDFs require OCR."
        )

    metadata = extract_metadata(
        text
    )

    tables = extract_tables(
        pdf_bytes
    )

    dataframe = build_dataframe(
        tables=tables,
        metadata=metadata,
        text=text,
    )

    if dataframe.empty:
        raise ValueError(
            "No supported metal measurements "
            "could be extracted from the PDF."
        )

    # --------------------------------------------------------
    # Provenance
    # --------------------------------------------------------

    dataframe.attrs[
        "pdf_import"
    ] = {
        "extraction_method":
            "PyMuPDF",

        "pages_with_text":
            text_pages,

        "table_count":
            len(tables),

        "metadata":
            metadata,

        "filename":
            filename,
    }

    return {
        "dataframe":
            dataframe,

        "metadata":
            metadata,

        "pages_with_text":
            text_pages,

        "table_count":
            len(tables),

        "extraction_method":
            "PyMuPDF",
    }
