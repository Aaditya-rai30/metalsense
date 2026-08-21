from __future__ import annotations

import io
import logging
import math
import uuid
from pathlib import Path

import pandas as pd
import requests
from fastapi import HTTPException, UploadFile

from database import db
from engine.data_quality_engine import DataQualityEngine
from engine.pollution_engine import METALS, calculate_indices
from services.standards_service import (
    get_standards,
    standard_metadata,
)


logger = logging.getLogger(__name__)


# ============================================================
# COLUMN ALIASES
# ============================================================

ALIASES = {
    "latitude": [
        "latitude",
        "lat",
    ],
    "longitude": [
        "longitude",
        "lon",
        "lng",
    ],
    "sample_id": [
        "sample_id",
        "sampleid",
        "sample id",
        "sample",
        "id",
    ],
    "date": [
        "date",
        "datetime",
        "date time",
        "time",
    ],
    "country": [
        "country",
    ],
    "water_type": [
        "water_type",
        "water type",
        "watertype",
    ],
    "unit": [
        "unit",
        "units",
    ],
    "authority": [
        "authority",
        "standard_authority",
        "standard authority",
    ],
}


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize(value) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def normalized_columns(df: pd.DataFrame):
    return {
        normalize(column): column
        for column in df.columns
    }


def find_column(
    columns,
    names,
):
    normalized_names = {
        normalize(name)
        for name in names
    }

    compact_names = {
        name.replace(" ", "")
        for name in normalized_names
    }

    for key, original in columns.items():

        if key in normalized_names:
            return original

        if key.replace(" ", "") in compact_names:
            return original

    return None


def find_metal_columns(
    df: pd.DataFrame,
):
    columns = normalized_columns(df)

    metal_columns = {}

    for metal, aliases in METALS.items():

        found = find_column(
            columns,
            aliases,
        )

        if found:
            metal_columns[metal] = found

    return metal_columns


# ============================================================
# EXPORT QUALITY
# ============================================================

def calculate_export_quality(
    records,
):
    """
    Calculate an integrity score for a MetalSense
    results export.

    This is NOT the raw laboratory-data quality score.

    It checks whether the already-calculated export contains
    complete and valid report information.
    """

    if not records:

        return {
            "score": 0,
            "type": "export_integrity",
            "label": "Export Integrity",
            "status": "Empty",
            "valid_records": 0,
            "invalid_records": 0,
            "missing_fields": 0,
            "coordinate_issues": 0,
            "analysis_issues": 0,
            "reason": (
                "No records were found in the "
                "MetalSense export."
            ),
        }

    required_fields = [
        "sample_id",
        "latitude",
        "longitude",
        "country",
        "region",
        "area",
        "analysis",
    ]

    analysis_fields = [
        "hpi",
        "hei",
        "cd",
        "status",
    ]

    total_checks = 0
    passed_checks = 0

    invalid_records = 0
    missing_fields = 0
    coordinate_issues = 0
    analysis_issues = 0

    for record in records:

        record_valid = True

        # ----------------------------------------------------
        # General fields
        # ----------------------------------------------------

        for field in required_fields:

            total_checks += 1

            value = record.get(field)

            if (
                value is None
                or value == ""
            ):

                missing_fields += 1
                record_valid = False

            else:

                passed_checks += 1

        # ----------------------------------------------------
        # Analysis fields
        # ----------------------------------------------------

        analysis = record.get(
            "analysis",
            {},
        )

        for field in analysis_fields:

            total_checks += 1

            value = analysis.get(
                field
            )

            if (
                value is None
                or value == ""
            ):

                analysis_issues += 1
                record_valid = False

            else:

                passed_checks += 1

        # ----------------------------------------------------
        # Coordinates
        # ----------------------------------------------------

        total_checks += 2

        try:

            latitude = float(
                record.get(
                    "latitude"
                )
            )

            longitude = float(
                record.get(
                    "longitude"
                )
            )

            if -90 <= latitude <= 90:
                passed_checks += 1
            else:
                coordinate_issues += 1
                record_valid = False

            if -180 <= longitude <= 180:
                passed_checks += 1
            else:
                coordinate_issues += 1
                record_valid = False

        except (
            TypeError,
            ValueError,
        ):

            coordinate_issues += 1
            record_valid = False

        if not record_valid:
            invalid_records += 1

    score = round(
        (
            passed_checks
            / total_checks
        ) * 100
        if total_checks
        else 0
    )

    if score >= 90:
        status = "Excellent"

    elif score >= 75:
        status = "Good"

    elif score >= 50:
        status = "Fair"

    else:
        status = "Poor"

    return {
        "score":
            score,

        "type":
            "export_integrity",

        "label":
            "Export Integrity",

        "status":
            status,

        "valid_records":
            len(records)
            - invalid_records,

        "invalid_records":
            invalid_records,

        "missing_fields":
            missing_fields,

        "coordinate_issues":
            coordinate_issues,

        "analysis_issues":
            analysis_issues,

        "reason": (
            "Score calculated from the completeness "
            "and validity of the previously exported "
            "MetalSense results. This score does not "
            "recalculate or validate the original raw "
            "laboratory measurements."
        ),
    }


