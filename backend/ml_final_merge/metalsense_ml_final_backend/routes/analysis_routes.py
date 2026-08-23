from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from security.auth import require_current_user
from security.rate_limit import rate_limit_api

from services.analysis_service import (
    get_analysis,
    get_summary,
    get_metal_analysis,
    get_spatial_data,
    get_ml_analysis,
    get_temporal_analysis,
    get_anomaly_analysis,
    get_explanations,
    get_rag_answer,
)


router = APIRouter(
    tags=["Analysis"],
    dependencies=[Depends(rate_limit_api)],
)


@router.get("/{dataset_id}", summary="Get Full Dataset Analysis")
async def analysis(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    user_id = user["user_id"]
    return {
        "dataset_id": dataset_id,
        "summary": await get_summary(dataset_id, user_id),
        "metals": await get_metal_analysis(dataset_id, user_id),
        "spatial": await get_spatial_data(dataset_id, user_id),
        "ml": await get_ml_analysis(dataset_id, user_id),
    }


@router.get("/{dataset_id}/summary", summary="Get Analysis Summary")
async def summary(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_summary(dataset_id, user["user_id"])


@router.get("/{dataset_id}/metals", summary="Get Metal Analysis")
async def metals(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_metal_analysis(dataset_id, user["user_id"])


@router.get("/{dataset_id}/spatial", summary="Get Spatial Analysis")
async def spatial(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_spatial_data(dataset_id, user["user_id"])


@router.get("/{dataset_id}/ml", summary="Get Final ML Analysis")
async def ml_analysis(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_ml_analysis(dataset_id, user["user_id"])


@router.get("/{dataset_id}/temporal", summary="Get Temporal Analysis")
async def temporal(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_temporal_analysis(dataset_id, user["user_id"])


@router.get("/{dataset_id}/anomalies", summary="Get ML Anomalies")
async def anomalies(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_anomaly_analysis(dataset_id, user["user_id"])


@router.get("/{dataset_id}/explanations", summary="Get Explainability")
async def explanations(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await get_explanations(dataset_id, user["user_id"])


@router.get("/{dataset_id}/rag", summary="Evidence Grounded RAG")
async def rag(
    dataset_id: str,
    question: str = Query(..., min_length=3, max_length=1000),
    top_k: int = Query(6, ge=1, le=12),
    user: dict = Depends(require_current_user),
):
    return await get_rag_answer(
        dataset_id,
        user["user_id"],
        question,
        top_k,
    )
