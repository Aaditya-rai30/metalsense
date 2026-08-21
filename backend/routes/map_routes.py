from fastapi import (
    APIRouter,
    Header,
    Query,
)

from services.auth_service import (
    get_current_user,
)

from services.map_service import (
    get_map_points,
    get_map_summary,
    get_hotspots,
    get_nearby_samples,
)


router = APIRouter(
    tags=["Map"],
)

async def require_user(
    authorization: str | None,
):
    return await get_current_user(
        authorization
    )


# ============================================================
# MAP POINTS
# ============================================================

@router.get(
    "/{dataset_id}/points"
)
async def points(
    dataset_id: str,
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return await get_map_points(
        dataset_id,
        user["user_id"],
    )


# ============================================================
# MAP SUMMARY
# ============================================================

@router.get(
    "/{dataset_id}/summary"
)
async def summary(
    dataset_id: str,
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return await get_map_summary(
        dataset_id,
        user["user_id"],
    )


# ============================================================
# HOTSPOTS
# ============================================================

@router.get(
    "/{dataset_id}/hotspots"
)
async def hotspots(
    dataset_id: str,
    radius_km: float = Query(
        default=5.0,
        gt=0,
        le=100,
    ),
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return await get_hotspots(
        dataset_id,
        user["user_id"],
        radius_km,
    )


# ============================================================
# NEARBY
# ============================================================

@router.get(
    "/{dataset_id}/nearby"
)
async def nearby(
    dataset_id: str,
    latitude: float,
    longitude: float,
    radius_km: float = Query(
        default=10.0,
        gt=0,
        le=100,
    ),
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return await get_nearby_samples(
        dataset_id,
        user["user_id"],
        latitude,
        longitude,
        radius_km,
    )
