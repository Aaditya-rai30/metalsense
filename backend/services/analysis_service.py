from __future__ import annotations

import logging

from fastapi import HTTPException

from database import db


logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def number(value):
    try:
        if value is None or value == "":
            return None

        value = float(value)

        if value != value:
            return None

        return value

    except (TypeError, ValueError):
        return None


def get_record_analysis(record: dict) -> dict:
    """
    Get the persisted analysis object regardless of whether
    the record uses the current or legacy key.
    """

    for key in (
        "analysis",
        "Analysis",
        "result",
        "results",
    ):
        value = record.get(key)

        if isinstance(value, dict):
            return value

    return {}


def get_hpi(record: dict):
    analysis = get_record_analysis(record)

    for value in (
        analysis.get("hpi"),
        analysis.get("HPI"),
        record.get("hpi"),
        record.get("HPI"),
    ):
        value = number(value)

        if value is not None:
            return value

    return None


def get_hei(record: dict):
    analysis = get_record_analysis(record)

    for value in (
        analysis.get("hei"),
        analysis.get("HEI"),
        record.get("hei"),
        record.get("HEI"),
    ):
        value = number(value)

        if value is not None:
            return value

    return None


def get_cd(record: dict):
    analysis = get_record_analysis(record)

    for value in (
        analysis.get("cd"),
        analysis.get("Cd"),
        record.get("cd"),
        record.get("Cd"),
    ):
        value = number(value)

        if value is not None:
            return value

    return None


def get_status(record: dict) -> str:
    analysis = get_record_analysis(record)

    value = (
        analysis.get("status")
        or analysis.get("Status")
        or record.get("status")
        or record.get("Status")
        or "UNKNOWN"
    )

    return str(value).strip().upper()


def get_measurements(record: dict) -> list:
    analysis = get_record_analysis(record)

    for value in (
        analysis.get("metals"),
        analysis.get("measurements"),
        analysis.get("qualified_measurements"),
        record.get("metals"),
        record.get("measurements"),
        record.get("qualified_measurements"),
    ):
        if isinstance(value, list):
            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

    return []


def get_measurement_metal(
    measurement: dict,
):
    value = (
        measurement.get("metal")
        or measurement.get("Metal")
        or measurement.get("symbol")
        or measurement.get("Symbol")
    )

    if value is None:
        return None

    return str(value).strip()


def get_measurement_value(
    measurement: dict,
):
    for value in (
        measurement.get("calculation_value"),
        measurement.get("numeric_value"),
        measurement.get("measured"),
        measurement.get("value"),
    ):
        value = number(value)

        if value is not None:
            return value

    return None


def get_measurement_ratio(
    measurement: dict,
):
    for value in (
        measurement.get("ratio"),
        measurement.get("Ratio"),
    ):
        value = number(value)

        if value is not None:
            return value

    return None


def get_measurement_exceedance(
    measurement: dict,
):
    for value in (
        measurement.get("exceedance"),
        measurement.get("Exceedance"),
        measurement.get("exceedance_percent"),
    ):
        value = number(value)

        if value is not None:
            return value

    return None


# ============================================================
# DATASET LOOKUP
# ============================================================

async def get_analysis(
    dataset_id: str,
    user_id: str,
):
    """
    Resolve a dataset by immutable dataset_id first.

    Then verify that the dataset belongs to the authenticated
    user.

    This avoids false 404s caused by an overly restrictive
    MongoDB query while retaining ownership protection.
    """

    logger.info(
        "Analysis lookup: dataset_id=%s user_id=%s",
        dataset_id,
        user_id,
    )

    # --------------------------------------------------------
    # First lookup by dataset ID only.
    # --------------------------------------------------------

    dataset = await db.datasets.find_one(
        {
            "dataset_id": str(
                dataset_id
            ),
        },
        {
            "_id": 0,
        },
    )

    if dataset is None:

        logger.warning(
            "Analysis dataset not found: %s",
            dataset_id,
        )

        raise HTTPException(
            status_code=404,
            detail=(
                f"Dataset not found: {dataset_id}"
            ),
        )

    # --------------------------------------------------------
    # Verify ownership.
    # --------------------------------------------------------

    stored_user_id = str(
        dataset.get(
            "user_id",
            "",
        )
    )

    requested_user_id = str(
        user_id or ""
    )

    logger.info(
        "Analysis ownership: stored=%s requested=%s",
        stored_user_id,
        requested_user_id,
    )

    if stored_user_id != requested_user_id:

        logger.warning(
            "Analysis ownership mismatch for dataset %s",
            dataset_id,
        )

        raise HTTPException(
            status_code=404,
            detail="Dataset not found",
        )

    return dataset


