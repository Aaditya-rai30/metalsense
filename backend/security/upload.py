from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile


# ============================================================
# SECURE UPLOAD CONFIGURATION
# ============================================================

# Maximum upload size: 25 MB
MAX_UPLOAD_SIZE = 25 * 1024 * 1024

# Maximum number of rows allowed in one dataset
MAX_DATASET_ROWS = 100_000

# Maximum number of columns allowed
MAX_DATASET_COLUMNS = 100

# Only these extensions are accepted
ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".pdf",
}


# ============================================================
# FILENAME VALIDATION
# ============================================================

def validate_filename(filename: str | None) -> str:
    """
    Validate and sanitize an uploaded filename.

    The filename is treated as untrusted user input.
    """

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="A filename is required.",
        )

    # Remove any directory components.
    safe_name = Path(filename).name

    if safe_name in {"", ".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        )

    # Reject control characters.
    if any(ord(char) < 32 for char in safe_name):
        raise HTTPException(
            status_code=400,
            detail="Filename contains invalid control characters.",
        )

    # Prevent excessively long filenames.
    if len(safe_name) > 255:
        raise HTTPException(
            status_code=400,
            detail="Filename is too long.",
        )

    return safe_name


# ============================================================
# EXTENSION VALIDATION
# ============================================================

def validate_extension(filename: str) -> str:
    """
    Validate the file extension against the MetalSense allowlist.
    """

    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Only CSV, XLSX, XLS, and PDF files are allowed."
            ),
        )

    return suffix


# ============================================================
# UPLOAD SIZE VALIDATION
# ============================================================

async def read_upload_safely(
    file: UploadFile,
    max_size: int = MAX_UPLOAD_SIZE,
) -> bytes:
    """
    Read an uploaded file while enforcing a hard size limit.

    The file is read in chunks rather than blindly calling
    await file.read(), preventing oversized uploads from being
    loaded into memory all at once.
    """

    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await file.read(1024 * 1024)

        if not chunk:
            break

        total_size += len(chunk)

        if total_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Uploaded file is too large. "
                    f"Maximum allowed size is "
                    f"{max_size // (1024 * 1024)} MB."
                ),
            )

        chunks.append(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    return b"".join(chunks)


# ============================================================
# DATASET DIMENSION VALIDATION
# ============================================================

def validate_dataframe_dimensions(
    row_count: int,
    column_count: int,
) -> None:
    """
    Prevent extremely large datasets from consuming excessive
    CPU and memory during Pandas/ML processing.
    """

    if row_count > MAX_DATASET_ROWS:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Dataset contains too many rows.",
                "maximum_rows": MAX_DATASET_ROWS,
                "received_rows": row_count,
            },
        )

    if column_count > MAX_DATASET_COLUMNS:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Dataset contains too many columns.",
                "maximum_columns": MAX_DATASET_COLUMNS,
                "received_columns": column_count,
            },
        )


# ============================================================
# METADATA VALIDATION
# ============================================================

def validate_metadata(metadata: dict) -> dict:
    """
    Validate import metadata before the dataset reaches the
    processing pipeline.
    """

    required_fields = [
        "data_source",
        "laboratory_organization",
        "report_id",
        "analytical_method",
        "detection_limit",
    ]

    cleaned = {}

    for field in required_fields:
        value = metadata.get(field)

        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} is required.",
            )

        value = str(value).strip()

        if not value:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be empty.",
            )

        if len(value) > 500:
            raise HTTPException(
                status_code=422,
                detail=f"{field} is too long.",
            )

        cleaned[field] = value

    # --------------------------------------------------------
    # Detection limit
    # --------------------------------------------------------

    detection_limit = cleaned["detection_limit"]

    # Accept common formats such as:
    #
    # 0.001
    # 0.001 mg/L
    # <0.001 mg/L
    #
    # but reject arbitrary huge strings.

    detection_pattern = re.compile(
        r"^[<>]?\s*\d+(?:\.\d+)?\s*(?:mg/L|mg/l|µg/L|ug/L|ppm|ppb)?$"
    )

    if not detection_pattern.match(detection_limit):
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid detection_limit. "
                "Use a numeric value optionally followed "
                "by a supported concentration unit."
            ),
        )

    return cleaned


# ============================================================
# BASIC CONTENT CHECK
# ============================================================

def validate_file_content(
    raw: bytes,
    suffix: str,
) -> None:
    """
    Perform lightweight content checks before Pandas parsing.

    This is not intended to replace Pandas validation. It is an
    additional security boundary.
    """

    if not raw:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )


    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if suffix == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The uploaded PDF file has an invalid "
                    "file signature."
                ),
            )

        return

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if suffix == ".csv":

        # CSV must contain valid text-like content.
        try:
            raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "CSV file is not valid UTF-8 text."
                ),
            )

        return

    # --------------------------------------------------------
    # XLSX
    # --------------------------------------------------------

    if suffix == ".xlsx":

        # XLSX files are ZIP containers.
        # ZIP files begin with PK.
        if not raw.startswith(b"PK"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The uploaded XLSX file has an invalid "
                    "file signature."
                ),
            )

        return

    # --------------------------------------------------------
    # XLS
    # --------------------------------------------------------

    if suffix == ".xls":

        # Traditional XLS files use the OLE compound document
        # signature.
        if not raw.startswith(
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "The uploaded XLS file has an invalid "
                    "file signature."
                ),
            )
