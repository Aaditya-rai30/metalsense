from __future__ import annotations

from schemas.dataset_schema import (
    DATASET_SCHEMA_VERSION,
    EXPORT_SCHEMA_FIELD,
    build_dataset_export_csv,
    is_frontend_report_export,
    is_schema_export,
    parse_frontend_report_export,
    parse_schema_export,
    validate_dataset_document,
)


def sample_dataset():
    measurement = {
        "metal": "Pb",
        "measured": 0.01,
        "numeric_value": 0.01,
        "calculation_value": 0.01,
        "ratio": 1.0,
    }
    return {
        "dataset_id": "dataset-1",
        "user_id": "user-1",
        "filename": "water.csv",
        "file_type": "CSV",
        "imported_at": "2026-08-24T00:00:00+00:00",
        "source_type": "raw_measurements",
        "data_source": "Lab upload",
        "laboratory_organization": "MetalSense Lab",
        "report_id": "REPORT-1",
        "analytical_method": "ICP-MS",
        "detection_limit": "0.001 mg/L",
        "columns": ["Sample_ID", "Pb"],
        "quality": {"score": 100},
        "records": [
            {
                "sample_id": "S001",
                "date": "2026-08-24",
                "latitude": 19.076,
                "longitude": 72.877,
                "country": "India",
                "region": "Maharashtra",
                "area": "Mumbai",
                "water_body": "Lake",
                "standard": "BIS IS 10500:2012",
                "authority": "BIS",
                "analysis": {
                    "hpi": 31.39,
                    "hei": 1.88,
                    "cd": 0.0,
                    "status": "LOW",
                    "highest_metal": "Pb",
                    "metals": [measurement],
                },
                "qualified_measurements": [measurement],
            }
        ],
    }


def test_dataset_schema_normalizes_new_documents():
    dataset = validate_dataset_document(sample_dataset())

    assert dataset["schema_version"] == DATASET_SCHEMA_VERSION
    assert dataset["records"][0]["analysis"]["status"] == "LOW"
    assert dataset["records"][0]["analysis"]["metals"][0]["metal"] == "Pb"


def test_versioned_csv_round_trip_preserves_service_data():
    exported = build_dataset_export_csv(sample_dataset()).encode()

    assert exported.decode().startswith(EXPORT_SCHEMA_FIELD)
    assert is_schema_export(exported)

    parsed = parse_schema_export(exported)
    record = parsed["records"][0]

    assert parsed["source_schema_version"] == "1"
    assert record["sample_id"] == "S001"
    assert record["analysis"]["hpi"] == 31.39
    assert record["analysis"]["metals"][0]["metal"] == "Pb"
    assert record["qualified_measurements"][0]["calculation_value"] == 0.01


def test_existing_frontend_report_is_still_importable():
    report = b""""MetalSense report","",""
"Dataset","water.csv",""
"User","Test User",""

"Sample_ID","Country","Latitude","Longitude","Pb","analysis_status","analysis_hpi","analysis_hei","analysis_cd"
"S001","India","19.076","72.877","0.01","LOW","31.39","1.88","0"
"""

    assert is_frontend_report_export(report)

    parsed = parse_frontend_report_export(report)
    record = parsed["records"][0]

    assert record["sample_id"] == "S001"
    assert record["analysis"]["status"] == "LOW"
    assert record["analysis"]["metals"][0] == {
        "metal": "Pb",
        "measured": 0.01,
        "numeric_value": 0.01,
        "calculation_value": 0.01,
    }