# ============================================================
# SUMMARY
# ============================================================

async def get_summary(
    dataset_id: str,
    user_id: str,
):
    dataset = await get_analysis(
        dataset_id,
        user_id,
    )

    records = dataset.get(
        "records",
        [],
    )

    hpi_values = []
    hei_values = []
    cd_values = []
    statuses = []

    for record in records:

        if not isinstance(
            record,
            dict,
        ):
            continue

        hpi = get_hpi(record)
        hei = get_hei(record)
        cd = get_cd(record)
        status = get_status(record)

        if hpi is not None:
            hpi_values.append(hpi)

        if hei is not None:
            hei_values.append(hei)

        if cd is not None:
            cd_values.append(cd)

        if status != "UNKNOWN":
            statuses.append(status)

    high_samples = sum(
        1
        for status in statuses
        if status in {
            "HIGH",
            "CRITICAL",
        }
    )

    moderate_samples = sum(
        1
        for status in statuses
        if status == "MODERATE"
    )

    low_samples = sum(
        1
        for status in statuses
        if status == "LOW"
    )

    safe_samples = sum(
        1
        for status in statuses
        if status == "SAFE"
    )

    status_order = {
        "UNKNOWN": 0,
        "SAFE": 1,
        "LOW": 2,
        "MODERATE": 3,
        "HIGH": 4,
        "CRITICAL": 5,
    }

    overall_status = (
        max(
            statuses,
            key=lambda value:
                status_order.get(
                    value,
                    0,
                ),
        )
        if statuses
        else "UNKNOWN"
    )

    average_hpi = (
        round(
            sum(hpi_values)
            / len(hpi_values),
            2,
        )
        if hpi_values
        else None
    )

    average_hei = (
        round(
            sum(hei_values)
            / len(hei_values),
            2,
        )
        if hei_values
        else None
    )

    average_cd = (
        round(
            sum(cd_values)
            / len(cd_values),
            2,
        )
        if cd_values
        else None
    )

    max_hpi = (
        round(
            max(hpi_values),
            2,
        )
        if hpi_values
        else None
    )

    min_hpi = (
        round(
            min(hpi_values),
            2,
        )
        if hpi_values
        else None
    )

    quality = dataset.get(
        "quality",
        {},
    )

    quality_score = None

    if isinstance(
        quality,
        dict,
    ):
        quality_score = number(
            quality.get("score")
        )

    return {
        "dataset_id":
            dataset_id,

        "record_count":
            len(records),

        "analyzed_record_count":
            len(hpi_values),

        "average_hpi":
            average_hpi,

        "average_hei":
            average_hei,

        "average_cd":
            average_cd,

        "max_hpi":
            max_hpi,

        "min_hpi":
            min_hpi,

        "overall_status":
            overall_status,

        "high_samples":
            high_samples,

        "moderate_samples":
            moderate_samples,

        "low_samples":
            low_samples,

        "safe_samples":
            safe_samples,

        "quality_score":
            quality_score,

        "source_type":
            dataset.get(
                "source_type",
                "unknown",
            ),
    }


# ============================================================
# METAL ANALYSIS
# ============================================================

