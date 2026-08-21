from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

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
# AUTH HELPER
# ============================================================

async def get_authenticated_user(
    authorization: str | None,
) -> dict:
    """
    Resolve the logged-in user from the Bearer token.

    This uses the same /api/auth/me endpoint contract already
    used by the frontend: Authorization: Bearer <token>.
    """

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required.",
        )

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization must use Bearer token.",
        )

    token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Bearer token is missing.",
        )

    # --------------------------------------------------------
    # Import the existing authentication implementation.
    #
    # Your project already handles token authentication in the
    # auth routes/service. Keep that implementation centralized.
    # --------------------------------------------------------

    try:
        from routes.auth_routes import get_user_from_token
    except ImportError:
        get_user_from_token = None

    if get_user_from_token is not None:
        user = await get_user_from_token(token)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token.",
            )

        return user

    # --------------------------------------------------------
    # Fallback for the current prototype if auth_routes does not
    # expose get_user_from_token().
    #
    # This keeps compatibility with the token/session structure
    # used by the current backend.
    # --------------------------------------------------------

    try:
        from database import db

        session = await db.sessions.find_one(
            {"token": token}
        )

        if not session:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token.",
            )

        user_id = session.get("user_id")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication session.",
            )

        user = await db.users.find_one(
            {"user_id": user_id}
        )

        if not user:
            raise HTTPException(
                status_code=401,
                detail="User not found.",
            )

        user.pop("_id", None)

        return user

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Authentication lookup failed: {exc}",
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

    authorization: str | None = Header(
        default=None
    ),
):
    """
    Upload CSV/XLS/XLSX dataset.

    Import metadata is mandatory and must be supplied together
    with the uploaded file.
    """

    # --------------------------------------------------------
    # Authenticate
    # --------------------------------------------------------

    user = await get_authenticated_user(
        authorization
    )

    # --------------------------------------------------------
    # Validate metadata
    #
    # FastAPI's Form(...) already makes each field required,
    # but we also reject whitespace-only values.
    # --------------------------------------------------------

    metadata = {
        "data_source": data_source.strip(),
        "laboratory_organization":
            laboratory_organization.strip(),
        "report_id": report_id.strip(),
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

    # --------------------------------------------------------
    # Import dataset
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
    authorization: str | None = Header(
        default=None
    ),
):
    user = await get_authenticated_user(
        authorization
    )

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
    authorization: str | None = Header(
        default=None
    ),
):
    user = await get_authenticated_user(
        authorization
    )

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
    authorization: str | None = Header(
        default=None
    ),
):
    user = await get_authenticated_user(
        authorization
    )

    return await delete_dataset(
        dataset_id,
        user,
    )
