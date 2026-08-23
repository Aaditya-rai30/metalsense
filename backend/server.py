import logging
import os

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from routes.auth_routes import router as auth_router
from routes.dataset_routes import router as dataset_router
from routes.standards_routes import router as standards_router
from routes.analysis_routes import router as analysis_router
from routes.map_routes import router as map_router
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
)

from fastapi.exceptions import RequestValidationError

from security.error_handlers import (
    unhandled_exception_handler,
    validation_exception_handler,
    http_exception_handler,
)

# ==========================================
# ENVIRONMENT
# ==========================================

load_dotenv()


ENVIRONMENT = os.getenv(
    "ENVIRONMENT",
    "development",
).lower()


FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:8081,http://127.0.0.1:8081",
    ).split(",")
    if origin.strip()
]


ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost",
    ).split(",")
    if host.strip()
]


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger(
    "metalsense.security"
)


# ==========================================
# SECURITY HEADERS
# ==========================================

class SecurityHeadersMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        response = await call_next(
            request
        )

        # Prevent MIME sniffing.
        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        # Prevent framing/clickjacking.
        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        # Limit referrer leakage.
        response.headers[
            "Referrer-Policy"
        ] = "strict-origin-when-cross-origin"

        # Restrict browser capabilities.
        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(self)"
        )

        # Restrict cross-origin resource usage.
        response.headers[
            "Cross-Origin-Resource-Policy"
        ] = "same-origin"

        response.headers[
            "Cross-Origin-Opener-Policy"
        ] = "same-origin"

        # Only enable HSTS in production HTTPS.
        if ENVIRONMENT == "production":
            response.headers[
                "Strict-Transport-Security"
            ] = (
                "max-age=31536000; "
                "includeSubDomains"
            )

        return response


# ==========================================
# CREATE FASTAPI APPLICATION
# ==========================================

app = FastAPI(
    title="MetalSense API",
    version="0.1.0",
    description=(
        "MetalSense Water Quality and Heavy "
        "Metal Pollution Intelligence API"
    ),
)

@app.on_event("startup")
async def startup():
    from database import ensure_indexes

    await ensure_indexes()
# ==========================================
# SECURITY HEADERS MIDDLEWARE
# ==========================================

app.add_middleware(
    SecurityHeadersMiddleware
)

app.add_exception_handler(
    HTTPException,
    http_exception_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)

app.add_exception_handler(
    Exception,
    unhandled_exception_handler,
)

# ==========================================
# CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
    ],
)


# ==========================================
# TRUSTED HOSTS
# ==========================================

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
)


# ==========================================
# ROUTES
# ==========================================

# Authentication
app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"],
)


# Dataset
#
# dataset_routes.py already has:
#     prefix="/datasets"
#
# Therefore mount it at /api.
#
# Final routes:
#     /api/datasets
#     /api/datasets/import
#     /api/datasets/{dataset_id}
#
app.include_router(
    dataset_router,
    prefix="/api",
)


# Standards
app.include_router(
    standards_router,
    prefix="/api/standards",
    tags=["Standards"],
)


# Analysis
app.include_router(
    analysis_router,
    prefix="/api/analysis",
    tags=["Analysis"],
)


# Map
app.include_router(
    map_router,
    prefix="/api/map",
    tags=["Map"],
)


# ==========================================
# ROOT
# ==========================================

@app.get("/api/")
async def root():
    return {
        "message": "MetalSense API",
        "version": "0.1.0",
        "status": "running",
    }
    
