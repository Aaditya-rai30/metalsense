from fastapi import APIRouter, Header

from services.auth_service import get_current_user
from services.analysis_service import (
    get_analysis,
    get_summary,
    get_metal_analysis,
    get_spatial_data,
)


router = APIRouter(
    tags=["Analysis"],
)


async def require_user(
    authorization: str | None,
):
    return await get_current_user(
        authorization
    )


# ============================================================
# FULL ANALYSIS
# ============================================================

@router.get(
    "/{dataset_id}"
)
async def analysis(
    dataset_id: str,
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return {
        "dataset_id":
            dataset_id,

        "summary":
            await get_summary(
                dataset_id,
                user["user_id"],
            ),

        "metals":
            await get_metal_analysis(
                dataset_id,
                user["user_id"],
            ),

        "spatial":
            await get_spatial_data(
                dataset_id,
                user["user_id"],
            ),
    }


# ============================================================
# SUMMARY
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

    return await get_summary(
        dataset_id,
        user["user_id"],
    )


# ============================================================
# METALS
# ============================================================

@router.get(
    "/{dataset_id}/metals"
)
async def metals(
    dataset_id: str,
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return await get_metal_analysis(
        dataset_id,
        user["user_id"],
    )


# ============================================================
# SPATIAL
# ============================================================

@router.get(
    "/{dataset_id}/spatial"
)
async def spatial(
    dataset_id: str,
    authorization: str | None = Header(
        default=None
    ),
):
    user = await require_user(
        authorization
    )

    return await get_spatial_data(
        dataset_id,
        user["user_id"],
    )
