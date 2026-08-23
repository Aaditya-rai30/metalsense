from __future__ import annotations

from fastapi import Header, HTTPException

from services.auth_service import get_current_user

from fastapi import (
    APIRouter,
    Header,
    Request,
)
from services.auth_service import (
    authenticate_user,
    create_user,
    get_current_user,
    logout,
)
async def require_current_user(
    authorization: str | None = Header(default=None),
) -> dict:
    """
    FastAPI dependency for protected endpoints.

    Resolves the authenticated user from the Bearer token.

    Returns:
        dict: Sanitized authenticated user.

    Raises:
        HTTPException 401: Missing or invalid authentication.
    """

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication scheme.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Bearer token is missing.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # Reuse the existing authentication implementation.
    user = await get_current_user(
        authorization
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    if not user.get("user_id"):
        raise HTTPException(
            status_code=401,
            detail="Invalid authenticated user.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return user


def require_dataset_owner(
    dataset: dict,
    user: dict,
) -> None:
    """
    Verify that the authenticated user owns a dataset.

    This is an authorization check, not authentication.

    Raises:
        HTTPException 403: Dataset belongs to another user.
    """

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    dataset_user_id = dataset.get("user_id")
    current_user_id = user.get("user_id")

    if not dataset_user_id or not current_user_id:
        raise HTTPException(
            status_code=403,
            detail="Access to this dataset is not permitted.",
        )

    if dataset_user_id != current_user_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this dataset.",
        )
