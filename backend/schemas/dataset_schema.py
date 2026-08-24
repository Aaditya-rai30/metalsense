from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DATASET_SCHEMA_VERSION = 1
EXPORT_SCHEMA_VERSION = "1"
EXPORT_SCHEMA_FIELD = "metalsense_schema_version"

EXPORT_COLUMNS = [
    EXPORT_SCHEMA_FIELD,
    "dataset_id",
    "dataset_filename",
    "exported_at",
    "data_source",
    "laboratory_organization",
    "report_id",
    "analytical_method",
    "detection_limit",
    "sample_id",
    "date",
    "latitude",
    "longitude",
    "country",
    "region",
    "area",
    "water_body",
    "standard",
    "authority",
    "hpi",
    "hei",
    "cd",
    "status",
    "highest_metal",
    "measurements_json",
    "qualified_measurements_json",
]

METAL_SYMBOLS = {
    "pb": "Pb",
    "cd": "Cd",
    "as": "As",
    "cr": "Cr",
    "hg": "Hg",
    "ni": "Ni",
    "cu": "Cu",
    "zn": "Zn",
    "fe": "Fe",
    "mn": "Mn",
}


class DatasetAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow")

    hpi: float | None = None
    hei: float | None = None
    cd: float | None = None
    status: str = "UNKNOWN"
    metals: list[dict[str, Any]] = Field(default_factory=list)
    highest_metal: str | None = None


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    sample_id: str
    date: Any | None = None
    latitude: float | None = None
    longitude: float | None = None
    country: str = "Unknown"
    region: str = "Unknown"
    area: str = "Unknown"
    water_body: str = "Unknown"
    standard: str | None = None
    authority: str | None = None
    analysis: DatasetAnalysis
    qualified_measurements: list[dict[str, Any]] = Field(default_factory=list)


class DatasetDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int = DATASET_SCHEMA_VERSION
    dataset_id: str
    user_id: str
    filename: str
    file_type: str
    imported_at: str
    source_type: str
    columns: list[str] = Field(default_factory=list)
    records: list[DatasetRecord] = Field(default_factory=list)
    quality: dict[str, Any] = Field(default_factory=dict)
    ml: dict[str, Any] = Field(default_factory=dict)
    data_source: str | None = None
    laboratory_organization: str | None = None
    report_id: str | None = None
    analytical_method: str | None = None
    detection_limit: str | None = None


