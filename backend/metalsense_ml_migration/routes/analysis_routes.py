from __future__ import annotations

from fastapi import APIRouter, Depends

from security.auth import require_current_user
from security.rate_limit import rate_limit_api
from services.analysis_service import get_analysis, get_summary, get_metal_analysis, get_spatial_data

router = APIRouter(tags=["Analysis"], dependencies=[Depends(rate_limit_api)])

@router.get("/{dataset_id}")
async def analysis(dataset_id: str, user: dict = Depends(require_current_user)):
    return {
        "dataset_id": dataset_id,
        "summary": await get_summary(dataset_id, user["user_id"]),
        "metals": await get_metal_analysis(dataset_id, user["user_id"]),
        "spatial": await get_spatial_data(dataset_id, user["user_id"]),
    }

@router.get("/{dataset_id}/summary")
async def summary(dataset_id: str, user: dict = Depends(require_current_user)):
    return await get_summary(dataset_id, user["user_id"])

@router.get("/{dataset_id}/metals")
async def metals(dataset_id: str, user: dict = Depends(require_current_user)):
    return await get_metal_analysis(dataset_id, user["user_id"])

@router.get("/{dataset_id}/spatial")
async def spatial(dataset_id: str, user: dict = Depends(require_current_user)):
    return await get_spatial_data(dataset_id, user["user_id"])
