from __future__ import annotations

import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import Response

from security.auth import require_current_user
from security.rate_limit import rate_limit_api

from services.dataset_service import (
    import_dataset,
    list_datasets,
    export_dataset,
    delete_dataset,
    clear_datasets,
)


router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


@router.post(
    "/import",
    summary="Upload Dataset",
)
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    data_source: str = Form(...),
    laboratory_organization: str = Form(...),
    report_id: str = Form(...),
    analytical_method: str = Form(...),
    detection_limit: str = Form(...),
    location_overrides: str | None = Form(None),
    user: dict = Depends(require_current_user),
):
    """Upload a dataset, optionally with user-confirmed PDF coordinates."""

    rate_limit_api(request)

    metadata = {
        "data_source": data_source.strip(),
        "laboratory_organization": laboratory_organization.strip(),
        "report_id": report_id.strip(),
        "analytical_method": analytical_method.strip(),
        "detection_limit": detection_limit.strip(),
    }

    missing = [
        field
        for field, value in metadata.items()
        if not value
    ]

    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "All import metadata fields are required.",
                "missing_fields": missing,
            },
        )

    # Coordinates confirmed in the Location Review modal arrive as JSON.
    if location_overrides:
        try:
            parsed_overrides = json.loads(location_overrides)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid location_overrides payload.",
            ) from exc

        if not isinstance(parsed_overrides, dict):
            raise HTTPException(
                status_code=422,
                detail="location_overrides must be a JSON object.",
            )

        metadata["location_overrides"] = parsed_overrides
    else:
        metadata["location_overrides"] = {}

    return await import_dataset(
        file=file,
        user=user,
        import_metadata=metadata,
    )


@router.get("")
async def get_datasets(
    user: dict = Depends(require_current_user),
):
    return await list_datasets(user)


@router.get("/{dataset_id}/export")
async def download_dataset(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    csv_content = await export_dataset(
        dataset_id,
        user,
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="metalsense-{dataset_id}.csv"'
            ),
        },
    )


@router.delete("")
async def remove_all_datasets(
    user: dict = Depends(require_current_user),
):
    return await clear_datasets(user)


@router.delete("/{dataset_id}")
async def remove_dataset(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await delete_dataset(dataset_id, user)