def validate_dataset_document(dataset: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a newly persisted dataset document."""

    normalized = {
        **dataset,
        "schema_version": DATASET_SCHEMA_VERSION,
    }
    return DatasetDocument.model_validate(normalized).model_dump(mode="python")


def _analysis_for(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("analysis")
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _json_list(value: Any) -> str:
    return json.dumps(
        _list_of_dicts(value),
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def build_dataset_export_csv(dataset: dict[str, Any]) -> str:
    """Serialize one MongoDB dataset using the stable MetalSense CSV schema."""

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=EXPORT_COLUMNS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()

    exported_at = datetime.now(timezone.utc).isoformat()

    for record in dataset.get("records", []):
        if not isinstance(record, dict):
            continue

        analysis = _analysis_for(record)
        writer.writerow(
            {
                EXPORT_SCHEMA_FIELD: EXPORT_SCHEMA_VERSION,
                "dataset_id": dataset.get("dataset_id", ""),
                "dataset_filename": dataset.get("filename", ""),
                "exported_at": exported_at,
                "data_source": dataset.get("data_source", ""),
                "laboratory_organization": dataset.get(
                    "laboratory_organization",
                    "",
                ),
                "report_id": dataset.get("report_id", ""),
                "analytical_method": dataset.get("analytical_method", ""),
                "detection_limit": dataset.get("detection_limit", ""),
                "sample_id": record.get("sample_id", ""),
                "date": record.get("date") or "",
                "latitude": record.get("latitude"),
                "longitude": record.get("longitude"),
                "country": record.get("country", ""),
                "region": record.get("region", ""),
                "area": record.get("area", ""),
                "water_body": record.get("water_body", ""),
                "standard": record.get("standard", ""),
                "authority": record.get("authority", ""),
                "hpi": analysis.get("hpi"),
                "hei": analysis.get("hei"),
                "cd": analysis.get("cd"),
                "status": analysis.get("status", "UNKNOWN"),
                "highest_metal": analysis.get("highest_metal") or "",
                "measurements_json": _json_list(analysis.get("metals")),
                "qualified_measurements_json": _json_list(
                    record.get("qualified_measurements")
                ),
            }
        )

    return output.getvalue()


def _decode_csv(raw: bytes) -> list[list[str]]:
    text = raw.decode("utf-8-sig", errors="strict")
    return list(csv.reader(io.StringIO(text)))


def is_schema_export(raw: bytes) -> bool:
    try:
        rows = _decode_csv(raw)
    except (UnicodeDecodeError, csv.Error):
        return False

    return bool(rows and rows[0] and rows[0][0].strip() == EXPORT_SCHEMA_FIELD)


def is_frontend_report_export(raw: bytes) -> bool:
    """Detect the report CSV generated by the pre-schema frontend."""

    try:
        rows = _decode_csv(raw)
    except (UnicodeDecodeError, csv.Error):
        return False

    return bool(rows and rows[0] and rows[0][0].strip().lower() == "metalsense report")


def _number(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        result = float(value)
        return result if result == result else None
    except (TypeError, ValueError):
        return None


def _parse_json_list(value: str, field: str) -> list[dict[str, Any]]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid {field} value in MetalSense export.") from exc

    if not isinstance(parsed, list) or not all(
        isinstance(item, dict) for item in parsed
    ):
        raise ValueError(f"{field} must contain a JSON array of objects.")

    return parsed


def parse_schema_export(raw: bytes) -> dict[str, Any]:
    """Parse the canonical versioned MetalSense CSV schema."""

    text = raw.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("MetalSense export is missing its header row.")

    missing = [column for column in EXPORT_COLUMNS if column not in reader.fieldnames]
    if missing:
        raise ValueError(
            "MetalSense export is missing required columns: " + ", ".join(missing)
        )

    records: list[dict[str, Any]] = []
    first_row: dict[str, str] | None = None

    for row_number, row in enumerate(reader, start=2):
        if row.get(EXPORT_SCHEMA_FIELD) != EXPORT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported MetalSense schema version on row {row_number}."
            )

        if first_row is None:
            first_row = row

        measurements = _parse_json_list(
            row.get("measurements_json", ""),
            "measurements_json",
        )
        qualified_measurements = _parse_json_list(
            row.get("qualified_measurements_json", ""),
            "qualified_measurements_json",
        )

        records.append(
            {
                "sample_id": row.get("sample_id", "").strip(),
                "date": row.get("date") or None,
                "latitude": _number(row.get("latitude")),
                "longitude": _number(row.get("longitude")),
                "country": row.get("country") or "Unknown",
                "region": row.get("region") or "Unknown",
                "area": row.get("area") or "Unknown",
                "water_body": row.get("water_body") or "Unknown",
                "geo_source": "Imported MetalSense schema export",
                "standard": row.get("standard") or None,
                "authority": row.get("authority") or None,
                "standard_reason": "Imported from a MetalSense schema export.",
                "analysis": {
                    "hpi": _number(row.get("hpi")),
                    "hei": _number(row.get("hei")),
                    "cd": _number(row.get("cd")),
                    "status": (row.get("status") or "UNKNOWN").strip().upper(),
                    "highest_metal": row.get("highest_metal") or None,
                    "metals": measurements,
                },
                "qualified_measurements": qualified_measurements,
            }
        )

    if not records or first_row is None:
        raise ValueError("MetalSense export contains no dataset records.")

    return {
        "records": records,
        "columns": list(reader.fieldnames),
        "source_type": "metalsense_export",
        "source_application": "MetalSense",
        "source_dataset": first_row.get("dataset_filename") or None,
        "source_export_date": first_row.get("exported_at") or None,
        "source_schema_version": EXPORT_SCHEMA_VERSION,
    }


def parse_frontend_report_export(raw: bytes) -> dict[str, Any]:
    """Parse CSV reports produced before the versioned schema was introduced."""

    rows = _decode_csv(raw)
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if "analysis_status" in row
            and "analysis_hpi" in row
            and "sample_id" in {column.strip().lower() for column in row}
        ),
        None,
    )

    if header_index is None:
        raise ValueError("MetalSense report is missing its dataset header row.")

    headers = rows[header_index]
    metadata = {
        row[0].strip().lower(): row[1].strip()
        for row in rows[1:header_index]
        if len(row) >= 2 and row[0].strip()
    }
    records: list[dict[str, Any]] = []

    for values in rows[header_index + 1 :]:
        if not values or not any(value.strip() for value in values):
            continue

        padded = values + [""] * max(0, len(headers) - len(values))
        row = dict(zip(headers, padded, strict=False))
        normalized = {key.strip().lower(): value for key, value in row.items()}

        measurements = []
        for key, value in normalized.items():
            symbol = METAL_SYMBOLS.get(key)
            measured = _number(value)
            if symbol and measured is not None:
                measurements.append(
                    {
                        "metal": symbol,
                        "measured": measured,
                        "numeric_value": measured,
                        "calculation_value": measured,
                    }
                )

        records.append(
            {
                "sample_id": normalized.get("sample_id", "").strip(),
                "date": normalized.get("date") or None,
                "latitude": _number(normalized.get("latitude")),
                "longitude": _number(normalized.get("longitude")),
                "country": normalized.get("country") or "Unknown",
                "region": normalized.get("region") or "Unknown",
                "area": normalized.get("area") or "Unknown",
                "water_body": normalized.get("water_body") or "Unknown",
                "geo_source": "Imported legacy MetalSense report",
                "standard": normalized.get("standard") or None,
                "authority": normalized.get("authority") or None,
                "standard_reason": "Imported from a legacy MetalSense report.",
                "analysis": {
                    "hpi": _number(normalized.get("analysis_hpi")),
                    "hei": _number(normalized.get("analysis_hei")),
                    "cd": _number(normalized.get("analysis_cd")),
                    "status": (normalized.get("analysis_status") or "UNKNOWN")
                    .strip()
                    .upper(),
                    "highest_metal": None,
                    "metals": measurements,
                },
                "qualified_measurements": measurements,
            }
        )

    if not records:
        raise ValueError("MetalSense report contains no dataset records.")

    return {
        "records": records,
        "columns": headers,
        "source_type": "metalsense_export",
        "source_application": "MetalSense",
        "source_dataset": metadata.get("dataset"),
        "source_export_date": None,
        "source_schema_version": "legacy-report",
    }