# ============================================================
# METALSENSE EXPORT DETECTION
# ============================================================

def is_metalsense_export(
    df: pd.DataFrame,
) -> bool:
    """
    Detect a MetalSense result export.

    The export currently has a malformed header with
    16 column labels while its data rows contain 13
    actual values.
    """

    columns = {
        normalize(column)
        for column in df.columns
    }

    required_markers = {
        "application",
        "dataset",
        "export date",
        "sample id",
        "latitude",
        "longitude",
        "hpi",
        "hei",
        "cd",
        "status",
    }

    return required_markers.issubset(
        columns
    )


def is_metalsense_export_raw(
    raw: bytes,
) -> bool:
    """
    Detect MetalSense export directly from the raw CSV.

    This is more reliable than inspecting the Pandas dataframe,
    because Pandas may already have misaligned the malformed
    export header.
    """

    try:

        text = raw.decode(
            "utf-8-sig",
            errors="replace",
        )

    except Exception:

        return False

    first_line = (
        text.splitlines()[0]
        if text.splitlines()
        else ""
    )

    normalized = normalize(
        first_line
    )

    required = [
        "application",
        "metalSense".lower(),
        "dataset",
        "export date",
        "sample id",
        "latitude",
        "longitude",
        "hpi",
        "hei",
        "cd",
        "status",
    ]

    return all(
        token in normalized
        for token in required
    )


# ============================================================
# METALSENSE EXPORT PARSER
# ============================================================

