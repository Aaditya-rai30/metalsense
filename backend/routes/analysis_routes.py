from __future__ import annotations

from fastapi import APIRouter, Depends

from security.auth import require_current_user

from services.analysis_service import (
    get_analysis,
    get_summary,
    get_metal_analysis,
    get_spatial_data,
)


router = APIRouter(
    tags=["Analysis"],
)


# ============================================================
# FULL ANALYSIS
# ============================================================

@router.get(
    "/{dataset_id}",
    summary="Get Full Dataset Analysis",
)
async def analysis(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    """
    Return the complete analysis for a dataset.

    The authenticated user's ID is passed to every
    service operation so dataset ownership can be enforced.
    """

    user_id = user["user_id"]

    return {
        "dataset_id": dataset_id,

        "summary": await get_summary(
            dataset_id,
            user_id,
        ),

        "metals": await get_metal_analysis(
            dataset_id,
            user_id,
        ),

        "spatial": await get_spatial_data(
            dataset_id,
            user_id,
        ),
    }


# ============================================================
# SUMMARY
# ============================================================

@router.get(
    "/{dataset_id}/summary",
    summary="Get Analysis Summary",
)
async def summary(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_summary(
        dataset_id,
        user["user_id"],
    )


# ============================================================
# METALS
# ============================================================

@router.get(
    "/{dataset_id}/metals",
    summary="Get Metal Analysis",
)
async def metals(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_metal_analysis(
        dataset_id,
        user["user_id"],
    )


# ============================================================
# SPATIAL
# ============================================================

@router.get(
    "/{dataset_id}/spatial",
    summary="Get Spatial Analysis",
)
async def spatial(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_spatial_data(
        dataset_id,
        user["user_id"],
    )