import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.auth_routes import router as auth_router
from routes.dataset_routes import router as dataset_router
from routes.standards_routes import router as standards_router
from routes.analysis_routes import router as analysis_router
from routes.map_routes import router as map_router


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
)


# ==========================================
# CREATE FASTAPI APPLICATION
# ==========================================

app = FastAPI(
    title="MetalSense API",
    version="0.1.0",
    description=(
        "MetalSense Water Quality and Heavy Metal "
        "Pollution Intelligence API"
    ),
)


# ==========================================
# CORS
# ==========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Dataset routes
#
# dataset_routes.py already contains:
#     prefix="/datasets"
#
# Therefore the server must mount it at /api,
# not /api/datasets.
#
# Final URLs:
#     /api/datasets
#     /api/datasets/import
#     /api/datasets/{dataset_id}
#
app.include_router(
    dataset_router,
    prefix="/api",
)


# Standards
#
# standards_routes.py already contains its own
# route prefix.
#
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
