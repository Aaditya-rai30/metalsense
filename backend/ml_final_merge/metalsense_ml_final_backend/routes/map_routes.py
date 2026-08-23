from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from security.auth import require_current_user
from security.rate_limit import rate_limit_api

from services.map_service import (
    get_map_points,
    get_map_summary,
    get_hotspots,
    get_nearby_samples,
    get_ml_spatial_summary,
)


router = APIRouter(
    tags=["Map"],
    dependencies=[Depends(rate_limit_api)],
)


@router.get("/{dataset_id}/points", summary="Get Map Points")
async def points(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_map_points(dataset_id, user["user_id"])


@router.get("/{dataset_id}/summary", summary="Get Map Summary")
async def summary(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_map_summary(dataset_id, user["user_id"])


@router.get("/{dataset_id}/hotspots", summary="Get Map Hotspots")
async def hotspots(
    dataset_id: str,
    radius_km: float = Query(5.0, gt=0, le=500),
    user: dict = Depends(require_current_user),
):
    return await get_hotspots(dataset_id, user["user_id"], radius_km)


@router.get("/{dataset_id}/nearby", summary="Get Nearby Samples")
async def nearby(
    dataset_id: str,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=500),
    user: dict = Depends(require_current_user),
):
    return await get_nearby_samples(
        dataset_id,
        user["user_id"],
        latitude,
        longitude,
        radius_km,
    )


@router.get("/{dataset_id}/ml-summary", summary="Get ML Spatial Summary")
async def ml_summary(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_ml_spatial_summary(
        dataset_id,
        user["user_id"],
    )