async def get_metal_analysis(
    dataset_id: str,
    user_id: str,
):
    dataset = await get_analysis(
        dataset_id,
        user_id,
    )

    records = dataset.get(
        "records",
        [],
    )

    metal_data = {}

    for record in records:

        measurements = get_measurements(
            record
        )

        for measurement in measurements:

            metal = get_measurement_metal(
                measurement
            )

            if not metal:
                continue

            metal_data.setdefault(
                metal,
                [],
            ).append(
                measurement
            )

    results = []

    for metal in sorted(
        metal_data.keys()
    ):

        measurements = metal_data[
            metal
        ]

        numeric_values = [
            get_measurement_value(
                measurement
            )
            for measurement in measurements
        ]

        numeric_values = [
            value
            for value in numeric_values
            if value is not None
        ]

        ratios = [
            get_measurement_ratio(
                measurement
            )
            for measurement in measurements
        ]

        ratios = [
            value
            for value in ratios
            if value is not None
        ]

        exceedances = [
            get_measurement_exceedance(
                measurement
            )
            for measurement in measurements
        ]

        exceedances = [
            value
            for value in exceedances
            if value is not None
        ]

        high_samples = 0

        for measurement in measurements:

            status = str(
                measurement.get(
                    "status",
                    "SAFE",
                )
            ).strip().upper()

            exceedance = (
                get_measurement_exceedance(
                    measurement
                )
            )

            if (
                status in {
                    "HIGH",
                    "CRITICAL",
                }
                or (
                    exceedance is not None
                    and exceedance > 0
                )
            ):
                high_samples += 1

        results.append(
            {
                "metal":
                    metal,

                "sample_count":
                    len(measurements),

                "average_measured":
                    (
                        round(
                            sum(numeric_values)
                            / len(
                                numeric_values
                            ),
                            6,
                        )
                        if numeric_values
                        else None
                    ),

                "maximum_measured":
                    (
                        round(
                            max(
                                numeric_values
                            ),
                            6,
                        )
                        if numeric_values
                        else None
                    ),

                "average_ratio":
                    (
                        round(
                            sum(ratios)
                            / len(ratios),
                            4,
                        )
                        if ratios
                        else None
                    ),

                "maximum_exceedance":
                    (
                        round(
                            max(
                                exceedances
                            ),
                            4,
                        )
                        if exceedances
                        else None
                    ),

                "high_samples":
                    high_samples,
            }
        )

    return {
        "dataset_id":
            dataset_id,

        "metals":
            results,

        "total_metals":
            len(results),
    }


# ============================================================
# SPATIAL
# ============================================================

async def get_spatial_data(
    dataset_id: str,
    user_id: str,
):
    dataset = await get_analysis(
        dataset_id,
        user_id,
    )

    records = dataset.get(
        "records",
        [],
    )

    points = []

    for record in records:

        latitude = number(
            record.get(
                "latitude"
            )
        )

        longitude = number(
            record.get(
                "longitude"
            )
        )

        if (
            latitude is None
            or longitude is None
        ):
            continue

        analysis = get_record_analysis(
            record
        )

        points.append(
            {
                "sample_id":
                    record.get(
                        "sample_id",
                        "Unknown",
                    ),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "country":
                    record.get(
                        "country",
                        "Unknown",
                    ),

                "region":
                    record.get(
                        "region",
                        "Unknown",
                    ),

                "area":
                    record.get(
                        "area",
                        "Unknown",
                    ),

                "date":
                    record.get(
                        "date"
                    ),

                "hpi":
                    get_hpi(
                        record
                    ),

                "hei":
                    get_hei(
                        record
                    ),

                "cd":
                    get_cd(
                        record
                    ),

                "status":
                    get_status(
                        record
                    ),

                "highest_metal":
                    analysis.get(
                        "highest_metal"
                    ),

                "standard":
                    record.get(
                        "standard"
                    ),

                "authority":
                    record.get(
                        "authority"
                    ),
            }
        )

    return {
        "dataset_id":
            dataset_id,

        "points":
            points,

        "count":
            len(points),
    }