def parse_metalsense_export(
    raw: bytes,
    filename: str,
):
    """
    Parse the MetalSense export from RAW CSV bytes.

    IMPORTANT:

    The export header has 16 labels:

        Application
        MetalSense
        Dataset
        sample.csv
        Export Date
        <timestamp>
        Sample ID
        Latitude
        Longitude
        Country
        Region
        Area
        HPI
        HEI
        Cd
        Status

    but every actual data row has 13 values:

        MetalSense
        sample.csv
        timestamp
        S001
        19.076
        72.877
        India
        Maharashtra
        Mumbai
        31.39
        1.88
        0
        LOW

    Therefore we intentionally read the data rows with
    header=None and skip the malformed header row.
    """

    export_columns = [
        "application",
        "dataset",
        "export_date",
        "sample_id",
        "latitude",
        "longitude",
        "country",
        "region",
        "area",
        "hpi",
        "hei",
        "cd",
        "status",
    ]

    # --------------------------------------------------------
    # Read raw data rows
    # --------------------------------------------------------

    try:

        raw_df = pd.read_csv(
            io.BytesIO(raw),
            header=None,
            skiprows=1,
            dtype=object,
            keep_default_na=False,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                "Could not parse MetalSense export: "
                f"{exc}"
            ),
        )

    actual_rows = []

    for row_number, row in raw_df.iterrows():

        values = row.tolist()

        # Remove trailing empty cells.
        while (
            values
            and (
                values[-1] is None
                or str(
                    values[-1]
                ).strip() == ""
            )
        ):

            values.pop()

        if len(values) != 13:

            logger.warning(
                "Skipping malformed MetalSense export row %s: %s",
                row_number + 2,
                values,
            )

            continue

        actual_rows.append(
            values
        )

    if not actual_rows:

        return {
            "records": [],

            "source_type":
                "metalsense_export",

            "source_application":
                "MetalSense",

            "source_dataset":
                None,

            "source_export_date":
                None,

            "columns":
                export_columns,

            "quality":
                calculate_export_quality(
                    []
                ),
        }

    # --------------------------------------------------------
    # Correctly aligned dataframe
    # --------------------------------------------------------

    export_df = pd.DataFrame(
        actual_rows,
        columns=export_columns,
    )

    # --------------------------------------------------------
    # Numeric fields
    # --------------------------------------------------------

    for column in [
        "latitude",
        "longitude",
        "hpi",
        "hei",
        "cd",
    ]:

        export_df[column] = pd.to_numeric(
            export_df[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Records
    # --------------------------------------------------------

    records = []

    for _, row in export_df.iterrows():

        status = (
            str(
                row["status"]
            )
            .strip()
            .upper()
        )

        analysis = {
            "hpi":
                (
                    float(
                        row["hpi"]
                    )
                    if pd.notna(
                        row["hpi"]
                    )
                    else None
                ),

            "hei":
                (
                    float(
                        row["hei"]
                    )
                    if pd.notna(
                        row["hei"]
                    )
                    else None
                ),

            "cd":
                (
                    float(
                        row["cd"]
                    )
                    if pd.notna(
                        row["cd"]
                    )
                    else None
                ),

            "status":
                status,

            # The export contains only aggregated
            # HPI / HEI / Cd results. It does not contain
            # original per-metal measurements.
            "metals": [],

            "highest_metal":
                None,
        }

        records.append(
            {
                "sample_id":
                    str(
                        row["sample_id"]
                    ).strip(),

                "date":
                    None,

                "latitude":
                    (
                        float(
                            row["latitude"]
                        )
                        if pd.notna(
                            row["latitude"]
                        )
                        else None
                    ),

                "longitude":
                    (
                        float(
                            row["longitude"]
                        )
                        if pd.notna(
                            row["longitude"]
                        )
                        else None
                    ),

                "country":
                    str(
                        row["country"]
                    ).strip(),

                "region":
                    str(
                        row["region"]
                    ).strip(),

                "area":
                    str(
                        row["area"]
                    ).strip(),

                "water_body":
                    "Unknown",

                "geo_source":
                    "Imported MetalSense export",

                "standard":
                    "Imported from MetalSense export",

                "authority":
                    "MetalSense",

                "standard_reason":
                    (
                        "Previously calculated result "
                        "imported from a MetalSense export."
                    ),

                "analysis":
                    analysis,
            }
        )

    # --------------------------------------------------------
    # Export metadata
    # --------------------------------------------------------

    source_application = str(
        export_df[
            "application"
        ].iloc[0]
    ).strip()

    source_dataset = str(
        export_df[
            "dataset"
        ].iloc[0]
    ).strip()

    source_export_date = str(
        export_df[
            "export_date"
        ].iloc[0]
    ).strip()

    return {
        "records":
            records,

        "source_type":
            "metalsense_export",

        "source_application":
            source_application,

        "source_dataset":
            source_dataset,

        "source_export_date":
            source_export_date,

        "columns":
            export_columns,

        "quality":
            calculate_export_quality(
                records
            ),
    }


# ============================================================
# RAW FILE PARSING
# ============================================================

async def parse_upload(
    file: UploadFile,
):
    filename = (
        file.filename
        or "dataset"
    )

    suffix = Path(
        filename
    ).suffix.lower()

    if suffix not in {
        ".csv",
        ".xlsx",
        ".xls",
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Only CSV, XLSX, and XLS "
                "files are supported."
            ),
        )

    raw = await file.read()

    if not raw:

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    try:

        if suffix == ".csv":

            df = pd.read_csv(
                io.BytesIO(raw)
            )

        else:

            df = pd.read_excel(
                io.BytesIO(raw)
            )

    except Exception as exc:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not parse file: {exc}"
            ),
        )

    if df.empty:

        raise HTTPException(
            status_code=400,
            detail="The file contains no records.",
        )

    return (
        filename,
        suffix,
        raw,
        df,
    )


