from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from security.auth import require_current_user

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


# ============================================================
# IMPORT DATASET
# ============================================================

@router.post(
    "/import",
    summary="Upload Dataset",
)
async def upload_dataset(
    file: UploadFile = File(...),

    data_source: str = Form(...),
    laboratory_organization: str = Form(...),
    report_id: str = Form(...),
    analytical_method: str = Form(...),
    detection_limit: str = Form(...),

    user: dict = Depends(require_current_user),
):
    """
    Upload CSV/XLS/XLSX dataset.

    Authentication is required.

    Import metadata is mandatory and must be supplied
    together with the uploaded file.
    """

    metadata = {
        "data_source": data_source.strip(),
        "laboratory_organization":
            laboratory_organization.strip(),
        "report_id":
            report_id.strip(),
        "analytical_method":
            analytical_method.strip(),
        "detection_limit":
            detection_limit.strip(),
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
                "message":
                    "All import metadata fields are required.",
                "missing_fields": missing,
            },
        )

    return await import_dataset(
        file=file,
        user=user,
        import_metadata=metadata,
    )


# ============================================================
# LIST DATASETS
# ============================================================

@router.get(
    "",
    summary="Get Datasets",
)
async def get_datasets(
    user: dict = Depends(require_current_user),
):
    """
    Return only datasets belonging to the authenticated user.
    """

    return await list_datasets(
        user
    )


# ============================================================
# DELETE ALL DATASETS
# ============================================================

@router.delete(
    "",
    summary="Remove All Datasets",
)
async def remove_all_datasets(
    user: dict = Depends(require_current_user),
):
    """
    Delete all datasets belonging to the authenticated user.
    """

    return await clear_datasets(
        user
    )


# ============================================================
# DELETE ONE DATASET
# ============================================================

@router.delete(
    "/{dataset_id}",
    summary="Remove Dataset",
)
async def remove_dataset(
    dataset_id: str,

    user: dict = Depends(require_current_user),
):
    """
    Delete a dataset only if it belongs to the
    authenticated user.
    """

    return await delete_dataset(
        dataset_id,
        user,
    )