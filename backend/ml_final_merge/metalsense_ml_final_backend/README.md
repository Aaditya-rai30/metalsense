# MetalSense Final-ML Backend Merge

These files merge the Final-ML analytical layer into the existing MetalSense backend while preserving the current security, upload, MongoDB, and route contracts.

## Updated live files

- engine/data_quality_engine.py
- engine/pollution_engine.py
- engine/anomaly_engine.py
- engine/explainability_engine.py
- engine/spatial_engine.py
- engine/temporal_engine.py
- engine/rag_engine.py
- engine/standards_registry.py
- engine/pipeline.py
- services/dataset_service.py
- services/analysis_service.py
- services/map_service.py
- services/standards_service.py
- routes/dataset_routes.py
- routes/analysis_routes.py
- routes/map_routes.py

## Not changed by this bundle

- server.py
- database.py
- security/*
- auth/session implementation
- standards_routes.py

## Important behavior

1. Existing valid sample dates are preserved.
2. Missing/unparseable dates are inferred only when a recognized season exists.
3. Inferred dates are marked with `date_inferred=true`.
4. HPI/HEI/Cd calculation keeps the existing `calculate_indices(...)` API used by the dataset service, but uses the Final-ML contamination-degree formula.
5. ML enrichment is persisted under `dataset.ml` so the existing frontend/API records remain compatible.
6. RAG is retrieval-only and does not fabricate regulatory conclusions.

## Before replacing live files

Back up the backend directory.

From backend:

    cp -a engine engine.backup-before-ml
    cp -a services services.backup-before-ml
    cp -a routes routes.backup-before-ml

Then copy the files from this bundle into the live backend.

## Smoke checks

    python -m py_compile engine/*.py services/*.py routes/*.py
    python -m uvicorn server:app --reload

Then test the authenticated dataset upload, analysis, and map endpoints with a fresh login token.