# ============================================================
# REVERSE GEOCODING
# ============================================================

def reverse_geo(
    latitude: float,
    longitude: float,
):
    try:

        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": latitude,
                "lon": longitude,
                "format": "jsonv2",
                "zoom": 10,
            },
            headers={
                "User-Agent":
                    "MetalSense/1.0",
            },
            timeout=8,
        )

        response.raise_for_status()

        address = response.json().get(
            "address",
            {},
        )

        return {
            "country":
                address.get(
                    "country",
                    "Unknown",
                ),

            "region":
                address.get(
                    "state",
                    address.get(
                        "region",
                        "Unknown",
                    ),
                ),

            "area":
                address.get(
                    "city",
                    address.get(
                        "town",
                        address.get(
                            "village",
                            "Unknown",
                        ),
                    ),
                ),

            "source":
                "OpenStreetMap Nominatim",

            "confidence":
                "reverse-geocoded",
        }

    except Exception:

        return {
            "country":
                "Unknown",

            "region":
                "Unknown",

            "area":
                "Unknown",

            "source":
                "Unavailable",

            "confidence":
                "unavailable",
        }


# ============================================================
# QUALITY DATAFRAME
# ============================================================

def build_quality_dataframe(
    df,
    sample_id_col,
    date_col,
    lat_col,
    lon_col,
    country_col,
    water_type_col,
    unit_col,
    metal_columns,
):
    rows = []

    for index, source_row in df.iterrows():

        if (
            sample_id_col
            and pd.notna(
                source_row[
                    sample_id_col
                ]
            )
        ):

            sample_id = str(
                source_row[
                    sample_id_col
                ]
            ).strip()

        else:

            sample_id = (
                f"Sample {index + 1}"
            )

        date = None

        if (
            date_col
            and pd.notna(
                source_row[
                    date_col
                ]
            )
        ):

            date = source_row[
                date_col
            ]

        latitude = source_row[
            lat_col
        ]

        longitude = source_row[
            lon_col
        ]

        if (
            water_type_col
            and pd.notna(
                source_row[
                    water_type_col
                ]
            )
        ):

            water_type = str(
                source_row[
                    water_type_col
                ]
            ).strip()

        else:

            water_type = "Unknown"

        if (
            unit_col
            and pd.notna(
                source_row[
                    unit_col
                ]
            )
        ):

            unit = str(
                source_row[
                    unit_col
                ]
            ).strip()

        else:

            unit = "mg/L"

        if (
            country_col
            and pd.notna(
                source_row[
                    country_col
                ]
            )
        ):

            country = str(
                source_row[
                    country_col
                ]
            ).strip()

        else:

            country = ""

        for metal, column in (
            metal_columns.items()
        ):

            raw_value = source_row[
                column
            ]

            numeric_value = pd.to_numeric(
                raw_value,
                errors="coerce",
            )

            rows.append(
                {
                    "sample_id":
                        sample_id,

                    "quality_record_id":
                        f"{sample_id}:{metal}",

                    "date":
                        date,

                    "latitude":
                        latitude,

                    "longitude":
                        longitude,

                    "water_type":
                        water_type,

                    "metal":
                        metal,

                    "value":
                        numeric_value,

                    "raw_value":
                        raw_value,

                    "unit":
                        unit,

                    "country":
                        country,
                }
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# RAW DATA IMPORT
# ============================================================

async def import_raw_dataset(
    df: pd.DataFrame,
    filename: str,
    suffix: str,
    user: dict,
    import_metadata: dict,
):
    columns = normalized_columns(
        df
    )

    lat_col = find_column(
        columns,
        ALIASES["latitude"],
    )

    lon_col = find_column(
        columns,
        ALIASES["longitude"],
    )

    if not lat_col or not lon_col:

        raise HTTPException(
            status_code=422,
            detail=(
                "Required columns latitude "
                "and longitude were not found."
            ),
        )

    sample_id_col = find_column(
        columns,
        ALIASES["sample_id"],
    )

    date_col = find_column(
        columns,
        ALIASES["date"],
    )

    country_col = find_column(
        columns,
        ALIASES["country"],
    )

    water_type_col = find_column(
        columns,
        ALIASES["water_type"],
    )

    unit_col = find_column(
        columns,
        ALIASES["unit"],
    )

    authority_col = find_column(
        columns,
        ALIASES["authority"],
    )

    metal_columns = find_metal_columns(
        df
    )

    if not metal_columns:

        raise HTTPException(
            status_code=422,
            detail=(
                "At least one supported heavy-metal "
                "column is required: "
                "Pb, Cd, As, Cr, Hg, Ni, Cu, Zn, Fe, Mn."
            ),
        )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    quality_df = (
        build_quality_dataframe(
            df=df,
            sample_id_col=sample_id_col,
            date_col=date_col,
            lat_col=lat_col,
            lon_col=lon_col,
            country_col=country_col,
            water_type_col=water_type_col,
            unit_col=unit_col,
            metal_columns=metal_columns,
        )
    )

    try:

        quality_engine = DataQualityEngine(
            quality_df,
            use_ml_outliers=True,
            restrict_to_india=False,
        )

        quality_report = (
            quality_engine.run()
        )

    except Exception as exc:

        logger.exception(
            "Data quality engine failed"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Data quality engine failed: "
                f"{exc}"
            ),
        )

    # --------------------------------------------------------
    # PROCESS SAMPLES
    # --------------------------------------------------------

    records = []
    errors = []

    coordinate_issues = 0
    quality_missing = 0

    standards_cache = {}

    for index, source_row in (
        df.iterrows()
    ):

        row_number = (
            int(index) + 2
        )

        # ----------------------------------------------------
        # Coordinates
        # ----------------------------------------------------

        try:

            latitude = float(
                source_row[
                    lat_col
                ]
            )

            longitude = float(
                source_row[
                    lon_col
                ]
            )

        except (
            TypeError,
            ValueError,
        ):

            latitude = math.nan
            longitude = math.nan

        if (
            pd.isna(latitude)
            or pd.isna(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):

            coordinate_issues += 1

            errors.append(
                {
                    "row":
                        row_number,

                    "column":
                        lat_col,

                    "problem":
                        (
                            "Latitude/longitude "
                            "is missing or outside "
                            "its valid range."
                        ),
                }
            )

            continue

        # ----------------------------------------------------
        # Country / Geolocation
        # ----------------------------------------------------

        if (
            country_col
            and pd.notna(
                source_row[
                    country_col
                ]
            )
            and str(
                source_row[
                    country_col
                ]
            ).strip()
        ):

            country = str(
                source_row[
                    country_col
                ]
            ).strip()

            geo = {
                "country":
                    country,

                "region":
                    "Unknown",

                "area":
                    "Unknown",

                "source":
                    "Uploaded country field",

                "confidence":
                    "provided",
            }

        else:

            geo = reverse_geo(
                latitude,
                longitude,
            )

            country = geo[
                "country"
            ]

        if normalize(
            country
        ) == "unknown":

            errors.append(
                {
                    "row":
                        row_number,

                    "column":
                        country_col
                        or "Country",

                    "problem":
                        (
                            "Unable to determine "
                            "country for this sample."
                        ),
                }
            )

            continue

        # ----------------------------------------------------
        # Authority
        # ----------------------------------------------------

        authority = None

        if (
            authority_col
            and pd.notna(
                source_row[
                    authority_col
                ]
            )
            and str(
                source_row[
                    authority_col
                ]
            ).strip()
        ):

            authority = str(
                source_row[
                    authority_col
                ]
            ).strip()

        # ----------------------------------------------------
        # Standards
        # ----------------------------------------------------

        cache_key = (
            normalize(country),
            normalize(authority),
        )

        try:

            if cache_key not in standards_cache:

                standards_cache[
                    cache_key
                ] = get_standards(
                    country=country,
                    authority=authority,
                )

            standards = (
                standards_cache[
                    cache_key
                ]
            )

        except ValueError as exc:

            errors.append(
                {
                    "row":
                        row_number,

                    "column":
                        country_col
                        or "Country",

                    "problem":
                        str(exc),
                }
            )

            continue

        metadata = standard_metadata(
            standards
        )

        # ----------------------------------------------------
        # POLLUTION CALCULATION
        # ----------------------------------------------------

        try:

            analysis = calculate_indices(
                row=source_row,
                metal_columns=metal_columns,
                standards=standards,
            )

        except Exception as exc:

            logger.exception(
                "Pollution calculation failed for row %s",
                row_number,
            )

            errors.append(
                {
                    "row":
                        row_number,

                    "problem":
                        (
                            "Pollution calculation "
                            f"failed: {exc}"
                        ),
                }
            )

            continue

        # ----------------------------------------------------
        # MISSING MEASUREMENTS
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

        # ----------------------------------------------------
        # SAMPLE ID
        # ----------------------------------------------------

        if (
            sample_id_col
            and pd.notna(
                source_row[
                    sample_id_col
                ]
            )
        ):

            sample_id = str(
                source_row[
                    sample_id_col
                ]
            ).strip()

        else:

            sample_id = (
                f"Sample {index + 1}"
            )

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        if (
            date_col
            and pd.notna(
                source_row[
                    date_col
                ]
            )
        ):

            sample_date = str(
                source_row[
                    date_col
                ]
            )

        else:

            sample_date = None

        # ----------------------------------------------------
        # WATER TYPE
        # ----------------------------------------------------

        if (
            water_type_col
            and pd.notna(
                source_row[
                    water_type_col
                ]
            )
        ):

            water_body = str(
                source_row[
                    water_type_col
                ]
            ).strip()

        else:

            water_body = "Unknown"

        # ----------------------------------------------------
        # QUALIFIED MEASUREMENTS
        # ----------------------------------------------------

        qualified_measurements = []

        try:

            from engine.measurement_qualifier import (
                parse_measurement,
            )

            for metal, column in (
                metal_columns.items()
            ):

                raw_value = source_row[
                    column
                ]

                parsed = parse_measurement(
                    raw_value
                )

                parsed["metal"] = metal
                parsed["unit"] = (
                    "mg/L"
                    if not unit_col
                    else str(
                        source_row.get(
                            unit_col,
                            "mg/L",
                        )
                    )
                )

                qualified_measurements.append(
                    parsed
                )

        except ImportError:

            # Qualifier module is optional so the
            # normal raw-data pipeline remains usable.
            qualified_measurements = []

        # ----------------------------------------------------
        # STORE RECORD
        # ----------------------------------------------------

        records.append(
            {
                "sample_id":
                    sample_id,

                "date":
                    sample_date,

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "country":
                    geo["country"],

                "region":
                    geo["region"],

                "area":
                    geo["area"],

                "water_body":
                    water_body,

                "geo_source":
                    geo["source"],

                "standard":
                    metadata[
                        "standard"
                    ],

                "authority":
                    metadata[
                        "authority"
                    ],

                "standard_reason":
                    (
                        "Standard selected from "
                        "MetalSense standard registry."
                    ),

                "analysis":
                    analysis,

                "qualified_measurements":
                    qualified_measurements,
            }
        )

    # --------------------------------------------------------
    # VALIDATION ERRORS
    # --------------------------------------------------------

    if errors:

        raise HTTPException(
            status_code=422,
            detail={
                "message":
                    "Data Validation Error",

                "errors":
                    errors,

                "quality_report":
                    quality_report,
            },
        )

    if not records:

        raise HTTPException(
            status_code=422,
            detail={
                "message":
                    "No valid records were produced.",

                "quality_report":
                    quality_report,
            },
        )

    # --------------------------------------------------------
    # DATASET
    # --------------------------------------------------------

    quality_score = round(
        float(
            quality_report.get(
                "overall_score",
                100,
            )
        )
    )

    dataset = {
        "dataset_id":
            str(uuid.uuid4()),

        "user_id":
            user["user_id"],

        "filename":
            filename,

        "file_type":
            suffix[1:].upper(),

        "data_source":
            import_metadata["data_source"],

        "laboratory_organization":
            import_metadata["laboratory_organization"],

        "report_id":
            import_metadata["report_id"],

        "analytical_method":
            import_metadata["analytical_method"],

        "detection_limit":
            import_metadata["detection_limit"],

        "source_type":
            "raw_measurements",

        "imported_at":
            pd.Timestamp.now(
                tz="UTC"
            ).isoformat(),

        "records":
            records,

        "columns":
            [
                str(column)
                for column in df.columns
            ],

        "quality": {
            "score":
                quality_score,

            "missing":
                quality_missing,

            "coordinate_issues":
                coordinate_issues,

            "duplicates":
                int(
                    df.duplicated().sum()
                ),

            "valid_records":
                len(records),

            "invalid_records":
                0,

            "engine_report":
                quality_report,
        },
    }

    await db.datasets.insert_one(
        dataset
    )

    dataset.pop(
        "_id",
        None,
    )

    return dataset


# ============================================================
# MAIN IMPORT
# ============================================================

async def import_dataset(
    file: UploadFile,
    user: dict,
    import_metadata: dict,
):
    (
        filename,
        suffix,
        raw,
        df,
    ) = await parse_upload(
        file
    )

    # ========================================================
    # METALSENSE EXPORT
    # ========================================================

    if (
        suffix == ".csv"
        and is_metalsense_export_raw(
            raw
        )
    ):

        logger.info(
            "Detected MetalSense export: %s",
            filename,
        )

        exported = (
            parse_metalsense_export(
                raw=raw,
                filename=filename,
            )
        )

        dataset = {
            "dataset_id":
                str(uuid.uuid4()),

            "user_id":
                user["user_id"],

            "filename":
                filename,

            "file_type":
                suffix[1:].upper(),

            "data_source":
                import_metadata["data_source"],

            "laboratory_organization":
                import_metadata["laboratory_organization"],

            "report_id":
                import_metadata["report_id"],

            "analytical_method":
                import_metadata["analytical_method"],

            "detection_limit":
                import_metadata["detection_limit"],

            "source_type":
                "metalsense_export",

            "source_application":
                exported[
                    "source_application"
                ],

            "source_dataset":
                exported[
                    "source_dataset"
                ],

            "source_export_date":
                exported[
                    "source_export_date"
                ],

            "imported_at":
                pd.Timestamp.now(
                    tz="UTC"
                ).isoformat(),

            "records":
                exported[
                    "records"
                ],

            "columns":
                exported[
                    "columns"
                ],

            "quality":
                exported[
                    "quality"
                ],
        }

        await db.datasets.insert_one(
            dataset
        )

        dataset.pop(
            "_id",
            None,
        )

        return dataset

    # ========================================================
    # NORMAL RAW DATASET
    # ========================================================

    return await import_raw_dataset(
        df=df,
        filename=filename,
        suffix=suffix,
        user=user,
        import_metadata=import_metadata,
    )


# ============================================================
# DATASET CRUD
# ============================================================

async def list_datasets(
    user: dict,
):
    return await db.datasets.find(
        {
            "user_id":
                user["user_id"]
        },
        {
            "_id": 0
        },
    ).sort(
        "imported_at",
        -1,
    ).to_list(50)


async def delete_dataset(
    dataset_id: str,
    user: dict,
):
    result = await db.datasets.delete_one(
        {
            "dataset_id":
                dataset_id,

            "user_id":
                user["user_id"],
        }
    )

    if not result.deleted_count:

        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )

    return {
        "deleted":
            True
    }


async def clear_datasets(
    user: dict,
):
    await db.datasets.delete_many(
        {
            "user_id":
                user["user_id"]
        }
    )

    return {
        "deleted":
            True
    }
