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


# ============================================================
# IMPORT DATASET
# ============================================================

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

    location_overrides: str = Form("{}"),

    user: dict = Depends(
        require_current_user
    ),
):
    """
    Upload CSV/XLS/XLSX/PDF dataset.

    Security layers:

        1. IP-based API rate limiting
        2. Bearer-token authentication
        3. Metadata validation
        4. Secure file validation
        5. Dataset/data-quality validation
    """

    # --------------------------------------------------------
    # RATE LIMIT
    # --------------------------------------------------------

    rate_limit_api(request)

    # --------------------------------------------------------
    # IMPORT METADATA
    # --------------------------------------------------------

    metadata = {
        "data_source":
            data_source.strip(),

        "laboratory_organization":
            laboratory_organization.strip(),

        "report_id":
            report_id.strip(),

        "analytical_method":
            analytical_method.strip(),

        "detection_limit":
            detection_limit.strip(),
    }

    # --------------------------------------------------------
    # OPTIONAL PDF LOCATION COORDINATE OVERRIDES
    # --------------------------------------------------------

    try:

        parsed_location_overrides = json.loads(
            location_overrides
        )

        if not isinstance(
            parsed_location_overrides,
            dict,
        ):
            raise ValueError(
                "location_overrides must be an object."
            )

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise HTTPException(
            status_code=422,
            detail={
                "message":
                    "Invalid location coordinate data.",

                "problem":
                    str(exc),
            },
        ) from exc

    # --------------------------------------------------------
    # REQUIRED METADATA VALIDATION
    # --------------------------------------------------------

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

                "missing_fields":
                    missing,
            },
        )

    # --------------------------------------------------------
    # ADD LOCATION OVERRIDES
    # --------------------------------------------------------

    metadata[
        "location_overrides"
    ] = parsed_location_overrides

    # --------------------------------------------------------
    # IMPORT DATASET
    # --------------------------------------------------------

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
    user: dict = Depends(
        require_current_user
    ),
):
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
    user: dict = Depends(
        require_current_user
    ),
):
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

    user: dict = Depends(
        require_current_user
    ),
):
    return await delete_dataset(
        dataset_id,
        user,
    )