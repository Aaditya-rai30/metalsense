from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)

from security.auth import require_current_user
from security.rate_limit import rate_limit_api

from services.dataset_service import (
    import_dataset,
    list_datasets,
    delete_dataset,
    clear_datasets,
)


router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


@router.post("/import", summary="Upload Dataset")
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    data_source: str = Form(...),
    laboratory_organization: str = Form(...),
    report_id: str = Form(...),
    analytical_method: str = Form(...),
    detection_limit: str = Form(...),
    user: dict = Depends(require_current_user),
):
    rate_limit_api(request)

    metadata = {
        "data_source": data_source.strip(),
        "laboratory_organization": laboratory_organization.strip(),
        "report_id": report_id.strip(),
        "analytical_method": analytical_method.strip(),
        "detection_limit": detection_limit.strip(),
    }

    missing = [
        field for field, value in metadata.items()
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

    return await import_dataset(
        file=file,
        user=user,
        import_metadata=metadata,
    )


@router.get("", summary="Get Datasets")
async def get_datasets(
    user: dict = Depends(require_current_user),
):
    return await list_datasets(user)


@router.delete("", summary="Remove All Datasets")
async def remove_all_datasets(
    user: dict = Depends(require_current_user),
):
    return await clear_datasets(user)


@router.delete("/{dataset_id}", summary="Remove Dataset")
async def remove_dataset(
    dataset_id: str,
    user: dict = Depends(require_current_user),
):
    return await delete_dataset(dataset_id, user)
