from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


# ============================================================
# RATE-LIMIT CONFIGURATION
# ============================================================

# Authentication endpoints:
# 5 requests per minute per IP.
AUTH_LIMIT = 5
AUTH_WINDOW = 60

# General API endpoints:
# 60 requests per minute per IP.
API_LIMIT = 60
API_WINDOW = 60


# ============================================================
# IN-MEMORY REQUEST STORAGE
# ============================================================

_requests: dict[str, deque[float]] = defaultdict(deque)


# ============================================================
# CLIENT IP
# ============================================================

def _get_client_ip(
    request: Request,
) -> str:
    """
    Resolve the client's IP address.

    For the current local prototype, use the direct socket
    address. Proxy-aware IP extraction should only be added
    when a trusted reverse proxy is configured.
    """

    if request.client is None:
        return "unknown"

    return request.client.host or "unknown"


# ============================================================
# CORE LIMIT CHECK
# ============================================================

def _check_limit(
    ip: str,
    limit: int,
    window: int,
    bucket_name: str,
) -> None:
    """
    Enforce a fixed-window request limit using timestamps.
    """

    now = time.monotonic()

    key = f"{bucket_name}:{ip}"

    bucket = _requests[key]

    cutoff = now - window

    # Remove expired timestamps.
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    # Limit reached.
    if len(bucket) >= limit:

        retry_after = max(
            1,
            int(
                window
                - (now - bucket[0])
            ),
        )

        raise HTTPException(
            status_code=429,
            detail=(
                "Too many requests. "
                "Please try again later."
            ),
            headers={
                "Retry-After":
                    str(retry_after),
            },
        )

    # Record current request.
    bucket.append(now)


# ============================================================
# AUTHENTICATION RATE LIMITER
# ============================================================

def rate_limit_auth(
    request: Request,
) -> None:
    """
    Strict limiter for authentication endpoints.

    5 requests / minute / IP.
    """

    ip = _get_client_ip(
        request
    )

    _check_limit(
        ip=ip,
        limit=AUTH_LIMIT,
        window=AUTH_WINDOW,
        bucket_name="auth",
    )


# ============================================================
# GENERAL API RATE LIMITER
# ============================================================

def rate_limit_api(
    request: Request,
) -> None:
    """
    General limiter for expensive API endpoints.

    60 requests / minute / IP.
    """

    ip = _get_client_ip(
        request
    )

    _check_limit(
        ip=ip,
        limit=API_LIMIT,
        window=API_WINDOW,
        bucket_name="api",
    )