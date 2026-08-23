from __future__ import annotations

import math

from fastapi import HTTPException

from database import db
from engine.spatial_engine import SpatialEngine
from services.analysis_service import (
    get_analysis,
    get_hpi,
    get_hei,
    get_cd,
    get_status,
)


_spatial_engine = SpatialEngine()

# ============================================================
# HELPERS
# ============================================================

def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate great-circle distance between two coordinates.
    """

    radius_km = 6371.0088

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(
        lat2 - lat1
    )

    delta_lon = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )

    return (
        2
        * radius_km
        * math.asin(
            math.sqrt(a)
        )
    )


def risk_score(
    status: str,
    hpi,
    hei,
    cd,
) -> float:
    """
    Produce a deterministic spatial risk score.

    Status gets the primary weight.
    HPI/HEI/Cd are used when available.
    """

    status_weights = {
        "SAFE": 0.0,
        "LOW": 25.0,
        "MODERATE": 50.0,
        "HIGH": 75.0,
        "CRITICAL": 100.0,
        "UNKNOWN": 0.0,
    }

    status_score = status_weights.get(
        status,
        0.0,
    )

    values = []

    for value in (
        hpi,
        hei,
        cd,
    ):

        try:

            if value is not None:
                values.append(
                    float(value)
                )

        except (
            TypeError,
            ValueError,
        ):
            pass

    if not values:
        return status_score

    # Normalize each metric to a 0-100-ish contribution.
    hpi_component = min(
        max(
            float(hpi or 0),
            0,
        ),
        200,
    ) / 2

    hei_component = min(
        max(
            float(hei or 0),
            0,
        ),
        20,
    ) * 5

    cd_component = min(
        max(
            float(cd or 0),
            0,
        ),
        20,
    ) * 5

    index_score = (
        hpi_component * 0.50
        + hei_component * 0.25
        + cd_component * 0.25
    )

    return round(
        max(
            status_score,
            index_score,
        ),
        2,
    )


def build_point(
    record: dict,
) -> dict | None:

    try:

        latitude = float(
            record.get("latitude")
        )

        longitude = float(
            record.get("longitude")
        )

    except (
        TypeError,
        ValueError,
    ):

        return None

    hpi = get_hpi(record)
    hei = get_hei(record)
    cd = get_cd(record)
    status = get_status(record)

    return {
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

        "season":
            record.get("season"),

        "date_inferred":
            bool(record.get("date_inferred", False)),

        "hpi":
            hpi,

        "hei":
            hei,

        "cd":
            cd,

        "status":
            status,

        "highest_metal":
            (
                record.get(
                    "analysis",
                    {},
                ).get(
                    "highest_metal"
                )
                if isinstance(
                    record.get(
                        "analysis",
                    ),
                    dict,
                )
                else None
            ),

        "standard":
            record.get(
                "standard"
            ),

        "authority":
            record.get(
                "authority"
            ),

        "risk_score":
            risk_score(
                status,
                hpi,
                hei,
                cd,
            ),
    }


# ============================================================
# MAP POINTS
# ============================================================

async def get_map_points(
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

        point = build_point(
            record
        )

        if point is not None:
            points.append(
                point
            )

    return {
        "dataset_id":
            dataset_id,

        "points":
            points,

        "count":
            len(points),
    }


# ============================================================
# MAP SUMMARY
# ============================================================

async def get_map_summary(
    dataset_id: str,
    user_id: str,
):
    result = await get_map_points(
        dataset_id,
        user_id,
    )

    points = result["points"]

    if not points:
        return {
            "dataset_id":
                dataset_id,

            "count":
                0,

            "high_risk_count":
                0,

            "moderate_count":
                0,

            "low_risk_count":
                0,

            "safe_count":
                0,

            "center":
                None,

            "bounds":
                None,
        }

    high_risk = [
        point
        for point in points
        if point["status"]
        in {
            "HIGH",
            "CRITICAL",
        }
    ]

    moderate = [
        point
        for point in points
        if point["status"]
        == "MODERATE"
    ]

    low = [
        point
        for point in points
        if point["status"]
        == "LOW"
    ]

    safe = [
        point
        for point in points
        if point["status"]
        == "SAFE"
    ]

    latitudes = [
        point["latitude"]
        for point in points
    ]

    longitudes = [
        point["longitude"]
        for point in points
    ]

    min_lat = min(latitudes)
    max_lat = max(latitudes)

    min_lon = min(longitudes)
    max_lon = max(longitudes)

    center = {
        "latitude":
            round(
                sum(latitudes)
                / len(latitudes),
                6,
            ),

        "longitude":
            round(
                sum(longitudes)
                / len(longitudes),
                6,
            ),
    }

    return {
        "dataset_id":
            dataset_id,

        "count":
            len(points),

        "high_risk_count":
            len(high_risk),

        "moderate_count":
            len(moderate),

        "low_risk_count":
            len(low),

        "safe_count":
            len(safe),

        "center":
            center,

        "bounds": {
            "north":
                max_lat,

            "south":
                min_lat,

            "east":
                max_lon,

            "west":
                min_lon,
        },
    }


# ============================================================
# HOTSPOT DETECTION
# ============================================================

async def get_hotspots(
    dataset_id: str,
    user_id: str,
    radius_km: float = 5.0,
):
    dataset = await get_analysis(dataset_id, user_id)
    return _spatial_engine.hotspots(
        dataset.get("records", []),
        dataset_id,
        radius_km,
    )


# ============================================================
# NEARBY SAMPLES
# ============================================================

async def get_nearby_samples(
    dataset_id: str,
    user_id: str,
    latitude: float,
    longitude: float,
    radius_km: float = 10.0,
):
    result = await get_map_points(
        dataset_id,
        user_id,
    )

    nearby = []

    for point in result["points"]:

        distance = haversine_km(
            latitude,
            longitude,
            point["latitude"],
            point["longitude"],
        )

        if distance <= radius_km:

            item = dict(point)

            item[
                "distance_km"
            ] = round(
                distance,
                3,
            )

            nearby.append(
                item
            )

    nearby.sort(
        key=lambda item:
            item["distance_km"]
    )

    return {
        "dataset_id":
            dataset_id,

        "origin": {
            "latitude":
                latitude,

            "longitude":
                longitude,
        },

        "radius_km":
            radius_km,

        "samples":
            nearby,

        "count":
            len(nearby),
    }


async def get_ml_spatial_summary(
    dataset_id: str,
    user_id: str,
):
    dataset = await get_analysis(dataset_id, user_id)
    return _spatial_engine.summary(
        dataset.get("records", []),
        dataset_id,
    )