def validate_coordinate_value(
    latitude,
    longitude,
    row_number: int,
) -> None:
    """
    Security-level validation for geographic coordinates.

    This runs before the expensive quality/ML pipeline.
    """

    import math

    # --------------------------------------------------------
    # Convert to float
    # --------------------------------------------------------

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid geographic coordinates.",
                "row": row_number,
                "problem": (
                    "Latitude and longitude must be numeric."
                ),
            },
        )

    # --------------------------------------------------------
    # Reject NaN / Infinity
    # --------------------------------------------------------

    if not math.isfinite(lat) or not math.isfinite(lon):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid geographic coordinates.",
                "row": row_number,
                "problem": (
                    "Latitude and longitude cannot be "
                    "NaN or infinite."
                ),
            },
        )

    # --------------------------------------------------------
    # Geographic bounds
    # --------------------------------------------------------

    if not -90 <= lat <= 90:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid latitude.",
                "row": row_number,
                "latitude": lat,
                "problem": (
                    "Latitude must be between -90 and 90."
                ),
            },
        )

    if not -180 <= lon <= 180:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid longitude.",
                "row": row_number,
                "longitude": lon,
                "problem": (
                    "Longitude must be between -180 and 180."
                ),
            },
        )
def validate_dataframe_security(
    df,
    latitude_column: str | None,
    longitude_column: str | None,
    metal_columns: list[str] | None = None,
) -> None:
    """
    Perform lightweight security validation on the parsed
    dataframe before it reaches the expensive MetalSense
    quality/ML pipeline.

    This is intentionally separate from the scientific
    validation already implemented in dataset_service.py.
    """

    import math

    # ========================================================
    # BASIC DATAFRAME CHECK
    # ========================================================

    if df is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to read dataset.",
        )

    if len(df) == 0:
        raise HTTPException(
            status_code=400,
            detail="Dataset contains no records.",
        )

    # ========================================================
    # COLUMN NAME SANITIZATION
    # ========================================================

    for column in df.columns:

        if not isinstance(column, str):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Invalid column name.",
                    "problem": (
                        "All dataset column names must "
                        "be strings."
                    ),
                },
            )

        if len(column) > 100:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Column name is too long.",
                    "column": column[:100],
                },
            )

    # ========================================================
    # COORDINATE CHECK
    # ========================================================

    if latitude_column and longitude_column:

        if latitude_column not in df.columns:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Latitude column not found.",
                    "column": latitude_column,
                },
            )

        if longitude_column not in df.columns:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Longitude column not found.",
                    "column": longitude_column,
                },
            )

        for index, row in df.iterrows():

            row_number = int(index) + 2

            try:
                latitude = float(
                    row[latitude_column]
                )

                longitude = float(
                    row[longitude_column]
                )

            except (TypeError, ValueError):

                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": (
                            "Invalid geographic "
                            "coordinates."
                        ),
                        "row": row_number,
                        "problem": (
                            "Latitude and longitude "
                            "must be numeric."
                        ),
                    },
                )

            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
            ):

                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": (
                            "Invalid geographic "
                            "coordinates."
                        ),
                        "row": row_number,
                        "problem": (
                            "Latitude and longitude "
                            "cannot be NaN or infinite."
                        ),
                    },
                )

            if not -90 <= latitude <= 90:

                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "Invalid latitude.",
                        "row": row_number,
                        "latitude": latitude,
                        "problem": (
                            "Latitude must be between "
                            "-90 and 90."
                        ),
                    },
                )

            if not -180 <= longitude <= 180:

                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "Invalid longitude.",
                        "row": row_number,
                        "longitude": longitude,
                        "problem": (
                            "Longitude must be between "
                            "-180 and 180."
                        ),
                    },
                )

    # ========================================================
    # METAL VALUE CHECK
    # ========================================================

    if metal_columns:

        for metal_column in metal_columns:

            if metal_column not in df.columns:
                continue

            for index, value in enumerate(
                df[metal_column]
            ):

                if value is None:
                    continue

                try:

                    numeric_value = float(value)

                except (TypeError, ValueError):

                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": (
                                "Invalid metal "
                                "measurement."
                            ),
                            "row": index + 2,
                            "column": metal_column,
                            "value": str(value),
                            "problem": (
                                "Metal concentration "
                                "must be numeric."
                            ),
                        },
                    )

                if not math.isfinite(
                    numeric_value
                ):

                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": (
                                "Invalid metal "
                                "measurement."
                            ),
                            "row": index + 2,
                            "column": metal_column,
                            "value": str(value),
                            "problem": (
                                "Metal concentration "
                                "cannot be NaN or infinite."
                            ),
                        },
                    )

                if numeric_value < 0:

                    raise HTTPException(
                        status_code=422,
                        detail={
                            "message": (
                                "Invalid metal "
                                "measurement."
                            ),
                            "row": index + 2,
                            "column": metal_column,
                            "value": numeric_value,
                            "problem": (
                                "Metal concentration "
                                "cannot be negative."
                            ),
                        },
                    )
