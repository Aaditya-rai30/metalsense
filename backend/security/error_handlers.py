from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger("metalsense.security")


# ============================================================
# UNEXPECTED EXCEPTIONS
# ============================================================

async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    """
    Handle unexpected server-side exceptions.

    Full details are logged internally.
    The client receives only a generic error.
    """

    logger.exception(
        "Unhandled exception | %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error."
        },
    )


# ============================================================
# VALIDATION ERRORS
# ============================================================

async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    """
    Return a clean validation response without exposing
    unnecessary internal implementation details.
    """

    logger.warning(
        "Request validation failed | %s %s | errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request data.",
            "errors": [
                {
                    "field": ".".join(
                        str(part)
                        for part in error.get(
                            "loc",
                            [],
                        )
                        if part != "body"
                    ),
                    "message": error.get(
                        "msg",
                        "Invalid value.",
                    ),
                }
                for error in exc.errors()
            ],
        },
    )


# ============================================================
# HTTP EXCEPTIONS
# ============================================================

async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    """
    Preserve intentional HTTP errors such as 401, 403,
    404 and 429 while keeping the response structured.
    """

    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "detail": exc.detail,
        },
    )
